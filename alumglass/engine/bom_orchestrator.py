"""BomOrchestrator — Engine tính BOM config-driven, dùng Formula Builder.

NGUYÊN TẮC: AlumGlass chỉ config, không hardcode nghiệp vụ.
- Mọi logic đến từ DB: Bom Item, Cost Bucket, Cost Template, Profile System, Product Type.
- Tính toán ủy thác cho Formula Builder: FormulaEngine cho CẢ B4 (Bom Items) và B6
  (Cost Template). Engine được cache theo nội dung công thức (engine/engine_cache.py).
- Engine này chỉ làm: đọc config → resolve biến → build formulas → gọi FB → lưu kết quả.

Flow 7 phase:
  B0: Version pinning
  B1: Gather inputs (al_bom_vars + scoped vars từ DB — data-driven)
  B2: Pre-fetch master data (batch query)
  B3: Build formula list cho FormulaEngine (FB)
  B4: Calculate Bom Items qua FormulaEngine (DAG + topo sort)
  B5: Aggregate cost buckets (Python loop)
  B6: Calculate Cost Template qua FormulaEngine (FB) — có cache
  B7: Save results (single commit)
"""
import ast
import datetime
import frappe
import hashlib
import json
import re
import math
from collections import defaultdict

from alumglass.al_bom_engine.glass_group_resolver import glass_group_rep
from alumglass.al_bom_engine.color_group_resolver import color_group_rep
from alumglass.al_formula_rules import rule_engine
from alumglass.al_formula_rules import rule_input as rule_input_lib
from alumglass.engine import row_literal_loader
from alumglass.variable_sources.field_provenance import display_label, display_unit
from alumglass.engine.formula_messages import (
    humanize_errors, unchosen_glass_message)

# Tiền tố câu "tạm tính 0 đ" khi engine KHÔNG tra được dòng giá cho mã của
# dòng. `api.explain_bom_line` dùng đúng tiền tố này để đánh dấu bước tra giá
# là CẢNH BÁO (`severity: "warning"`) — khác `missing` vốn mang nghĩa "chưa
# lưu dữ liệu". Một chỗ khai báo, tránh 2 bản chuỗi trôi lệch nhau.
ZERO_PRICE_TRACE_PREFIX = "Chưa tìm được dòng giá cho mã này"


#: `qty` formula dạng ĐƠN GIẢN `lookup_rule('MÃ'[, INPUT]) [* MULT]` — dùng
#: để giải thích "con số số lượng ở đâu ra". Chỉ nhận ĐÚNG 1 lời gọi,
#: INPUT/MULT là biến đơn hoặc số literal. Chặng 3: INPUT được PHÉP vắng khi
#: quy tắc khai biến toàn cục (engine tự chèn biến đó trước khi tính). Dạng
#: phức tạp (toán tử khác, lời gọi lồng, biểu thức trong tham số) ⇒ ⛔ đoán,
#: để trống vết.
_QTY_RULE_SIMPLE_RE = re.compile(
    r"""^\s*lookup_rule\s*\(\s*(?P<quote>['"])(?P<code>[^'"]+)(?P=quote)\s*
        (?:,\s*(?P<input>[A-Za-z_]\w*|\d+(?:\.\d+)?)\s*)?\)\s*
        (?:\*\s*(?P<mult>[A-Za-z_]\w*|\d+(?:\.\d+)?))?\s*$""",
    re.VERBOSE)

#: Lời gọi `lookup_rule('MÃ')` MỘT tham số — chặng 3 thay bằng dạng 2 tham
#: số khi quy tắc khai biến toàn cục (`input_scope = GLOBAL`).
_ONE_ARG_LOOKUP_RULE_RE = re.compile(
    r"""\blookup_rule\s*\(\s*(?P<quote>['"])(?P<code>[^'"\n]+)(?P=quote)\s*\)""")

#: Token là số literal (khác tên biến) trong `lookup_rule(...)` đơn giản.
_SIMPLE_NUMBER_TOKEN_RE = re.compile(r"^\d+(?:\.\d+)?$")


def assert_parent_editable(parent, docstatus=None):
    """Chặn tính giá lên dòng của báo giá ĐÃ CHỐT / ĐÃ HUỶ — theo TÊN CHA.

    Bản dùng chung cho cả 2 loại đích:
      - dòng ĐÃ LƯU: `assert_quotation_item_editable(name)` tra parent rồi gọi
        hàm này;
      - dòng MỚI (chưa có tên dòng, chỉ có tên cha): API `preview_bom` gọi
        thẳng hàm này với `params["parent"]` — dòng mới chưa có trong DB nên
        không thể tra parent từ tên dòng.

    `parent` rỗng/`new-…` = báo giá CHƯA lưu ⇒ docstatus coi như 0 (cho qua).
    `docstatus` truyền sẵn để caller khỏi đọc DB lần nữa khi đã biết.
    """
    if not parent:
        frappe.throw(
            "Không tìm thấy báo giá để kiểm tra trạng thái — không tính giá được.",
            frappe.DoesNotExistError,
        )
    if str(parent).startswith("new-"):
        # Báo giá chưa lưu ⇒ chưa thể submit/huỷ ⇒ luôn sửa được.
        return
    if docstatus is None:
        docstatus = frappe.db.get_value("Quotation", parent, "docstatus") or 0
    if docstatus == 1:
        frappe.throw(
            "Báo giá '{0}' đã gửi khách nên không tính lại giá được — số liệu đã "
            "chốt phải giữ nguyên. Muốn đổi giá: huỷ báo giá này rồi bấm "
            "\"Tạo bản sửa\" (Amend), hoặc tạo báo giá mới.".format(parent)
        )
    if docstatus == 2:
        frappe.throw(
            "Báo giá '{0}' đã huỷ nên không tính lại giá được. Hãy tạo báo giá "
            "mới nếu cần báo giá lại cho khách.".format(parent)
        )


def assert_quotation_item_editable(quotation_item_name):
    """Chặn tính giá lên dòng của báo giá ĐÃ CHỐT / ĐÃ HUỶ.

    `b7_save_results` ghi giá bằng `frappe.db.set_value()` — hàm này bỏ qua
    toàn bộ cơ chế bảo vệ của Frappe (⛔ không chạy document event, ⛔ không
    kiểm quyền, ⛔ không chặn chứng từ đã submit) nên phải tự chốt ở đây.
    Dùng docstatus của Quotation CHA (⛔ không tin docstatus của dòng con).

    Dùng CHUNG cho cả 2 đường: `b7_save_results` (chốt chính, sát lệnh ghi)
    và `api.calculate_bom` (chốt sớm, trước mọi tính toán).
    """
    parent = frappe.db.get_value("Quotation Item", quotation_item_name, "parent")
    if not parent:
        frappe.throw(
            "Không tìm thấy dòng báo giá %s" % quotation_item_name,
            frappe.DoesNotExistError,
        )
    assert_parent_editable(parent)


# ── calc_meta: dấu vân tay của THAM SỐ đã tính (phase 1 = chỉ GHI) ─────
# `params_hash` trả lời đúng một câu: "con số này được tính từ bộ tham số nào?"
# Phase 2 mới dùng nó để kiểm khi Lưu; phase 1 chỉ ghi kèm kết quả.
# Chuẩn hoá: al_bom_vars (chuỗi JSON do client gửi) được PARSE rồi dump lại với
# `sort_keys` — thứ tự key/thụt lề không làm đổi hash. ⛔ Không ép "2400" thành
# 2400: engine nhận đúng kiểu client gửi, hai kiểu có thể cho kết quả khác nhau
# nên ⛔ không được báo "cùng tham số" (khác design §8.7 — xem báo cáo job).
def canonical_params(bom_code=None, bom_version=None, item_code=None,
                     bom_vars=None):
    """Bộ tham số đã chuẩn hoá — dùng CHUNG cho hash và (phase 2) kiểm khi Lưu."""
    if isinstance(bom_vars, str):
        try:
            bom_vars = json.loads(bom_vars or "{}")
        except (ValueError, TypeError):
            # Chuỗi không phải JSON: giữ nguyên để hash vẫn phân biệt được.
            pass
    return {
        "al_bom": bom_code or "",
        "al_bom_version": bom_version or "",
        "item_code": item_code or "",
        "al_bom_vars": bom_vars if bom_vars is not None else {},
    }


def compute_params_hash(bom_code=None, bom_version=None, item_code=None,
                        bom_vars=None):
    """SHA-256 (hex) của tham số đã chuẩn hoá — cùng tham số ⇒ cùng hash."""
    payload = json.dumps(
        canonical_params(bom_code, bom_version, item_code, bom_vars),
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _utc_now_iso():
    """ISO-8601 UTC (giây) — ⛔ không phụ thuộc `frappe.utils.now_datetime`
    để hàm thuần (engine + standalone test) chạy được cả ngoài site."""
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# ── SAFE FUNCS dùng chung B4 + B6 (inject vào FormulaEngine của cả 2 phase) ──
def _missing_reason_text(reason):
    """Dịch mã lý do thiếu (máy) sang câu người đọc.

    Mã gốc: `khong_co_nguon:<DocType>` / `thieu_field:<DocType>.<field>`
    (xem `engine/row_literal_loader.py`). Tên bảng/field chỉ vào log, ⛔ UI.
    """
    code = (reason or "").split(":", 1)[0]
    if code == "khong_co_nguon":
        return "chưa tìm được dữ liệu nguồn đã khai"
    if code == "thieu_field":
        return "dữ liệu nguồn không có thông tin cần lấy"
    return "chưa xác định được nguồn giá trị"


def _record_engine_warning(key, message):
    """Ghi cảnh báo engine vào túi dùng chung (xem engine/composite_pricing).

    Module-level vì `_lookup_rule`/`_roundup` là safe_func truyền vào FB —
    không có `self` để ghi thẳng vào `bom_engine_errors`/`cost_engine_errors`.
    Túi được BomOrchestrator hút về 2 túi lỗi ở B4/B6 (xem
    `_drain_engine_warnings`) và đi ra ngoài qua `al_bom_result["errors"]`.
    """
    from alumglass.engine.composite_pricing import add_engine_warning
    add_engine_warning(key, message)


def _lookup_rule(rule_code, input_value=None):
    """Tra cứu AL Rule (rule trả SỐ). Hỗ trợ CONSTANT, THRESHOLD, LOOKUP.

    Module-level để B4 và B6 dùng CHUNG một implementation (nay cả hai đều
    truyền qua `safe_funcs` của FormulaEngine — xem `_engine_safe_funcs`):
    tránh duplicate + đảm bảo 2 phase resolve rule giống nhau.

    Chặng 2B: `AL Rule` gộp 2 doctype cũ, cột kết quả do `result_type` quyết
    định. Công thức chỉ dùng được rule trả SỐ (NUMBER) — rule chọn mã vật tư
    (ITEM) lọt vào đây là lỗi cấu hình, phải nổi lên chứ ⛔ im lặng trả 0.
    """
    try:
        rule = frappe.get_cached_doc("AL Rule", rule_code)
        # Nhãn NGƯỜI-ĐỌC-ĐƯỢC cho mọi câu cảnh báo: `rule_name`, ⛔ bao giờ
        # phơi `rule_code` (mã nội bộ) ra nhân viên báo giá. Fallback về mã
        # khi quy tắc chưa đặt tên.
        rule_label = rule.get("rule_name") or rule_code
        if (rule.get("result_type") or "") != "NUMBER":
            _record_engine_warning(
                "lookup_rule_sai_loai:%s" % rule_code,
                "Quy tắc \"%s\" là quy tắc chọn mã vật tư nên không dùng được "
                "trong công thức — tạm tính 0, thành tiền chưa đúng. Báo quản "
                "trị kiểm tra quy tắc này." % rule_label,
            )
            return 0
        active = rule_engine.rule_is_active(rule)
        result = rule.resolve(input_value)
        if not active:
            # Rule đã TẮT nhưng công thức còn tham chiếu: vẫn trả 0 để lượt
            # tính không chết, nhưng PHẢI nổi lên `al_bom_result["errors"]` —
            # ⛔ im lặng trả 0 khiến người dùng tưởng giá đúng.
            _record_engine_warning(
                "lookup_rule_da_tat:%s" % rule_code,
                "Quy tắc \"%s\" đã TẮT nhưng công thức còn dùng — tạm tính 0, "
                "thành tiền chưa đúng. Báo quản trị bật lại quy tắc này."
                % rule_label,
            )
        elif result is None:
            # Rule ĐANG BẬT nhưng không dòng nào khớp giá trị tra cứu: trước
            # đây rơi thẳng về 0 trong im lặng ⇒ người dùng tưởng giá đúng.
            # Rule TẮT đã có cảnh báo riêng ở nhánh trên nên ⛔ báo trùng.
            _record_engine_warning(
                "lookup_rule_khong_khop:%s" % rule_code,
                "Quy tắc \"%s\" không có dòng nào khớp giá trị tra cứu — đang "
                "tạm tính 0, thành tiền chưa đúng. Báo quản trị kiểm tra lại "
                "dải/bảng tra của quy tắc." % rule_label,
            )
        return result if result is not None else 0
    except frappe.DoesNotExistError:
        # F9: mã rule sai trong công thức KHÔNG được biến mất im lặng — ghi
        # cảnh báo vào túi lỗi engine (hiện ở kết quả) rồi vẫn trả 0 để BOM
        # không chết. Rule không tồn tại nên ⛔ có tên để nêu — chỉ có mã.
        _record_engine_warning(
            "lookup_rule_thieu_ma:%s" % rule_code,
            "Không tìm thấy quy tắc có mã '%s' (công thức tham chiếu sai "
            "mã?) — tạm tính 0, thành tiền chưa đúng. Báo quản trị kiểm tra "
            "công thức." % rule_code,
        )
        return 0


def _roundup(x, y=None):
    """Làm tròn LÊN — ngữ nghĩa ROUNDUP(x, y) kiểu Excel (F13).

    - y rỗng/0/None → math.ceil(x): giữ NGUYÊN hành vi cũ (config hiện có
      dùng `roundup(H_mm/700, 0)` theo hướng dẫn trên AL Bom Item).
    - y > 0 → làm tròn lên tới y chữ số thập phân (roundup(2.111, 2) = 2.12).
    - y < 0 → làm tròn lên tới hàng chục/trăm (roundup(1234, -2) = 1300).
    Excel làm tròn RA XA 0 nên phần đã nhân hệ số của số âm dùng math.floor
    (math.ceil(-2.5) = -2, sai ngữ nghĩa Excel ROUNDUP(-2.5) = -3).
    """
    if not y:
        return math.ceil(x)
    factor = 10 ** int(y)
    scaled = x * factor
    return (math.ceil(scaled) if scaled >= 0 else math.floor(scaled)) / factor


#: Bộ safe_funcs nhớ sẵn — xem `_engine_safe_funcs`.
_ENGINE_SAFE_FUNCS = {}


def _engine_safe_funcs():
    """Bộ `safe_funcs` dùng chung B4 + B6 — dựng MỘT LẦN, giữ nguyên identity.

    VÌ SAO phải nhớ kết quả: engine nay được cache (xem `engine/engine_cache.py`)
    nên nó giữ tham chiếu tới đúng dict này. Dựng dict mới mỗi lần gọi vẫn cho
    kết quả đúng, nhưng làm cấu hình "không còn là một" khi soi lại — và quan
    trọng hơn, `lookup_calc_pattern` phải import TRỄ (tránh vòng import lúc nạp
    module), nên cần một chỗ nhớ.

    Cả 3 hàm đều là hàm module-level, ⛔ không giữ trạng thái theo instance;
    `_lookup_rule` ghi cảnh báo vào túi chung trên `frappe.local` (theo request),
    nên cache engine ⛔ không làm thất lạc cảnh báo.
    """
    funcs = _ENGINE_SAFE_FUNCS.get("v1")
    if funcs is None:
        from alumglass.al_formula_rules.doctype.al_quantity_calc_method.al_quantity_calc_method import (
            lookup_calc_pattern)
        funcs = {
            "lookup_calc_pattern": lookup_calc_pattern,
            "lookup_rule": _lookup_rule,
            "roundup": _roundup,
        }
        _ENGINE_SAFE_FUNCS["v1"] = funcs
    return funcs


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


def _format_number_vi(value, unit=""):
    """Số kiểu Việt Nam cho câu giải thích: 8 → "8", 6.6 → "6,6", 50000 → "50.000"."""
    if value is None or isinstance(value, bool):
        return "—"
    if isinstance(value, (int, float)):
        rounded = round(float(value), 4)
        if rounded == int(rounded):
            text = "{:,}".format(int(rounded)).replace(",", ".")
        else:
            text = ("{:,.4f}".format(rounded)
                    .rstrip("0").rstrip(".")
                    .replace(",", "|").replace(".", ",").replace("|", "."))
    else:
        text = str(value).strip()
        if not text:
            return "—"
    return text + (unit or "")


def _lower_first(text):
    """Hạ chữ đầu (nhãn biến đứng giữa câu): "Số cánh" → "số cánh"."""
    text = (text or "").strip()
    if not text:
        return ""
    return text[:1].lower() + text[1:]


def _dimension_value_lines(value):
    """Các dòng có nghĩa của 1 giá trị dimension (strip, bỏ dòng rỗng).

    Dòng giá áp cho NHIỀU lựa chọn lưu value nhiều dòng — vd
    `"IMPORT\\nDOMESTIC"` hay `"POWDER_COATED\\nANODIZED\\nWOOD_GRAIN"` —
    ⛔ KHÔNG phải 1 giá trị đã chọn.
    """
    if value is None:
        return []
    text = value if isinstance(value, str) else str(value)
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _is_zero_dimension_value(value):
    """0 nghĩa là KHÔNG dùng tiêu chí đó (cột số để mặc định) — ⛔ không
    phải thông số thật, ⛔ không đưa vào câu giải thích giá."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == 0
    try:
        return float(str(value).strip()) == 0
    except (TypeError, ValueError):
        return False


def _format_money_vi(value):
    """Tiền cho câu giải thích: 50000 → "50.000 đ"."""
    text = _format_number_vi(value)
    return text if text == "—" else text + " đ"


def _default_price_list(price_list=None):
    """Price list mặc định — đọc từ Selling Settings (chuẩn Frappe/ERPNext),
    KHÔNG hardcode 'Standard Selling'. Fallback 'Standard Selling' chỉ khi
    Selling Settings chưa cấu hình (giữ hành vi cũ cho site mới/demo).
    Đồng bộ với fb_handlers.py (đã configurable qua source_config từ trước).

    `price_list`: bối cảnh giá do MÁY CHỦ truyền vào (xem
    `BomOrchestrator._default_price_list`) — có giá trị thì dùng luôn, ⛔ không
    đọc cấu hình. Mặc định `None` = giữ NGUYÊN hành vi cũ cho mọi caller khác
    (fb_handlers, install_fb_bindings, api).
    """
    if price_list:
        return price_list
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


# 2026-10 (fix hiệu năng #5): bảng `Formula Global Variable` là hằng số cấu
# hình (VAT_RATE, NC_SX_PCT, ASYNC_BOM_THRESHOLD...), đọc MỖI dòng BOM tính
# nhưng gần như không đổi → cache Redis. Cache, khoá cache, TTL và hàm đọc
# dùng chung nằm ở 1 nguồn duy nhất:
# formula_builder/api/global_variable_cache.py
# (`CACHE_TTL_SECONDS` = 60s, invalidate bởi
# `FormulaGlobalVariable.on_update`/`on_trash` phía formula_builder).
#
# ⚠️ `frappe.db.set_value()` KHÔNG chạy document event (xem
# frappe/database/database.py: "will not call Document events"), nên các
# đường ghi kiểu đó KHÔNG xoá được cache — vd patch
# alumglass/patches/v28_9/normalize_percent_system_vars.py sửa
# VAT_RATE/OH_VC_PCT/OH_QLY_PCT bằng frappe.db.set_value(...,
# update_modified=False). Với những đường ghi ấy, TTL 60s là lưới an toàn
# chặn cửa sổ đọc giá trị cũ.


# ── Phase 0b: Biến phần trăm lưu phần trăm nguyên (8/12/16/3/3/10) ──────
# Engine chia 100 → 0.08 trước khi dùng. Nhận diện theo suffix tên var:
#   *_PCT (NC_SX_PCT, OH_VC_PCT, OH_QLY_PCT), *_MARGIN (PROFIT_MARGIN),
#   *_RATE (VAT_RATE).
_PERCENT_VAR_SUFFIXES = ("_PCT", "_MARGIN", "_RATE")


# ── CONFIG: Các field kết quả ghi vào Quotation Item ─────────────────
OUTPUT_FIELDS = [
    "al_gia_vat", "al_gia_ban", "al_bom_result",
]

# ── F8: các trường tổng tiền của Quotation cha cần ghi lại sau khi đổi rate
# (đối chiếu erpnext/selling/doctype/quotation/quotation.json). Chỉ ghi trường
# THỰC SỰ có trên meta (meta.has_field) để không lệch giữa các phiên bản
# Frappe/ERPNext (máy này v14, đích v16).
_QUOTATION_TOTAL_FIELDS = (
    "total_qty",
    "total",
    "base_total",
    "net_total",
    "base_net_total",
    "total_taxes_and_charges",
    "base_total_taxes_and_charges",
    "grand_total",
    "base_grand_total",
    "rounded_total",
    "base_rounded_total",
    "in_words",
    "base_in_words",
)

# ── DEFAULT: Các field trong Bom Item chứa công thức ─────────────────
# ⚠ LƯỚI AN TOÀN CUỐI, KHÔNG phải nguồn cấu hình. Nguồn DUY NHẤT là
# `AL Formula Field` (đọc qua `alumglass.api.formula_registry.
# get_formula_fieldnames`) — xem `_resolve_formula_fieldnames`: danh sách này
# chỉ được dùng khi KHÔNG đọc được sổ đăng ký, và khi đó engine BẮT BUỘC ghi
# cảnh báo `formula_fields_fallback_registry` vào túi lỗi (⛔ im lặng rơi lưới).
DEFAULT_FORMULA_FIELDS = ["width", "height", "qty", "show_condition",
                           "item_condition_formula", "rule_input_expr"]

# ── B1: sổ đăng ký "field nào là field công thức" ────────────────────
# DocType + bảng con mà engine đánh giá công thức (xem `AL Formula Field`).
FORMULA_REGISTRY_DOCTYPE = "AL Bom Set"
FORMULA_REGISTRY_CHILD_TABLE = "items"

#: Các field CÓ THỂ mang công thức trên dòng BOM. ⚠ CHỈ dùng để PHÁT HIỆN
#: "dòng đang có công thức mà sổ đăng ký không khai" ⇒ cảnh báo
#: `formula_fields_registry_thieu:<field>`. ⛔ KHÔNG dùng để tính: danh sách
#: này không thêm field nào vào công thức, engine chỉ đánh giá đúng những
#: field có trong registry.
#:
#: R5 (2026-11-27): `panel_count_formula` / `qty_per_panel_formula` đã bị GỠ
#: khỏi `AL Bom Item` (ô chết, engine không đọc) ⇒ bỏ khỏi đây. Giữ lại tên
#: đã xoá sẽ làm cảnh báo "sổ đăng ký thiếu" trỏ tới field không còn tồn tại.
FORMULA_FIELD_CANDIDATES = tuple(DEFAULT_FORMULA_FIELDS)


class BomOrchestrator:
    """Engine tính BOM 7-phase, hoàn toàn config-driven."""

    #: Field của dòng Quotation Item được phép LẤY TỪ `params` khi preview.
    #: ⛔ KHÔNG mở rộng danh sách này: `params` do client gửi lên, mọi field
    #: ngoài đây (tiền tệ, bảng giá, khách hàng, company…) phải đọc từ DB để
    #: client không đổi được bối cảnh giá.
    #: ⚠ Ngoại lệ DUY NHẤT là các khoá `SERVER_CONTEXT_KEYS` bên dưới: chúng
    #: chỉ do code MÁY CHỦ (`alumglass.api.preview_guard`) đặt vào, sau khi
    #: `alumglass.api._parse_preview_params` đã loại chúng khỏi tham số client.
    PREVIEW_ROW_FIELDS = (
        "al_bom", "al_bom_version", "al_bom_vars",
        "item_code", "item_name", "qty", "uom", "stock_uom",
    )

    #: Khoá bối cảnh giá do MÁY CHỦ truyền qua `params` (tiền tệ, bảng giá,
    #: công ty, khách hàng, tỷ giá) → field tương ứng của Quotation. Vì sao
    #: cần: báo giá MỚI chưa có dòng trong DB ⇒ `_doc_currency()`/
    #: `_default_price_list()` không đọc được `Quotation.currency`/
    #: `selling_price_list` ⇒ rơi về mặc định site ⇒ chọn Item Price khác
    #: tiền tệ, giá lưu khác giá đã preview.
    #: ⛔ Không bao giờ nhận các khoá này từ client: `_parse_preview_params`
    #: (api) loại bỏ tường minh trước khi dựng `params` cho engine.
    SERVER_CONTEXT_FIELDS = (
        ("_currency", "currency"),
        ("_price_list", "selling_price_list"),
        ("_company", "company"),
        ("_conversion_rate", "conversion_rate"),
        ("_plc_conversion_rate", "plc_conversion_rate"),
        ("_customer", "customer"),
    )

    SERVER_CONTEXT_KEYS = tuple(key for key, _field in SERVER_CONTEXT_FIELDS)

    def __init__(self, quotation_item_name=None, params=None, persist=True):
        """`persist=True` (mặc định) = hành vi CŨ 100%: đọc dòng từ DB
        (B0) và ghi kết quả + tổng tiền + commit (B7).

        `persist=False` = PREVIEW: dựng `_qi_doc` từ `params` (phủ lên dòng DB
        nếu có tên), chạy B0→B6, ⛔ KHÔNG gọi B7 ⇒ ⛔ không ghi một byte nào.
        Hình dạng `_build_response()` giữ nguyên, thêm `calc_meta`.
        """
        self.quotation_item_name = quotation_item_name
        self.params = dict(params or {})
        self.persist = bool(persist)
        self.inputs = {}
        self.bom_items = []
        self.row_literals = {}
        self.bom_result = []
        self.buckets = defaultdict(float)
        self.cost_result = {}
        self.cost_template_trace = {}   # V6 P8: line_code → trace (build lúc tính)
        self.gia_vat = 0
        # V6 P10/D7: items snapshot cost template ĐANG dùng (b6) — để
        # _resolve_final_price/_resolve_pre_vat_price dò dòng is_final_price /
        # is_pre_vat_price (fallback line_code GIA_VAT/GIA_BAN nếu không flag).
        self._cost_template_snapshot_items = []
        # B5 FB-max: lỗi structured từ engine (B4/B6) — lưu trong al_bom_result
        self.bom_engine_errors = {}
        self.cost_engine_errors = {}
        # Cached references (tránh load lại)
        self._qi_doc = None
        self._bom_doc = None
        self._formula_fieldnames = None
        self._dim_fieldname_cache = None   # Cache composite key field mapping
        self._dim_mapping_raw_cache = None  # V6 P10: cache mapping thô (chưa lọc category)
        # F5-3/F5-6 (audit 2026-10): cache tiền tệ báo giá (lọc Item Price theo
        # tiền tệ) + price_list ĐANG dùng chung cho mọi query giá trong 1 lần
        # chạy BOM (nhánh FB-max đọc từ binding, batch #6 trước đây luôn dùng
        # _default_price_list() → trộn 2 bảng giá trong cùng dict `prices`).
        self._currency_cache = None
        self._currency_filter_cache = {}
        self._active_price_list_cache = None
        self._line_formulas = defaultdict(dict)  # V6 P8: slug → {field: formula} (trace line vật tư)
        # V6 P4 (A5/A7): override config từ al_bom_vars — set trong b1.
        # Mọi override đều OPT-IN — không có key → giữ nguyên 100% hành vi cũ.
        self.accessory_set_code = None
        self.glass_master_override = None
        self.glass_master_map = {}
        self.color_master_override = None
        self.color_master_map = {}
        self.profile_system_override = None
        self.cost_template_override = None
        # V6 P5 (Phase 1c): giá trị từ child table system_variables của AL Profile
        # System — áp lại sau FB binding (FB đọc offset_* field).
        self._profile_child_vars = {}
        # Tên biến người dùng NHẬP TƯỜNG MINH (top-level al_bom_vars + extra_vars)
        # — set trong b1_gather_inputs, dùng để áp LẠI sau bước resolve lại system
        # vars theo profile override (1.5c): user input luôn thắng profile.
        self._user_provided = set()
        # 2026-09 (nâng cấp #3): {slug: {glass_thick, glass_type, max_area_m2}}
        # — set trong b2_prefetch_master_data, đọc lại trong
        # b4_calculate_bom_items để validate diện tích kính vs khổ tối đa.
        self._glass_data = {}
        # Vết tra cứu (Phase 2) — additive, không tham gia tính toán:
        #   _resolved_rule_items: (rule_code, rule_input) -> item_code (B2)
        #   _price_info: item_code -> {price_list, row, price, base_price,
        #                              multiplier} — dòng Item Price ĐÃ dùng
        #   _price_rows: item_code -> tên dòng Item Price khớp (tra nhanh)
        self._resolved_rule_items = {}
        self._price_info = {}
        self._price_rows = {}
        # Nhãn người đọc (Phase 2 — UX): KHÔNG bao giờ đưa mã kỹ thuật ra câu
        # giải thích. `*_raw` vẫn giữ dữ liệu gốc để support đối chiếu.
        self._rule_names = {}          # rule_code -> rule_name
        # rule_code -> {rule_name, input_label, input_unit, output_label,
        #               rule_description} — nhãn quy tắc TỰ MÔ TẢ (AL Rule
        # thêm 4 field mô tả). `_rule_names` giữ nguyên dạng chuỗi cũ để mọi
        # chỗ đang đọc nó không phải sửa; câu trace đọc metadata từ đây.
        self._rule_meta = {}
        self._rule_matches = {}        # (rule_code, input) -> {rule_name, range}
        self._item_names = {}          # item_code -> item_name
        self._price_list_names = {}    # price_list -> price_list_name
        self._dimension_meta = None    # variable_name -> {label, link_doctype}
        self._link_value_cache = {}    # (doctype, name) -> tên hiển thị
        # var_name -> nhãn người đọc (AL Variable Library.var_label) — chỉ đọc
        # khi công thức lỗi thiếu biến, để câu báo không phơi mã kỹ thuật.
        self._var_label_cache = {}

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
        # B7 là đường GHI DUY NHẤT của engine — preview (persist=False) bỏ hẳn
        # để "xem trước" không đẻ ra một byte nào xuống DB (kể cả status/job id).
        if self.persist:
            self.b7_save_results()
        return self._build_response()

    # ══════════════════════════════════════════════════════════════════
    # B0: Version Pinning
    # ══════════════════════════════════════════════════════════════════
    def b0_version_pinning(self):
        if self.persist:
            # Đường CŨ, giữ nguyên 100%: dòng phải tồn tại trong DB.
            self._qi_doc = frappe.get_doc("Quotation Item", self.quotation_item_name)
        else:
            self._qi_doc = self._build_preview_doc()
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
                # F11 — ưu tiên tái dùng version mới nhất đã có của BOM (nếu
                # `current_version` chưa set vì version còn ở Draft chưa qua nút
                # Xuất bản), tránh mỗi lần bấm "Tính giá" lại đẻ thêm một
                # version. Đường tính giá CỐ Ý KHÔNG tạo version (tránh sinh dữ
                # liệu ngầm + tránh vòng qua quy trình duyệt): engine cũng
                # không thể "tính live" khi thiếu version — b2_prefetch_master_
                # data throw "BOM Version không có snapshot", còn _get_bom_set
                # trả None khi thiếu bom_version. Nên BOM thật sự CHƯA có
                # version nào thì báo lỗi rõ ràng, chỉ người dùng tự tạo
                # version qua nút "Tạo BOM Version mới" trên form BOM rồi quay
                # lại bấm Tính giá.
                self.bom_version_name = self._latest_existing_version()
                if self.bom_version_name:
                    self.bom_version = frappe.get_cached_doc(
                        "AL BOM Version", self.bom_version_name)
                else:
                    frappe.throw(
                        "BOM '%s' chưa có phiên bản nào nên chưa tính giá được. "
                        "Mở BOM này → bấm \"Tạo BOM Version mới\" → duyệt và "
                        "Xuất bản phiên bản, rồi bấm \"Tính giá\" lại."
                        % self.bom_code
                    )

    def _build_preview_doc(self):
        """Dựng `_qi_doc` cho đường PREVIEW (persist=False).

        - Dòng ĐÃ LƯU ⇒ đọc doc từ DB rồi PHỦ các field whitelist của `params`
          (danh sách `PREVIEW_ROW_FIELDS`). Nhờ vậy engine thấy đúng tham số
          người dùng đang thấy trên dialog mà ⛔ không phải ghi DB trước.
          ⚠ Doc DB được CHÉP sang `frappe._dict` trước khi phủ: `frappe.get_doc`
          để object trong document cache của request — sửa thẳng object đó có
          thể làm code khác trong cùng request đọc số đã bị phủ.
        - Dòng MỚI (`new-…`/không có tên) ⇒ `frappe._dict` chỉ từ params.
          Chỉ field trong whitelist + định danh cha được đưa vào — ⛔ không
          nhận tiền tệ/bảng giá/khách hàng TỪ CLIENT. Ngoại lệ: bối cảnh giá
          do MÁY CHỦ truyền (`SERVER_CONTEXT_FIELDS`, khoá `_…`) được ghi
          thành FIELD THẬT (`currency`, `selling_price_list`…) để các đường
          đọc doc (vd. `fb_handlers._doc_currency`) cũng thấy đúng bối cảnh
          của báo giá đang lưu — khoá `_…` tự nó ⛔ lọt vào doc.
        """
        params = self.params or {}
        name = self.quotation_item_name

        if name and not str(name).startswith("new-"):
            doc = frappe.get_doc("Quotation Item", name)
            if isinstance(doc, dict):
                data = dict(doc)
            elif hasattr(doc, "as_dict"):
                data = dict(doc.as_dict())
            else:
                data = {}
                for field in ("name", "parent", "parenttype", "parentfield", "doctype"):
                    data[field] = doc.get(field)
            for field in self.PREVIEW_ROW_FIELDS:
                if data.get(field) is None:
                    data[field] = doc.get(field)
                if field in params and params[field] is not None:
                    data[field] = params[field]
            self._apply_server_price_context(data)
            return frappe._dict(data)

        data = {
            "doctype": "Quotation Item",
            "name": name or "new-preview-item",
            "parenttype": "Quotation",
            "parentfield": "items",
            # Cha chỉ để biết TIỀN TỆ / quyền — ⛔ không phải nguồn giá.
            "parent": params.get("parent") or "",
        }
        for field in self.PREVIEW_ROW_FIELDS:
            if field in params and params[field] is not None:
                data[field] = params[field]
        self._apply_server_price_context(data)
        return frappe._dict(data)

    def _apply_server_price_context(self, data):
        """Ghi bối cảnh giá MÁY CHỦ (`_currency`…) thành field THẬT của doc giả.

        Chỉ áp khi `params` có khoá tương ứng (client ⛔ gửi được — xem
        `SERVER_CONTEXT_FIELDS`). Nhờ vậy đường đọc doc (`fb_handlers.
        _doc_currency` → `doc.get("currency")`) thấy đúng tiền tệ của báo giá
        đang lưu, kể cả khi báo giá còn là bản nháp chưa có dòng trong DB.
        ⛔ Không ghi khoá `_…` vào doc (sẽ thành field rác).
        """
        params = self.params or {}
        for key, field in self.SERVER_CONTEXT_FIELDS:
            value = params.get(key)
            if value is not None and value != "":
                data[field] = value
        return data

    def _latest_existing_version(self):
        """F11 — tìm AL BOM Version mới nhất của BOM này (creation mới nhất).

        `frappe.get_all` KHÔNG có `order_by` sẽ rơi về `DefaultOrderBy` của meta
        — dùng `order_by` tường minh để không phụ thuộc meta.
        """
        rows = frappe.get_all(
            "AL BOM Version",
            filters={"bom": self.bom_code},
            fields=["name"],
            order_by="creation DESC",
            limit=1,
        )
        return rows[0]["name"] if rows else None

    # ══════════════════════════════════════════════════════════════════
    # B1: Gather Inputs — đọc từ al_bom_vars JSON + resolve system vars
    # ══════════════════════════════════════════════════════════════════
    def b1_gather_inputs(self):
        # ── HỢP ĐỒNG ƯU TIÊN (cao → thấp), lớp GHI SAU thắng ─────────
        #   user input tường minh (al_bom_vars top-level + extra_vars)   (1.5)
        #     > AL Profile System.system_variables child override        (1.4b)
        #       > FB get_live_context (binding + doc field + global)     (1.4)
        #         > Formula Global Variable                              (1.2)
        # Lớp chỉ-điền-khi-thiếu: Library system var (1.3) + user var
        # default_value (1.6) — không thắng lớp nào ở trên.
        # ⚠ 1.5c resolve LẠI toàn bộ system vars theo profile override nên có
        # thể đè biến user vừa sửa; vì vậy giá trị user được snapshot trước và
        # ÁP LẠI ngay sau đó (user input luôn thắng profile).
        # ── 1.1 Đọc user inputs từ al_bom_vars JSON (đã có trong _qi_doc) ──
        bom_vars_str = self._qi_doc.get("al_bom_vars")
        bom_vars = {}
        if bom_vars_str:
            try:
                bom_vars = json.loads(bom_vars_str) if isinstance(
                    bom_vars_str, str) else bom_vars_str
            except json.JSONDecodeError:
                pass

        # extra_vars ghi SỚM ở đây (giữ nguyên hành vi cũ cho mọi lớp đọc
        # giữa chừng), rồi được áp LẠI ở 1.5 cùng top-level — nếu chỉ ghi ở
        # đây, Formula Global Variable (1.2) sẽ đè giá trị user đã nhập.
        self.inputs.update(bom_vars.get("extra_vars", {}) if isinstance(
            bom_vars.get("extra_vars"), dict) else {})

        # ── 1.2 Global Variables từ Formula Builder ──────────────────
        # 2026-10 (fix hiệu năng #5): bảng hằng số cấu hình, gần như không
        # đổi nhưng trước đây full-table-scan mỗi lần tính 1 dòng BOM. Helper
        # dùng chung: formula_builder/api/global_variable_cache.py (cache
        # Redis, TTL 60s, invalidate từ on_update/on_trash của
        # FormulaGlobalVariable — xem comment đầu khối ở trên, gồm cả giới
        # hạn với đường ghi `frappe.db.set_value`).
        from formula_builder.api.global_variable_cache import (
            get_all_global_variables,
        )
        for gv in get_all_global_variables():
            try:
                self.inputs[gv["var_name"]] = float(gv["constant_value"])
            except (ValueError, TypeError):
                self.inputs[gv["var_name"]] = gv["constant_value"]

        # ── 1.4 FB-max (B1) — Phase 3a FLIP (thứ tự mới): FB resolve TRƯỚC.
        #     get_live_context = nguồn chính (global binding + system variable
        #     FVB đã seed — topological sort + fallback default_value).
        #     Khi FVB seed thiếu/không binding → get_live_context trả ít →
        #     bước 1.3 bên dưới giữ resolver cũ (fill-missing). Trước đây thứ
        #     tự là 1.3 → 1.4; đổi sang FB-first để biến đã seed KHÔNG phải
        #     resolve 2 lần (1.3 chạy legacy rồi FB ghi đè cùng giá trị).
        fb_ctx = self._resolve_fb_context()
        for key, value in fb_ctx.items():
            self.inputs[key] = value

        # ── 1.3 Resolve system variables từ AL Variable Library ──────
        #     (fallback backward-compat — CHỈ cho biến CHƯA có trong fb_ctx /
        #     inputs: guard `fill_missing_only` — biến FB đã phủ (seed) thì
        #     giữ giá trị FB, không chạy legacy lại; biến CHƯA seed (source
        #     không mappable / không binding) vẫn resolve như cũ + fallback
        #     default_value / AL Rule CONSTANT bên dưới.)
        self._resolve_system_variables(fill_missing_only=True)

        # ── 1.4b V6 P5 (Phase 1c): child table system_variables ưu tiên hơn
        #     FB binding tự resolve (FB đọc source_field/offset_* của profile).
        #     Child table = config tường minh theo profile → ghi đè sau cùng
        #     (trước bom_vars user input — user input vẫn thắng cuối cùng).
        for key, value in self._profile_child_vars.items():
            self.inputs[key] = value

        # ── 1.5 Merge user input values (bom_vars ghi đè) ────────────
        # Gộp CẢ `extra_vars` + top-level (xem hợp đồng ưu tiên đầu hàm):
        # đây là lớp mạnh nhất, áp SAU global/FB/Library. Ghi nhớ danh sách
        # biến user đã nhập để áp lại lần nữa sau bước 1.5c.
        user_values = {}
        if isinstance(bom_vars.get("extra_vars"), dict):
            user_values.update(bom_vars["extra_vars"])
        for key in list(bom_vars.keys()):
            if key not in ("extra_vars", "accessory_set", "glass_master"):
                user_values[key] = bom_vars[key]
        self._user_provided = set(user_values)
        for key, value in user_values.items():
            self.inputs[key] = value

        # ── 1.5b Capture override config từ al_bom_vars (V6 P4: A5/A7) ──
        # `_accessory_set`/`_profile_system`/`_cost_template` (Phase 1 convention
        # underscore-prefix) + `glass_master` (user var, không vào inputs).
        # Fallback `accessory_set` (convention cũ). Mọi override OPT-IN — không
        # có key → giữ nguyên 100% hành vi cũ (golden 2C/4C không đổi).
        self.accessory_set_code = None
        self.glass_master_override = None
        self.glass_master_map = {}
        self.color_master_override = None   # Q2: mã màu global cũ (backward-compat)
        self.color_master_map = {}          # Q2: {rep: mã_màu_đã_chọn} theo vị trí
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
            # Q2: màu theo VỊ TRÍ (dialog "Màu sắc" — lưu {rep: mã_màu_đã_chọn},
            # rep = default_color của dòng AL Bom Item/AL Accessory Item).
            self.color_master_override = bom_vars.get("aluminum_color")
            cm_map = bom_vars.get("color_master_map")
            if isinstance(cm_map, dict):
                self.color_master_map = cm_map
            self.profile_system_override = bom_vars.get("_profile_system")
            self.cost_template_override = bom_vars.get("_cost_template")

        # ── 1.5c (V6 P4): override profile_system — resolve lại system vars
        #     từ profile system đã chọn. `_resolve_fb_context()` ở 1.4 dùng
        #     profile MẶC ĐỊNH của Bom Set (scope AL Bom Set) → FVB không thể
        #     biết override → phải resolve LẠI TOÀN BỘ system vars theo profile
        #     override (fill_missing_only=False, ghi đè), để OFFSET_*/NC_* của
        #     profile thay thế thắng FB. Áp khi có override (OPT-IN — không có
        #     override → giữ nguyên hành vi cũ; bước 1.3 ở trên đã fill-missing
        #     nên không ghi đè giá trị FB của default profile).
        if self.profile_system_override:
            # Snapshot giá trị user TRƯỚC khi resolve lại — bước dưới ghi đè
            # toàn bộ system vars (kể cả biến user vừa sửa tay ở dialog).
            # Hợp đồng ưu tiên đầu hàm: user input thắng profile override.
            user_snapshot = {
                key: self.inputs[key]
                for key in self._user_provided if key in self.inputs
            }
            self._resolve_system_variables()
            for key, value in user_snapshot.items():
                self.inputs[key] = value

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

    def _percent_var_metadata(self):
        """F6 — đọc 1 lần var_type + var_label từ AL Variable Library.

        Trả về (tập tên biến khai `var_type == "Percent"`, map tên → nhãn).
        Lỗi đọc thư viện KHÔNG làm chết luồng — rơi về cách đoán theo hậu tố
        tên (hành vi cũ), chỉ ghi log.
        """
        try:
            rows = frappe.get_all(
                "AL Variable Library",
                fields=["var_name", "var_label", "var_type"],
            ) or []
        except Exception as exc:
            frappe.log_error(
                title="AlumGlass: không đọc được AL Variable Library (chuẩn hoá %)",
                message="Quotation Item %s — %s" % (self.quotation_item_name, exc))
            return set(), {}
        declared = set()
        labels = {}
        for row in rows:
            name = row.get("var_name")
            if not name:
                continue
            if row.get("var_type") == "Percent":
                declared.add(name)
            labels[name] = row.get("var_label") or name
        return declared, labels

    def _normalize_percent_inputs(self):
        """Chuẩn hoá biến phần trăm: phần trăm nguyên (8) → decimal (0.08).

        An toàn mixed-data: value ≤ 1 (đã là decimal, data chưa migrate) → giữ
        nguyên; value > 1 (phần trăm nguyên) → chia 100. Idempotent — chạy lại
        không nhân đôi.

        F6: biến được khai `var_type == "Percent"` trong AL Variable Library
        thì LUÔN chuẩn hoá (không phụ thuộc hậu tố tên); biến không khai giữ
        nguyên cách đoán theo hậu tố tên (tương thích ngược dữ liệu đang chạy).
        """
        declared_percent, var_labels = self._percent_var_metadata()
        # Nhãn biến dùng lại cho câu giải thích "quy tắc tính số lượng"
        # (`_qty_rule_trace`) — đọc MỘT lần ở đây, ⛔ thêm query mỗi dòng.
        self._var_labels = var_labels
        for key in list(self.inputs.keys()):
            is_percent = (key in declared_percent) or key.endswith(
                _PERCENT_VAR_SUFFIXES)
            if not is_percent:
                continue
            val = self.inputs[key]
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                continue
            if val == 1 and (key in declared_percent or key.endswith(_PERCENT_VAR_SUFFIXES)):
                # F6: giá trị đúng bằng 1 là ca mơ hồ (1% hay 100%) — ngưỡng
                # chia `> 1` giữ nguyên 1 ⇒ hiểu là 100%. Báo để người dùng
                # kiểm tra, KHÔNG đổi luồng tính.
                label = var_labels.get(key) or key
                _record_engine_warning(
                    "phan_tram_mo_ho_bang_1__warn:%s" % key,
                    "Biến '%s' đang có giá trị bằng 1 — nếu đây là biến phần trăm, hệ thống hiểu là 100%% (ý bạn là 1%% thì nhập 0.01); nếu là tỉ lệ/hệ số thì bỏ qua cảnh báo này." % label,
                )
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
        except Exception as exc:
            # D9: lỗi bị nuốt trước đây → giờ ghi log, luồng chạy KHÔNG đổi.
            frappe.log_error(
                title="AlumGlass: không đọc được AL Variable Library (user vars)",
                message="Quotation Item %s — %s" % (self.quotation_item_name, exc))
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

    def _resolve_system_variables(self, fill_missing_only=False):
        """DATA-DRIVEN: Đọc system variables từ AL Variable Library.

        Với mỗi system variable có source_doctype + source_field,
        tự động resolve giá trị. Thêm 1 system var mới = 1 record Library.

        Phase 3a (flip B1): tham số `fill_missing_only=True` — khi FB (FVB,
        bước 1.4) đã resolve xong trước, bước 1.3 CHỈ resolve cho biến CHƯA có
        trong self.inputs (guard `if var not in fb_ctx` ở caller). Biến đã
        được FVB phủ (seed v28_9/v28_11) → giữ giá trị FB, KHÔNG chạy lại
        legacy cho biến đó (cùng nguồn, cùng doc AL Bom Set → tránh làm việc
        thừa). `fill_missing_only=False` = hành vi đầy đủ cũ (dùng cho nhánh
        override 1.5c — override profile phải GHI ĐÈ toàn bộ).

        ★ REFACTOR (dọn nợ — không trùng lặp): logic resolve source_records +
        đọc AL Profile System.system_variables đã tách vào module dùng chung
        alumglass.al_bom_engine.system_variable_resolver — CÙNG module với
        api/__init__.py::_resolve_doc_values() dùng cho autocomplete/preview,
        đảm bảo "giá trị hiện trong autocomplete" luôn khớp "giá trị dùng khi
        tính BOM thật" (trước đây 2 nơi tự viết riêng, lệch tên biến).
        Trước đây source_records hardcode CỨNG 2 key ("AL Profile System",
        "AL Product Type") — nay tự dò field Link trên AL Bom Set (giống
        _resolve_variable_set_name) → thêm source_doctype mới cho System
        Variable = thêm 1 field Link trên AL Bom Set, không sửa code này.

        Phase 3a: `self._profile_child_vars` giờ capture TRỰC TIẾP từ child
        row của profile (không qua self.inputs.get) — vì trong thứ tự mới
        (FB trước, 1.3 sau) inputs[var] đã bị FB ghi đè (field value), capture
        qua inputs sẽ LƯU NHẦM giá trị field thay vì child override → 1.4b
        không ghi đè đúng. Giá trị child = đúng thứ `resolve_system_variable_
        values` ưu tiên (child > field), nên capture direct bảo toàn hành vi
        cũ bất kể thứ tự chạy.
        """
        from alumglass.al_bom_engine.system_variable_resolver import (
            fetch_system_vars, resolve_source_record_names,
            resolve_system_variable_values)

        # `fetch_system_vars` (module dùng chung) đã kèm `source_link_field` +
        # fallback an toàn khi site chưa migrate cột mới; `default_value` là
        # cột B1 cần thêm cho 2 nhánh fallback bên dưới.
        system_vars = fetch_system_vars(extra_fields=["default_value"])
        if not system_vars:
            return

        bom_set = self._get_bom_set()
        if not bom_set:
            return

        # V6 P4: `_profile_system` override (từ al_bom_vars) ưu tiên hơn
        # profile system mặc định của Bom Set. OPT-IN — không có override
        # → giữ nguyên hành vi cũ (tự dò ra đúng field profile_system trên
        # AL Bom Set, resolve đúng giá trị hiện có).
        source_records = resolve_source_record_names(
            "AL Bom Set", bom_set.name, system_vars)
        if self.profile_system_override:
            source_records["AL Profile System"] = self.profile_system_override

        # 2026-10 (fix hiệu năng #2 — đã kiểm chứng an toàn): TRƯỚC đây lọc
        # SAU khi resolve (resolve full rồi vứt kết quả biến đã có FB) — tốn
        # đúng 1 lần `frappe.db.get_value`/biến cho những biến bị vứt ngay
        # sau đó. Lọc `system_vars` TRƯỚC khi gọi `resolve_system_variable_
        # values` để không query biến đã có trong self.inputs (do FB bước
        # 1.4 đã phủ). AN TOÀN: `_profile_child_vars` (bên dưới) đọc TRỰC
        # TIẾP child table của `profile_doc` (không phụ thuộc `system_vars`
        # đã lọc), và fallback default_value (bên dưới nữa) vẫn dùng
        # `system_vars` ĐẦY ĐỦ (biến chưa lọc) — chỉ riêng lệnh query DB là
        # được thu hẹp. Không đổi kết quả, chỉ giảm số round-trip.
        # B4b: LUÔN bỏ qua biến đã có giá trị trong `self.inputs` (FB/Formula
        # Variable Binding đã phủ, hoặc lớp trước đã điền). Vì sao ĐỔI so với
        # trước: bản cũ chỉ lọc khi `fill_missing_only=True`; nhánh chạy đầy đủ
        # còn resolve LẠI rồi `self.inputs.update(...)` — ghi đè giá trị FB
        # bằng đường đọc trực tiếp, tức là làm lại đúng việc FB vừa làm và có
        # thể ra số khác. Phần còn lại của lớp này (override child
        # `AL Profile System.system_variables`) vẫn chạy như cũ và vẫn thắng.
        # `fill_missing_only` giữ trong chữ ký cho caller cũ, nay không đổi
        # hành vi.
        system_vars_to_query = [sv for sv in system_vars
                                if sv["var_name"] not in self.inputs]

        resolved_vals = (resolve_system_variable_values(source_records, system_vars_to_query)
                          if system_vars_to_query else {})
        self.inputs.update(resolved_vals)

        # Lưu lại phần override từ AL Profile System.system_variables riêng
        # (b1_gather_inputs áp lại SAU FB binding — child table phải thắng).
        # Capture TRỰC TIẾP giá trị child row (xem docstring Phase 3a) —
        # không đọc self.inputs.get(var_name) vì trong thứ tự FB-first nó có
        # thể là giá trị FB (field value), KHÔNG phải child override.
        self._profile_child_vars = {}
        ps_name = source_records.get("AL Profile System")
        if ps_name:
            try:
                profile_doc = frappe.get_cached_doc("AL Profile System", ps_name)
                for row in profile_doc.get("system_variables") or []:
                    if not row.get("is_active"):
                        continue
                    var_name = row.get("variable")
                    val = row.get("value")
                    if not var_name or val is None or str(val).strip() == "":
                        continue
                    # Parse giống resolve_system_variable_values (V6 P5):
                    # số → float, công thức/ký tự → giữ nguyên.
                    try:
                        parsed = float(val)
                    except (ValueError, TypeError):
                        parsed = val
                    # resolved_vals (chưa filter) đã có child override — nếu
                    # khác rỗng, đó là giá trị chuẩn nhất (đúng module dùng
                    # chung). parse tay chỉ là fallback khi resolved_vals
                    # không chứa (fill mode loại biến FB đã phủ).
                    self._profile_child_vars[var_name] = parsed
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

        # R6/B5: ⛔ KHÔNG còn fallback "lấy số từ AL Rule CONSTANT" khi biến hệ
        # không resolve được. Vì sao bỏ: nó tự bịa ra một con số (đo được 48 ở
        # một số biến) trong im lặng — báo giá ra tiền mà không ai biết nguồn.
        # Nay: giữ nguyên biến ở trạng thái THIẾU và ghi cảnh báo để người dùng
        # thấy đúng chỗ cần khai (Library / Formula Variable Binding / Profile).
        for sv in system_vars:
            var_name = sv["var_name"]
            # CHỈ xét biến VẮNG MẶT. Giá trị 0 là giá trị thật (offset = 0,
            # phụ phí = 0) — bản trước coi 0 là "chưa có" nên báo sai và đẩy
            # người dùng đi sửa một cấu hình đang đúng.
            if var_name in self.inputs:
                continue
            # Chỉ báo cho biến KHAI nguồn mà vẫn không ra giá trị — biến không
            # khai nguồn là biến cấu hình, có thể không dùng ở bộ này.
            if not (sv.get("source_doctype") or "").strip():
                continue
            label = sv.get("var_label") or var_name
            self.bom_engine_errors[
                f"bien_he_chua_co_nguon:{var_name}"
            ] = (
                f"Thiếu giá trị cho biến “{label}” nên giá có thể sai. "
                f"Nhờ quản trị khai nguồn dữ liệu cho biến này "
                f"(Thư viện biến → Nguồn dữ liệu) rồi tính lại."
            )

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
        except Exception as exc:
            # D9: trước đây nuốt lỗi hoàn toàn. Luồng chạy giữ nguyên (fallback
            # resolver 1.3), chỉ để lỗi không biến mất.
            frappe.log_error(
                title="AlumGlass: không import được get_live_context (B1)",
                message="Quotation Item %s — %s" % (self.quotation_item_name, exc))
            return {}
        # Scope: AL Bom Set khi có (system var FVB cần doc có link profile_system)
        scope_doctype = "Quotation Item"
        scope_docname = self.quotation_item_name
        has_bom_set = False
        try:
            bom_set = self._get_bom_set()
            if bom_set and getattr(bom_set, "name", None):
                scope_doctype = "AL Bom Set"
                scope_docname = bom_set.name
                has_bom_set = True
        except Exception as exc:
            # D9: không resolve được Bom Set → giữ scope cũ (an toàn) + ghi log.
            frappe.log_error(
                title="AlumGlass: không resolve được AL Bom Set (B1 scope)",
                message="Quotation Item %s — %s" % (self.quotation_item_name, exc))
        if not has_bom_set and not self.persist:
            # PREVIEW + KHÔNG có Bom Set: bỏ hẳn doc khỏi scope (design §2.1).
            # Lý do: doc nạp theo TÊN sẽ mang dữ liệu CŨ trong DB, trong khi
            # người dùng đang xem tham số MỚI chưa lưu ⇒ binding scope
            # "Quotation Item" (nếu ai đó thêm sau này) sẽ đọc số cũ IM LẶNG.
            # Với dữ liệu seed hiện tại (không có binding scope này) hành vi
            # tính ⛔ không đổi; dòng mới (`new-…`) vốn đã không có doc.
            scope_docname = ""
        try:
            scope_json = json.dumps({
                "current_doctype": scope_doctype,
                "current_docname": scope_docname,
            })
            ctx = get_live_context(scope_json)
        except Exception as exc:
            # D9: lỗi gọi FB get_live_context → fallback resolver cũ + ghi log.
            frappe.log_error(
                title="AlumGlass: get_live_context lỗi (B1)",
                message="Quotation Item %s — %s" % (self.quotation_item_name, exc))
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
        from alumglass.al_bom_engine.fb_config import get_named_constant
        accessory_color_group_category = get_named_constant("DEFAULT_ACCESSORY_CATEGORY", default="")
        # ← Resolve 1 LẦN trước vòng lặp (không phải per-accessory-row).
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
                # Q2: màu theo vị trí (giữ "category" gốc = "" như cũ, không
                # ảnh hưởng lọc dimension hiện có — chỉ dùng tag riêng này để
                # gom section "Phụ kiện" trong dialog "Màu sắc").
                "default_color": acc.get("default_color", ""),
                "color_group_category": accessory_color_group_category,   # trước: "PHU_KIEN"
                "supplier_location": acc.get("supplier_location", ""),
                "install_position": acc.get("install_position", ""),
                "cut_angle": "",
                "note": acc.get("note", ""),
            })

    # ══════════════════════════════════════════════════════════════════
    # B2: Pre-fetch Master Data — batch query từ DB
    # ══════════════════════════════════════════════════════════════════
    def load_snapshot_items(self):
        """Nạp `self.bom_items` từ snapshot của BOM Version đã pin.

        Tách khỏi `b2_prefetch_master_data` để đường tra giá CHO DIALOG
        (`prepare_price_context`) dùng ĐÚNG một nguồn dòng BOM với engine —
        nếu dialog đọc nguồn khác, giá ở dialog sẽ lệch giá lúc bấm "Tính giá".
        """
        if not self.bom_version or not self.bom_version.bom_set_snapshot:
            frappe.throw("BOM Version không có snapshot")

        snap = json.loads(self.bom_version.bom_set_snapshot) if isinstance(
            self.bom_version.bom_set_snapshot, str
        ) else self.bom_version.bom_set_snapshot
        self.bom_items = snap.get("items", [])

    def prepare_price_context(self):
        """Dựng ngữ cảnh tra giá GIỐNG b2 nhưng KHÔNG chạy batch query của b2.

        Dùng cho dialog (giá kính hiển thị trước khi bấm "Tính giá"): cần
        `inputs` (b1) + danh sách dòng BOM (snapshot) + danh sách category
        kính — đủ để `price_for_code()` chạy ĐÚNG thuật toán composite của
        b2/#2. ⛔ Không gọi b2 thật: b2 tra giá TOÀN BỘ mã với
        `allow_missing=False` ở nhánh mặc định, một mã khác thiếu giá sẽ
        THROW và làm hỏng cả lần xem giá của dialog.
        """
        from alumglass.al_bom_engine.glass_group_resolver import (
            fetch_glass_category_codes,
        )

        self.b0_version_pinning()
        self.b1_gather_inputs()
        self.load_snapshot_items()
        self._glass_categories = fetch_glass_category_codes(
            {it.get("category", "") for it in self.bom_items
             if it.get("category")})
        return self

    def price_for_code(self, item_code, allow_missing=True):
        """Trả `(price, price_list, matched_row)` cho 1 mã — ĐÚNG đường giá b2.

        Thứ tự y hệt b2 batch #2: FB binding trước (nếu có cấu hình), rồi
        resolver composite cũ. ⛔ Không bao giờ throw khi `allow_missing=True`
        — mã chưa có dòng Item Price trả giá 0 (dialog tự báo "chưa có giá").
        """
        if not item_code:
            return 0, self._active_price_list(), None
        prices = self._fetch_composite_prices_via_fb([item_code])
        if prices is None:
            prices = self._fetch_composite_prices(
                [item_code], price_list=self._active_price_list(),
                allow_missing=allow_missing)
        price = prices.get(item_code)
        if price is None:
            return 0, self._active_price_list(), None
        info = self._price_info.get(item_code) or {}
        return price, self._active_price_list(), (info.get("row") or None)

    def raw_price_row(self, item_code, price_list=None):
        """Dòng Item Price THÔ (chưa áp composite key) — đường dự phòng của
        dialog khi KHÔNG dựng được đủ ngữ cảnh (thiếu dimension/inputs).

        Trả `(price, row)`; `(0, None)` khi không có dòng còn hiệu lực.
        """
        price_list = price_list or self._active_price_list()
        rows = frappe.get_all(
            "Item Price",
            filters={"item_code": item_code, "price_list": price_list},
            fields=["name", "item_code", "price_list_rate", "currency",
                    "valid_from", "valid_upto"],
        )
        valid_rows = self._filter_price_rows(rows, price_list)
        if not valid_rows:
            return 0, None
        return valid_rows[0]["price_list_rate"], valid_rows[0]

    def b2_prefetch_master_data(self):
        self.load_snapshot_items()

        # ── B2 FB-max: nạp phụ kiện (VL_PK) từ AL Accessory Set ──────
        # Phải nạp TRƯỚC vòng gom codes để item_code của phụ kiện được
        # batch query weight + Item Price (KL-MZS20/KL-KHOA-01/KL-T-MJ06).
        bom_set = self._get_bom_set()
        self._load_accessories(bom_set)

        # Nhận diện "category kính" (requires_glass_master = 1) SỚM — vừa để
        # biết mã `default_glass_master` nào THẬT SỰ được dùng làm mã kính
        # (Pha 3, xem dưới), vừa tái dùng cho `glass_data` ở cuối B2 (1 query).
        from alumglass.al_bom_engine.glass_group_resolver import (
            fetch_glass_category_codes,
        )
        self._glass_categories = fetch_glass_category_codes(
            {it.get("category", "") for it in self.bom_items
             if it.get("category")})

        # ── Gom tất cả codes để batch query ──────────────────────────
        item_codes = []
        price_base_items = []
        glass_master_codes = []
        # Pha 3: mã kính MẶC ĐỊNH của dòng KÍNH — danh sách riêng để tra
        # giá/trọng lượng bằng đường cho phép thiếu (xem khối dưới).
        default_glass_codes = []
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
                if item.get("category") in self._glass_categories:
                    default_glass_codes.append(gm)
            if item.get("item_selection_mode") == "Rule" and item.get("item_rule"):
                rule_codes.append(item["item_rule"])

        # V6 P10: thêm TẤT CẢ mã kính override (per vị trí + global) vào
        # batch query weight + price. Bỏ giá trị rỗng/khoảng trắng — mã rỗng
        # lọt vào đây sẽ bị tra giá như 1 item thật và sinh cảnh báo
        # "…cho item ''…" (rác, không ai xử lý được).
        if self.glass_master_map:
            item_codes.extend(
                v for v in self.glass_master_map.values() if v and str(v).strip())
        if self.glass_master_override:
            item_codes.append(self.glass_master_override)

        # ── Pha 3 (Owner chốt "cách B"): mã kính khai MẶC ĐỊNH trên dòng KÍNH
        # (`default_glass_master`) cũng phải tra được TRỌNG LƯỢNG + ĐƠN GIÁ.
        # Trước đây các mã này chỉ vào `gm_fetch` (lấy thông số kính) — không
        # nằm trong `item_codes` ⇒ dòng kính chọn theo đường mặc định ra
        # unit_price 0 / weight 0 (đo được: 0 vs 300 000 đ của đường map).
        # Giữ riêng danh sách này để tra giá bằng ĐƯỜNG CHO PHÉP THIẾU
        # (`allow_missing=True`): mã kính KHÔNG có dòng Item Price phải ra giá
        # 0 + CẢNH BÁO, ⛔ không được THROW làm dừng cả lần tính giá.
        # Chỉ lấy mã của dòng có category KÍNH — dòng khác khai
        # `default_glass_master` thì engine ⛔ không dùng làm mã kính, tra giá
        # cho nó chỉ sinh cảnh báo rác không ai xử lý được.
        default_glass_codes = sorted({
            c for c in default_glass_codes if c and str(c).strip()})

        # ── Batch query #1: Item weights + TÊN hiển thị ──────────────
        # Nạp tên cho MỌI mã dòng có thể hiển thị: mã của chính dòng
        # (`lit.item_code` sau resolve) + `price_base_item` (mã đại diện tra
        # giá) + mã kính MẶC ĐỊNH (Pha 3 — trọng lượng của dòng kính lấy theo
        # mã này). Nhờ vậy bước 1 / câu tra giá ra TÊN vật tư thay vì mã trần —
        # vẫn đúng 1 query, ⛔ không N+1. Mã kính (AL Glass Master) lấy tên ở
        # batch #3 bên dưới nếu Item chưa có.
        weights = {}
        name_codes = list(set(item_codes + price_base_items + default_glass_codes))
        if name_codes:
            for it in frappe.get_all("Item",
                                      filters={"name": ("in", name_codes)},
                                      fields=["name", "weight_per_unit",
                                              "item_name"]):
                weights[it["name"]] = it.get("weight_per_unit", 0)
                self._item_names[it["name"]] = it.get("item_name") or ""

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
                                      # max_area_m2 (2026-09, nâng cấp #3):
                                      # fetch thêm để validate diện tích 1
                                      # tấm kính đã tính KHÔNG vượt khổ tối
                                      # đa nhà cung cấp có thể sản xuất —
                                      # xem validate ở cuối b4_calculate_bom_items.
                                      fields=["name", "total_thick_mm", "glass_type",
                                              "max_area_m2", "glass_name"]):
                glass_masters[gm["name"]] = {
                    # `total_thick_mm` = tên CHUẨN (trùng tên field nguồn trên
                    # AL Glass Master); `glass_thick` = alias cũ, giữ nguyên để
                    # rule_input_expr / công thức đã viết không vỡ.
                    "total_thick_mm": gm.get("total_thick_mm", 0),
                    "glass_thick": gm.get("total_thick_mm", 0),
                    "glass_type": gm.get("glass_type", ""),
                    "max_area_m2": gm.get("max_area_m2", 0) or 0,
                    # Nhãn người đọc — câu giải thích không phơi mã nội bộ.
                    "glass_name": gm.get("glass_name", "") or "",
                }
                # Mã kính cũng là "mã dòng" hiển thị ở bước 1 / câu tra giá
                # theo mã đại diện ⇒ nạp tên từ batch ĐÃ CÓ (không N+1).
                # KHÔNG đè tên Item thật nếu trùng mã (Item đã nạp ở batch #1).
                if gm.get("glass_name") and gm["name"] not in self._item_names:
                    self._item_names[gm["name"]] = gm["glass_name"]
        # Nhãn loại kính (glass_type là Link) — 1 query cho các mã đang dùng.
        type_codes = {v.get("glass_type") for v in glass_masters.values()
                      if v.get("glass_type")}
        type_names = {}
        if type_codes:
            try:
                for gt in frappe.get_all(
                        "AL Glass Type",
                        filters={"name": ("in", list(type_codes))},
                        fields=["name", "type_name"]):
                    type_names[gt["name"]] = gt.get("type_name") or ""
            except Exception as exc:
                frappe.logger("alumglass").error(
                    "AlumGlass: không đọc được nhãn AL Glass Type — %s" % exc)
        for gm in glass_masters.values():
            gm["glass_type_name"] = type_names.get(gm.get("glass_type"), "")

        # ── Batch #2b (Pha 3): giá cho mã kính MẶC ĐỊNH ──────────────
        # Fetch RIÊNG với `allow_missing=True` — mã kính chưa có dòng Item
        # Price trả 0 + cảnh báo `thieu_gia_item:<mã>` (cảnh báo này PHẢI nổi
        # lên: mã kính là mã CÓ được đọc giá, khác mã kính giữ chỗ bị bỏ cảnh
        # báo ở `_unused_placeholder_codes`). ⛔ Không ghi đè mã đã có giá ở
        # batch #2 (đường glass_master_map / glass_master_override).
        # Chỉ tra mã THẬT SỰ dùng được làm mã kính (có record AL Glass Master —
        # `row_literals` cũng chỉ thay `item_code` khi mã nằm trong
        # `glass_masters`); mã khai sai/đã xoá ⛔ không sinh cảnh báo rác.
        extra_glass_codes = [c for c in default_glass_codes
                             if c not in all_price_items and c in glass_masters]
        if extra_glass_codes:
            extra_prices = self._fetch_composite_prices(
                extra_glass_codes, price_list=self._active_price_list(),
                allow_missing=True)
            for code, price in extra_prices.items():
                if code in prices:
                    continue
                prices[code] = price

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
        # `self._glass_categories` đã tính Ở ĐẦU b2 (Pha 3 — dùng cho mã kính
        # mặc định) trên CÙNG tập category của `self.bom_items` ⇒ ⛔ không lặp
        # lại query ở đây.

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
            if item.get("category") in self._glass_categories:
                rep, is_real = glass_group_rep(item)
                resolved_gm = self._resolve_glass_override(rep, is_real)
            else:
                resolved_gm = None
            if resolved_gm and resolved_gm in glass_masters:
                glass_data[slug] = glass_masters[resolved_gm]
            else:
                glass_data[slug] = {
                    "total_thick_mm": 0,
                    "glass_thick": 0,       # alias cũ — giữ để không vỡ rule
                    "glass_type": "",
                    "max_area_m2": 0,
                    "glass_name": "",
                    "glass_type_name": "",
                }
        # 2026-09 (nâng cấp #3): lưu lại để B4 validate diện tích kính vs
        # max_area_m2 sau khi đã tính unit_qty (m²) của từng dòng kính.
        self._glass_data = glass_data

        # ── Batch query #5: AL Rule chọn mã (NOW AFTER glass_data) ──
        # FIX (bug thật): code cũ resolve + cache theo `rule_code` DUY NHẤT
        # (`for rule_code in set(rule_codes)`), dùng `_resolve_rule_input_for_code`
        # — hàm này duyệt `self.bom_items` và trả về input của DÒNG ĐẦU TIÊN
        # khớp `item_rule == rule_code`. Khi ≥2 dòng dùng CHUNG 1 rule_code
        # (rất phổ biến — 1 rule ngưỡng độ dày dùng cho MỌI vị trí kính, VD
        # "nep_kinh_canh" và "nep_kinh_sidelite" cùng "RULE-NEP-GLASSTHICK"
        # nhưng khác rule_input_expr vì tham chiếu 2 slug kính khác nhau) →
        # CHỈ dòng đầu tiên được resolve đúng, các dòng còn lại "mượn" luôn
        # cùng 1 item_code đã cache theo rule_code → đổi kính ở vị trí sau
        # không có tác dụng gì lên nẹp/keo của CHÍNH vị trí đó.
        # Sửa: resolve theo TỪNG DÒNG bằng rule_input_expr CỦA CHÍNH nó, cache
        # theo cặp (rule_code, rule_input) — vẫn tránh gọi resolve_item() thừa
        # khi nhiều dòng cùng rule_code VÀ cùng input (trường hợp trùng thật).
        resolved_items = {}          # (rule_code, rule_input) -> item_code
        resolved_item_names = {}
        for item in self.bom_items:
            if item.get("item_selection_mode") != "Rule" or not item.get("item_rule"):
                continue
            rule_code = item["item_rule"]
            rule_input = self._resolve_rule_input_for_item(item, glass_data)
            if rule_input is None or rule_input == "":
                # §7.6: ⛔ `continue` im lặng — dòng mất mã thì người dùng phải
                # thấy VÌ SAO và làm gì. `_describe_rule_input` đã cache cấu
                # hình quy tắc nên lời gọi lại này ⛔ thêm query.
                self._warn_missing_rule_source(item, glass_data)
                continue
            cache_key = (rule_code, rule_input)
            if cache_key not in resolved_items:
                resolved = self._resolve_dynamic_item(rule_code, rule_input)
                if resolved:
                    resolved_items[cache_key] = resolved
                    resolved_item_names[resolved] = True

        # Vết tra cứu (Phase 2): giữ map rule → mã để B4 dựng `rule_trace`
        # (biết rule KHÔNG khớp, thay vì đoán qua item_code cuối).
        self._resolved_rule_items = dict(resolved_items)

        # ── Batch query #6: Resolved Item weights + prices ─────────
        if resolved_item_names:
            for it in frappe.get_all("Item",
                                      filters={"name": ("in", list(resolved_item_names))},
                                      fields=["name", "weight_per_unit",
                                              "item_name"]):
                weights[it["name"]] = it.get("weight_per_unit", 0)
                self._item_names[it["name"]] = it.get("item_name") or ""
            # F5-6/D4 (audit 2026-10):
            #  1) Dùng ĐÚNG price_list của nhánh FB-max (nếu có binding cấu
            #     hình) thay vì luôn _default_price_list() — trước đây cùng 1
            #     dict `prices` trộn 2 bảng giá (nhánh FB 1 bảng, batch #6 bảng
            #     khác) nên cùng 1 BOM có thể ra 2 mức giá.
            #  2) KHÔNG ghi đè mã đã resolve ở batch #2 (composite/FB): batch #6
            #     chạy SAU và tra thô theo item_code (bỏ qua composite key) nên
            #     ghi đè = thay giá đã resolve đúng bằng giá thô sai dimension.
            #  3) Chỉ lấy dòng Item Price còn hiệu lực + đúng tiền tệ (F5-3).
            resolved_price_list = self._active_price_list()
            already_resolved = set(prices)
            rule_price_rows = frappe.get_all(
                "Item Price",
                filters={"item_code": ("in", list(resolved_item_names)),
                         "price_list": resolved_price_list},
                fields=["name", "item_code", "price_list_rate", "currency",
                        "valid_from", "valid_upto"],
            )
            rows_by_code = defaultdict(list)
            for ip in rule_price_rows:
                rows_by_code[ip["item_code"]].append(ip)
            for code, rows in rows_by_code.items():
                if code in already_resolved:
                    continue  # đã resolve ở batch #2 — không ghi đè
                valid_rows = self._filter_price_rows(rows, resolved_price_list)
                if not valid_rows:
                    continue
                if len(valid_rows) > 1:
                    # Nhiều dòng giá cho cùng mã mà dòng này resolve từ Dynamic
                    # Item Rule (không tra theo composite key) → không chắc dòng
                    # nào đúng, lấy dòng đầu + báo để người cấu hình bổ sung
                    # dimension cho item này.
                    _record_engine_warning(
                        "gia_nhieu_dong_rule_item:%s" % code,
                        "Mã '%s' (do quy tắc chọn mã trả về) có %d dòng Item "
                        "Price trong bảng giá '%s' — engine chưa tra theo composite "
                        "key cho dòng này, tạm lấy dòng '%s'."
                        % (code, len(valid_rows), resolved_price_list,
                           valid_rows[0].get("name", "?"))
                    )
                prices[code] = valid_rows[0]["price_list_rate"]
                # Vết tra cứu: dòng Item Price đã dùng cho item resolve từ
                # AL Rule (batch #6).
                self._record_price_info(
                    code, price_list=resolved_price_list,
                    row=valid_rows[0], price=valid_rows[0]["price_list_rate"],
                    dim_fieldnames=self._dim_fieldnames_for_category(
                        self._category_by_code().get(code, "")),
                    # Nhánh này KHÔNG khớp theo composite key — engine lấy
                    # dòng đầu tiên của mã resolve từ Rule.
                    price_match="plain_row")

        # F2/D9: gom cảnh báo phát sinh ở B2 (tra giá/rule) vào túi lỗi engine.
        # B4 MERGE tiếp (không ghi đè) nên cảnh báo B2 không bị mất.
        # Bỏ cảnh báo "thiếu giá" của mã KÍNH GIỮ CHỖ (xem
        # `_unused_placeholder_codes`) — câu đó nói về 1 mã KHÔNG tham gia tính
        # tiền nên với người dùng nó là LỖI GIẢ, mà lại nổi lên tận banner/popup
        # của dialog báo giá. GIÁ vẫn tra/giữ nguyên y như trước, ⛔ chỉ bỏ câu.
        self._drain_engine_warnings(
            skip_item_codes=self._unused_placeholder_codes(glass_masters))
        # Dòng kính GIỮ CHỖ chưa được chọn kính: câu "thiếu dòng giá" đúng về
        # hiện tượng nhưng sai về việc cần làm (người dùng phải CHỌN KÍNH,
        # không phải sửa bảng giá). Đổi câu để không đẩy họ đi sửa sai chỗ.
        self._explain_unchosen_glass(glass_masters)

        # ── Build row_literals ───────────────────────────────────────
        for item in self.bom_items:
            slug = item.get("slug", "")
            ic = item.get("item_code", "")
            pbi = item.get("price_base_item", "")
            # V6 P10: line kính dùng mã kính đã resolve theo vị trí (hoặc
            # global) — giá tra theo Item Price của mã này (có composite key
            # nếu đã cấu hình Pricing Dimension cho category kính).
            if item.get("category") in self._glass_categories:
                rep, is_real = glass_group_rep(item)
                resolved_gm = self._resolve_glass_override(rep, is_real)
                if resolved_gm and resolved_gm in glass_masters:
                    ic = resolved_gm

            gd = glass_data.get(slug, {})
            _mc = material_categories.get(item.get("category", ""), {}) or {}

            # Q2: màu đã chọn cho ĐÚNG dòng này (rep=None → dòng không tham
            # gia nhóm màu, luôn dùng màu cố định của chính item — không có gì
            # để "resolve", để trống trên kết quả).
            color_rep = color_group_rep(item)
            resolved_color = self._resolve_color_override(color_rep) if color_rep else None

            lit = {
                "weight_per_unit": weights.get(ic, 0) if ic else 0,
                "unit_price": (prices.get(pbi, 0) if pbi
                               else (prices.get(ic, 0) if ic else 0)),
                "calc_pattern": item.get("calc_pattern", ""),
                # Độ dày kính: `total_thick_mm` là tên CHUẨN (trùng field
                # nguồn), `glass_thick` là alias cũ — hai khoá CÙNG giá trị để
                # công thức/rule cũ và mới đều chạy, không phải đổi cấu hình.
                "total_thick_mm": gd.get("total_thick_mm", 0),
                "glass_thick": gd.get("glass_thick", 0),
                "glass_type": gd.get("glass_type", ""),
                "glass_type_name": gd.get("glass_type_name", ""),
                "glass_name": gd.get("glass_name", ""),
                "max_area_m2": gd.get("max_area_m2", 0) or 0,
                "item_code": ic,
                "scrap_pct": _mc.get("scrap_pct", 0),
                # V6 P8 (Phase 1e): has_weight (NHÔM/THÉP/INOX) → renderer
                # cột Trọng lượng. Rule-resolve item giữ category gốc.
                "has_weight": _mc.get("has_weight", 0),
                # Q2: hiển thị ở bảng Preview (dialog quotation.js) — thông
                # tin tĩnh khai báo trên AL Bom Item/AL Accessory Item, cộng
                # màu đã resolve theo vị trí (nếu dòng có tham gia nhóm màu).
                "color": resolved_color or "",
                "supplier_location": item.get("supplier_location", ""),
                "install_position": item.get("install_position", ""),
                "cut_angle": item.get("cut_angle", ""),
                "note": item.get("note", ""),
            }

            # AL Rule resolution (glass_thick/type đã có từ glass_data)
            if item.get("item_selection_mode") == "Rule" and item.get("item_rule"):
                rule_code = item["item_rule"]
                rule_input = self._resolve_rule_input_for_item(item, glass_data)
                resolved = resolved_items.get((rule_code, rule_input)) if rule_input not in (None, "") else None
                if resolved:
                    lit["item_code"] = resolved
                    lit["unit_price"] = prices.get(resolved, 0)
                    lit["weight_per_unit"] = weights.get(resolved, 0)

            # B2 FB-max: Accessory Item có thể ghi đè unit_price trực tiếp
            # (không cần Item Price). Row phụ kiện chỉ có slug/item_code/qty/
            # qty_formula/unit_price → ghi đè khi giá trị dương.
            if item.get("unit_price") not in (None, "", 0):
                lit["unit_price"] = item["unit_price"]

            # B3a: điền các biến theo dòng KHAI TRONG LIBRARY mà 17 literal
            # lõi ở trên chưa phủ. Chỉ điền tên CÒN THIẾU ⇒ ⛔ đổi số tiền
            # hiện có. Thiếu nguồn ⇒ ghi cảnh báo `bien_chua_co_o_buoc:*`,
            # ⛔ gán 0 (0 là giá trị thật, sẽ che lỗi cấu hình).
            lit, _missing = row_literal_loader.fill_literals(
                lit, self._row_literal_defs(), self._row_literal_sources(
                    item, gd, _mc, ic, lit, weights))
            for miss in _missing:
                # Lý do kỹ thuật (`khong_co_nguon:<DocType>`) ⛔ đưa ra người
                # dùng — dịch thành câu việc-cần-làm.
                self.bom_engine_errors.setdefault(
                    "bien_chua_co_o_buoc:%s:b2" % miss["name"],
                    "Biến “%s” chưa có giá trị khi nạp dữ liệu dòng — %s. "
                    "Nhờ quản trị kiểm tra mục “Nguồn dữ liệu” của biến "
                    "(Thư viện biến)."
                    % (miss["label"],
                       _missing_reason_text(miss.get("reason"))))

            self.row_literals[slug] = lit

        # ── Danh sách field công thức ────────────────────────────────
        # KHÔNG đọc ở đây nữa: việc chọn nguồn (danh sách riêng của bộ /
        # sổ đăng ký `AL Formula Field` / lưới dự phòng) nằm ở ĐÚNG MỘT chỗ
        # là `_resolve_formula_fieldnames()` — gọi từ `b3_build_formulas`.
        # Tách ra để cảnh báo (`formula_fields_*`) luôn đi kèm quyết định,
        # không phụ thuộc b2 có chạy hay không.

    def _row_literal_defs(self):
        """Định nghĩa biến theo dòng khai trong Library (cache 1 lượt tính).

        Đọc `AL Variable Library` với `group_label = Row Literals` (nhóm DUY
        NHẤT của biến — ô `category` cũ đã gộp 2026-11-27). Site chưa migrate
        (chưa có cột `is_active`) ⇒ vẫn đọc, coi mọi dòng là bật; lỗi DB ⇒
        trả [] (engine chạy như cũ, ⛔ làm sập tính giá).
        """
        if hasattr(self, "_row_literal_defs_cache"):
            return self._row_literal_defs_cache
        rows = []
        try:
            rows = frappe.get_all(
                "AL Variable Library",
                filters={"group_label": "Row Literals"},
                fields=["var_name", "var_label", "source_doctype",
                        "source_field", "is_active"],
                order_by="sort_order asc, var_name asc",
            ) or []
        except Exception:
            try:
                rows = frappe.get_all(
                    "AL Variable Library",
                    filters={"group_label": "Row Literals"},
                    fields=["var_name", "var_label", "source_doctype",
                            "source_field"],
                    order_by="var_name asc",
                ) or []
            except Exception:
                rows = []
        active = [row for row in rows
                  if row.get("is_active") in (None, 1, "1", True)]
        self._row_literal_defs_cache = row_literal_loader.collect_defs(active)
        return self._row_literal_defs_cache

    @staticmethod
    def _row_literal_sources(item, glass_data, material_category, item_code,
                             lit, weights):
        """Gom nguồn đã prefetch thành `{doctype: {field: value}}`.

        CHỈ dùng dữ liệu đã nạp (⛔ truy vấn DB trong vòng lặp dòng BOM).
        `Item`/`Item Price` chỉ có field engine đã tra sẵn — biến mới trỏ
        field khác sẽ được báo `thieu_field` thay vì đoán.
        """
        def _dict(value):
            if value is None:
                return {}
            if isinstance(value, dict):
                return value
            try:
                return {key: value.get(key) for key in value.keys()}
            except Exception:
                return {}

        sources = {
            "AL Bom Item": _dict(item),
            "AL Accessory Item": _dict(item),
            "AL Glass Master": _dict(glass_data),
            "AL Material Category": _dict(material_category),
            "Item": {"weight_per_unit": weights.get(item_code, 0)},
            "Item Price": {"price_list_rate": lit.get("unit_price", 0)},
        }
        return sources

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
            filters={"is_active": 1},
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

        # `bom_version` có thể vắng (test stub / dựng orchestrator rút gọn) —
        # nhánh này còn phục vụ TRA NHÃN hiển thị, ⛔ không được nổ vì thiếu
        # attribute; rỗng thì rơi xuống query live bên dưới.
        snapshot_raw = getattr(
            getattr(self, "bom_version", None),
            "pricing_dimension_snapshot", None)
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
            filters={"is_active": 1},
            # price_multiplier (2026-09, fix nâng cấp #2): trước đây KHÔNG
            # select field này ở nhánh live-query — mọi truy cập
            # m.get("price_multiplier") ở nơi khác (vd
            # _fetch_composite_prices_multiplier_chain) âm thầm luôn trả về
            # default (1.0) dù DB có giá trị khác, CHỈ khi BOM Version CHƯA
            # publish (chưa có pricing_dimension_snapshot — nhánh snapshot ở
            # trên đã có price_multiplier đúng, xem al_bom_version.py
            # _snapshot_pricing_dimensions). Thêm field vào đây để 2 nhánh
            # (snapshot / live) luôn cho cùng kết quả.
            fields=["variable_name", "pricing_dimension", "material_category",
                    "price_multiplier"])
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
    # Scope đa doctype của pricing binding (A5 — khớp §9.1 fb_source_type_contract):
    # binding global + binding khai trên Quotation Item hoặc AL Bom Item.
    _PRICING_SCOPE_DOCTYPES = ("Quotation Item", "AL Bom Item")

    def _get_pricing_bindings(self):
        """B2 FB-max: lấy Formula Variable Binding có khả năng resolve giá.

        A5 (v28_11): dùng `formula_builder.api.binding_scope` làm NGUỒN duy
        nhất của scope-filter — KHÔNG tự fork luật lọc (trước đây filter tay
        chỉ theo applies_to_doctype ∈ {"", Quotation Item, AL Bom Item}, bỏ
        qua applies_to_field → có thể lệch với preview/get_live_context).
        `get_scope_bindings_multi` = DB prefilter is_active + source_type ∈
        _PRICING_SOURCE_TYPES + applies_to_doctype ∈ ["", *scope doctypes],
        rồi python filter `binding_matches_any_doctype`.

        Row-context pricing: lúc resolve không có 1 doc/doctype gốc duy nhất
        (mỗi item_code là 1 row composite — có thể thuộc nhiều doctype), và
        caller KHÔNG ép field → áp dụng đúng §9.1: giữ nguyên bộ ứng viên,
        không bóp field ở fetch. Khi binding KHÔNG set applies_to_field → áp
        mọi field của doctype khớp (kết quả KHÔNG đổi so với hành vi cũ —
        golden-safe). Trả về list binding dict (định dạng BatchBindingResolver,
        bộ field = BINDING_FIELDS) hoặc [] → caller fallback resolver cũ.
        """
        try:
            from formula_builder.api.binding_scope import get_scope_bindings_multi
        except Exception as exc:
            # D9: fallback này là CHỦ Ý (formula_builder bản cũ chưa có
            # binding_scope) nhưng trước đây im lặng hoàn toàn → ghi log để biết
            # vì sao scope binding không đi qua đường chuẩn.
            frappe.logger("alumglass").warning(
                "AlumGlass: formula_builder không có binding_scope — dùng filter "
                "tay cũ (chỉ theo doctype). %s" % exc)
            # formula_builder chưa có binding_scope (version cũ) → fallback
            # filter tay cũ (chỉ theo doctype, không field) giữ hành vi trước A5.
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
            except Exception as exc2:
                frappe.log_error(
                    title="AlumGlass: đọc Formula Variable Binding lỗi (B2)",
                    message="Quotation Item %s — %s" % (
                        self.quotation_item_name, exc2))
                return []
        try:
            return get_scope_bindings_multi(
                doctypes=self._PRICING_SCOPE_DOCTYPES,
                source_types=list(self._PRICING_SOURCE_TYPES),
                order_by="resolve_priority asc",
            ) or []
        except Exception as exc:
            frappe.log_error(
                title="AlumGlass: get_scope_bindings_multi lỗi (B2)",
                message="Quotation Item %s — %s" % (self.quotation_item_name, exc))
            return []

    def _category_by_code(self):
        """{item_code/price_base_item: category} — dùng chung cho CẢ
        `_fetch_composite_prices_via_fb` (FB-max) VÀ `_fetch_composite_prices`
        (fallback), tránh viết lại 2 lần (V6 P10 trước đây chỉ có ở fallback
        — khiến nhánh FB-max thiếu context `category`, xem fix bên dưới).
        """
        category_by_code = {}
        for item in self.bom_items:
            cat = item.get("category", "")
            for code_field in ("item_code", "price_base_item"):
                code = item.get(code_field)
                if code and code not in category_by_code:
                    category_by_code[code] = cat
        return category_by_code

    def _color_category_by_code(self):
        """Giống `_category_by_code()` nhưng ưu tiên `color_group_category`
        (tag riêng — phụ kiện luôn = "PHU_KIEN" dù `category` gốc để trống)
        khi có. CHỈ dùng để xác định biến "màu" áp dụng cho item_code này
        (`_color_variable_for_category`) — KHÔNG ảnh hưởng category dùng cho
        các dimension khác (DO_DAY/XUAT_XU/BE_MAT...) hay weight/scrap lookup,
        vốn vẫn phải dùng `category` gốc (rỗng cho phụ kiện, như thiết kế cũ).
        """
        m = {}
        for item in self.bom_items:
            cat = item.get("color_group_category") or item.get("category", "")
            for code_field in ("item_code", "price_base_item"):
                code = item.get(code_field)
                if code and code not in m:
                    m[code] = cat
        return m

    def _compute_color_price_overrides(self):
        """Q2 (Màu sắc theo vị trí): {(item_code_hoặc_price_base_item, biến_màu):
        mã_màu_đã_resolve} cho MỌI dòng có tham gia nhóm màu (default_color
        cấu hình + đã/đang có giá trị resolve được — kể cả fallback về chính
        default_color khi user chưa đổi gì).

        GIỚI HẠN đã biết: nếu ≥2 dòng khác `default_color` (khác nhóm màu)
        nhưng dùng CHUNG `item_code`/`price_base_item`, dòng xử lý SAU sẽ ghi
        đè key này (do prices cuối cùng vẫn chỉ lưu 1 giá/item_code — xem
        `_fetch_composite_prices_via_fb`/`_fetch_composite_prices`). Muốn tách
        hẳn giá theo 2 màu khác nhau cho CÙNG 1 mã nhôm, dùng riêng
        `price_base_item` cho từng dòng (đã hỗ trợ sẵn, không cần sửa gì thêm).
        """
        from alumglass.al_bom_engine.color_group_resolver import color_group_rep
        overrides = {}
        for item in self.bom_items:
            rep = color_group_rep(item)
            if not rep:
                continue
            resolved_color = self._resolve_color_override(rep)
            if not resolved_color:
                continue
            cat = item.get("color_group_category") or item.get("category", "")
            color_var = self._color_variable_for_category(cat)
            if not color_var:
                continue
            for code_field in ("item_code", "price_base_item"):
                code = item.get(code_field)
                if code:
                    overrides[(code, color_var)] = resolved_color
        return overrides

    # ══════════════════════════════════════════════════════════════════
    # F5-3/F5-6/F2/D9 (audit 2026-10): helper dùng chung cho MỌI query Item
    # Price của engine — price list đang dùng, tiền tệ, thời hạn hiệu lực và
    # túi cảnh báo engine. Gộp 1 chỗ để nhánh FB-max / nhánh fallback / batch #6
    # không lệch nhau (thuật toán match + lọc dòng đã gộp ở
    # engine/composite_pricing.py, dùng chung với fb_handlers).
    # ══════════════════════════════════════════════════════════════════
    def _price_context(self, key):
        """Bối cảnh giá do MÁY CHỦ truyền qua `params` (`SERVER_CONTEXT_KEYS`).

        Chỉ `alumglass.api.preview_guard` đặt các khoá này (lấy từ CHÍNH doc
        báo giá đang lưu) — `alumglass.api._parse_preview_params` đã loại
        chúng khỏi tham số client gửi lên. Rỗng/None ⇒ `None` để caller rơi
        về đường đọc DB y như trước.
        """
        value = (self.params or {}).get(key)
        if value is None or value == "":
            return None
        return value

    def _default_price_list(self):
        """Price list mặc định CỦA LẦN CHẠY: ưu tiên bối cảnh máy chủ
        (`_price_list` = `Quotation.selling_price_list` đang lưu), không có
        thì đọc Selling Settings như cũ.

        Vì sao: báo giá MỚI chưa có dòng trong DB nên engine không đọc được
        `Quotation.selling_price_list` ⇒ rơi về mặc định site ⇒ chọn Item
        Price khác bảng giá người dùng đang thấy trên form.
        """
        return _default_price_list(self._price_context("_price_list"))

    def _active_price_list(self):
        """Price list dùng CHUNG cho mọi query giá trong 1 lần chạy BOM.

        Nhánh FB-max đọc price_list từ binding.source_config (set trong
        `_fetch_composite_prices_via_fb`); không có binding → bối cảnh máy
        chủ (`_price_list`) → Selling Settings (hành vi cũ). Batch #6 trước
        đây luôn dùng _default_price_list() nên trộn 2 bảng giá trong cùng
        dict `prices` (F5-6/D4).
        """
        return self._active_price_list_cache or self._default_price_list()

    def _doc_currency(self):
        """Tiền tệ của báo giá đang tính: bối cảnh máy chủ (`_currency`) →
        Quotation.currency → company → mặc định site. Trả "" khi không xác
        định được (khi đó KHÔNG lọc tiền tệ)."""
        if self._currency_cache is not None:
            return self._currency_cache
        currency = ""
        try:
            # `.get` thay vì getattr: `_qi_doc` có thể là `frappe._dict` (đường
            # preview dòng mới) — vẫn đọc được. Tiền tệ ưu tiên bối cảnh MÁY
            # CHỦ (`_currency` = `Quotation.currency` của CHÍNH doc đang lưu:
            # báo giá mới chưa có dòng trong DB nên không đọc được từ đó).
            # ⛔ Client không đặt được khoá này — xem `SERVER_CONTEXT_KEYS`.
            currency = self._price_context("_currency") or ""
            parent = self._qi_doc.get("parent") if self._qi_doc is not None else None
            if not currency and parent:
                currency = frappe.db.get_value(
                    "Quotation", parent, "currency") or ""
            if not currency:
                company = self._price_context("_company") or ""
                if not company and parent:
                    company = frappe.db.get_value(
                        "Quotation", parent, "company") or ""
                if company:
                    currency = frappe.db.get_value(
                        "Company", company, "default_currency") or ""
            if not currency:
                currency = frappe.db.get_single_value(
                    "Global Defaults", "default_currency") or ""
        except Exception as exc:
            # D9: thiếu thông tin tiền tệ chỉ làm mất bộ lọc tiền tệ (KHÔNG chết
            # BOM) nhưng phải để lại dấu vết thay vì nuốt im lặng.
            frappe.logger("alumglass").error(
                "AlumGlass: không resolve được tiền tệ báo giá — %s" % exc)
            currency = ""
        self._currency_cache = currency
        return currency

    def _price_currency(self, price_list):
        """Tiền tệ dùng để LỌC Item Price — None = không lọc (hành vi cũ).

        Xem composite_pricing.currency_filter_value: CHỈ lọc khi tiền tệ của
        Price List khớp tiền tệ báo giá. Cache theo price_list (1 lần chạy BOM
        thường chỉ dùng 1 bảng giá).
        """
        if price_list in self._currency_filter_cache:
            return self._currency_filter_cache[price_list]
        from alumglass.engine.composite_pricing import currency_filter_value
        currency = currency_filter_value(price_list, self._doc_currency())
        self._currency_filter_cache[price_list] = currency
        return currency

    def _filter_price_rows(self, rows, price_list=None):
        """Lọc dòng Item Price dùng được (còn hiệu lực + đúng tiền tệ) — F5-3.

        Trả [] khi không còn dòng nào: caller PHẢI báo thiếu giá (F5-7) thay vì
        âm thầm dùng dòng đã hết hạn. Dùng chung composite_pricing.filter_price_rows
        với fb_handlers để 2 nhánh luôn lọc giống nhau.
        """
        from alumglass.engine.composite_pricing import filter_price_rows
        currency = self._price_currency(price_list) if price_list else None
        return filter_price_rows(rows, currency=currency)

    def _drain_engine_warnings(self, bag=None, skip_item_codes=None):
        """Hút cảnh báo từ túi dùng chung về túi lỗi engine (F2/D9).

        Túi dùng chung (frappe.local) cần thiết vì fb_handlers chạy trong cùng
        tiến trình nhưng KHÔNG có tham chiếu tới orchestrator.

        `skip_item_codes`: mã KÍNH GIỮ CHỖ không dòng nào đọc giá (xem
        `_unused_placeholder_codes`) — bỏ cảnh báo "thiếu giá" của chúng. Cảnh
        báo các mã KHÁC giữ nguyên.
        """
        try:
            from alumglass.engine.composite_pricing import drain_engine_warnings
            warnings = drain_engine_warnings()
        except Exception:
            return
        if warnings and skip_item_codes:
            prefix = "thieu_gia_item:"
            warnings = {
                key: msg for key, msg in warnings.items()
                if not (key.startswith(prefix)
                        and key[len(prefix):] in skip_item_codes)
            }
        if warnings:
            (bag if bag is not None else self.bom_engine_errors).update(warnings)

    # ══════════════════════════════════════════════════════════════════
    # Câu người đọc cho lỗi công thức
    # ══════════════════════════════════════════════════════════════════
    def _variable_label(self, var_name):
        """`(biến có trong Thư viện biến?, nhãn người đọc)` — cache 1 lượt tính.

        Phân biệt 2 ca để câu báo chỉ đúng việc cần làm: biến CÓ trong thư
        viện nhưng thiếu giá trị (khai giá trị) ≠ biến KHÔNG có trong thư viện
        (phải khai biến trước).
        """
        if var_name in self._var_label_cache:
            return self._var_label_cache[var_name]
        known, label = False, ""
        try:
            row = frappe.db.get_value(
                "AL Variable Library", {"var_name": var_name},
                ["name", "var_label"], as_dict=True) or {}
            known = bool(row)
            label = (row.get("var_label") or "").strip()
        except Exception:
            # Không đọc được thư viện KHÔNG phải lý do làm hỏng lượt tính —
            # câu báo vẫn dùng mã biến, chỉ kém thân thiện hơn.
            known, label = False, ""
        self._var_label_cache[var_name] = (known, label)
        return self._var_label_cache[var_name]

    def _readable_formula_errors(self, errors):
        """Đổi lỗi eval thô (Python) thành câu người đọc được.

        Chỉ đổi đúng ca đã gặp thật: `name '<biến>' is not defined` — công
        thức đọc biến chưa có giá trị ⇒ nêu NHÃN biến + việc cần làm. Lỗi
        khác giữ nguyên văn để không che mất thông tin chẩn đoán. Nguyên văn
        luôn được ghi vào log phía máy chủ để support đối chiếu.
        """
        out = humanize_errors(errors, self._variable_label)
        for key, message in (errors or {}).items():
            if out.get(key) == message:
                continue
            try:
                frappe.logger("alumglass").warning(
                    "Công thức %s lỗi (nguyên văn): %s" % (key, message))
            except Exception:
                pass
        return out

    def _explain_unchosen_glass(self, glass_masters):
        """Đổi câu "thiếu dòng giá" của dòng kính CHƯA CHỌN KÍNH cho đúng việc.

        Điều kiện nhận diện (hẹp, ⛔ đoán): dòng thuộc nhóm kính, `item_code`
        LÀ một mã kính trong danh mục (tức đang dùng mã giữ chỗ), và ⛔ có
        kính nào được chọn cho vị trí đó.
        """
        for item in self.bom_items or []:
            code = item.get("item_code") or ""
            if not code or code not in glass_masters:
                continue
            if item.get("category") not in self._glass_categories:
                continue
            key = "thieu_gia_item:%s" % code
            if key not in self.bom_engine_errors:
                continue
            try:
                rep, is_real = glass_group_rep(item)
                chosen = self._resolve_glass_override(rep, is_real)
            except Exception:
                continue
            if chosen:
                continue
            label = self._item_names.get(code) or code
            self.bom_engine_errors[key] = unchosen_glass_message(label)

    def _unused_placeholder_codes(self, glass_masters):
        """Mã gốc của dòng KÍNH mà ⛔ KHÔNG dòng nào đọc giá nữa — mã GIỮ CHỖ.

        AL Bom Set thường khai 1 mã kính GIỮ CHỖ chung cho các vị trí kính (VD
        KINH-01..KINH-04 theo vị trí) — mã đại diện, thường ⛔ không có dòng Item
        Price nào, chỉ để giữ chỗ cho tới lúc lập báo giá (dialog "Kính theo vị
        trí" thay bằng kính thật của báo giá đó).

        Dòng kính ĐÃ được chọn kính (`row_literals` thay `item_code` bằng MÃ
        KÍNH khi mã đó có trong `glass_masters`) ⇒ `item_code` gốc của dòng đó
        ⛔ không còn được đọc để tra giá/khối lượng. Nhưng batch #2 vẫn tra giá
        cho nó (vì nó nằm trong `item_codes`) → sinh cảnh báo
        "Không tìm được dòng Item Price … cho 'KINH-01' …" cho một mã KHÔNG
        tham gia tính tiền → dialog báo giá hiện banner/popup LỖI ĐỎ dù người
        dùng đã chọn kính cho MỌI vị trí.

        ⛔ Chỉ trả về mã KHÔNG ai đọc giá — giữ nguyên cảnh báo cho:
          - dòng kính CHƯA chọn được kính (giá thật sự tra theo mã gốc đó);
          - mã còn được dòng KHÁC đọc (VD vừa là kính giữ chỗ, vừa là
            `price_base_item` của dòng nhôm);
          - `price_base_item` của dòng kính — `row_literals` vẫn ưu tiên tra
            theo nó nếu có khai (danh mục Kính ⛔ không bắt buộc khai).
        """
        used = set()
        unused = set()
        for item in self.bom_items:
            ic = item.get("item_code") or ""
            pbi = item.get("price_base_item") or ""
            if pbi:
                # row_literals ưu tiên tra giá theo price_base_item → mã này CÒN dùng
                used.add(pbi)
            if ic and item.get("category") in self._glass_categories:
                rep, is_real = glass_group_rep(item)
                resolved_gm = self._resolve_glass_override(rep, is_real)
                # CÙNG điều kiện với `row_literals` — mã kính phải có trong
                # glass_masters thì việc thay thế mới thật sự xảy ra.
                if resolved_gm and resolved_gm in glass_masters:
                    # MÃ KÍNH này LÀ mã được đọc (giá/khối lượng của dòng) ⇒
                    # cảnh báo thiếu giá của nó là THẬT, phải giữ.
                    used.add(resolved_gm)
                    unused.add(ic)
                    continue
            if ic:
                used.add(ic)
        return unused - used

    def _fetch_composite_prices_via_fb(self, item_codes):
        """B2 FB-max: resolve composite price — batch 1 lần cho TẤT CẢ item_codes.

        FIX N+1 (2026-09): bản cũ gọi resolve_all_bindings_batch theo TỪNG
        item_code (M lần) → 2×M query. resolve_all_bindings_batch không có API
        multi-row, nên sửa tại đây: đọc CONFIG (price_list, pricing_mode) từ
        binding đúng 1 lần, rồi tái dùng _fetch_composite_prices(allow_missing=True)
        — đã cache mapping ở self._dim_mapping_raw_cache, cùng thuật toán
        best_partial_match với fb_handlers.

        allow_missing=True bắt buộc — 2 nhánh khác hành vi no-match (fb_handlers
        trả 0, fallback mặc định throw); không xử lý sẽ đổi hành vi ngầm.

        Chỉ tối ưu N+1 cho ĐÚNG 1 binding chủ (source_type=aluminum_price_
        composite). 0 hoặc >1 binding loại này active cùng lúc → rơi về nhánh
        chậm _fetch_composite_prices_via_fb_slow (an toàn hơn đoán config nào ưu tiên).
        """
        bindings = self._get_pricing_bindings()
        if not bindings:
            return None

        fast_path_bindings = [
            b for b in bindings if b.get("source_type") == "aluminum_price_composite"
        ]
        other_bindings = [b for b in bindings if b not in fast_path_bindings]
        if len(fast_path_bindings) != 1 or other_bindings:
            return self._fetch_composite_prices_via_fb_slow(bindings, item_codes)

        import json
        cfg = json.loads(fast_path_bindings[0].get("source_config") or "{}")
        pricing_mode = cfg.get("pricing_mode", "exact_match")
        price_list = cfg.get("price_list") or self._default_price_list()
        # F5-6/D4: nhớ price_list đang dùng để batch #6 (giá item resolve từ
        # AL Rule) KHÔNG trộn bảng giá khác vào cùng dict `prices`.
        self._active_price_list_cache = price_list

        if pricing_mode == "exact_match":
            return self._fetch_composite_prices(
                item_codes, price_list=price_list, allow_missing=True)

        if pricing_mode == "multiplier_chain":
            return self._fetch_composite_prices_multiplier_chain(item_codes, price_list=price_list)

        return None

    def _fetch_composite_prices_via_fb_slow(self, bindings, item_codes):
        """Đường cũ (per-item, có N+1) — CHỈ dùng cho case lạ (0/nhiều hơn 1
        binding aluminum_price_composite active, hoặc có binding khác xen vào).
        Giữ nguyên logic gốc, ưu tiên đúng behavior hơn tối ưu.
        """
        from formula_builder.api.batch_binding_resolver import resolve_all_bindings_batch

        category_by_code = self._category_by_code()
        color_category_by_code = self._color_category_by_code()
        color_overrides = self._compute_color_price_overrides()
        prices = {}
        for item_code in item_codes:
            row_ctx = dict(self.inputs)
            row_ctx["item_code"] = item_code
            row_ctx["price_base_item"] = item_code
            row_ctx["category"] = category_by_code.get(item_code, "")
            color_var = self._color_variable_for_category(
                color_category_by_code.get(item_code, ""))
            if color_var:
                override_val = color_overrides.get((item_code, color_var))
                if override_val:
                    row_ctx[color_var] = override_val
            row_ctx["row"] = {
                "item_code": item_code,
                "price_base_item": item_code,
                "category": category_by_code.get(item_code, ""),
            }
            try:
                resolved = resolve_all_bindings_batch(
                    bindings, doc=self._qi_doc, pre_resolved=row_ctx)
            except Exception as exc:
                # D9: lỗi bị nuốt trước đây (item này mất giá trong im lặng) —
                # luồng chạy giữ nguyên (continue), chỉ ghi log để không mất dấu.
                frappe.log_error(
                    title="AlumGlass: resolve giá qua FB binding lỗi (B2)",
                    message="item_code %s — %s" % (item_code, exc))
                continue
            for _var_name, val in resolved.items():
                if isinstance(val, (int, float)) and val:
                    prices[item_code] = float(val)
                    # Vết tra cứu: đường binding tự do không trả dòng Item
                    # Price ⇒ chỉ ghi được giá, `row` để rỗng (API sẽ nói
                    # "không lưu được dòng giá khớp" thay vì bịa).
                    self._record_price_info(
                        item_code, price_list="", row=None,
                        price=float(val),
                        # Binding tự do trả giá, KHÔNG có dòng Item Price ⇒
                        # không có dimension nào tham gia chọn giá.
                        price_match="plain_row")
                    break
        return prices if prices else None

    def _fetch_composite_prices_multiplier_chain(self, item_codes, price_list):
        """multiplier_chain mode — batch 1 query base price cho TẤT CẢ item_codes,
        frappe.get_cached_value cho multiplier (đã request-cache sẵn trong Frappe).

        F5-3/F5-4 (audit 2026-10): query base price trước đây chỉ lọc item_code
        + price_list và lấy dòng ĐẦU TIÊN (`setdefault`) — vừa lấy nhầm dòng giá
        đã hết hạn/khác tiền tệ, vừa có thể lấy dòng giá composite (đã gồm phụ
        phí màu/độ dày) làm giá GỐC rồi nhân multiplier thêm lần nữa.
        """
        if not item_codes:
            return {}

        from alumglass.engine.composite_pricing import pick_base_price

        category_by_code = self._category_by_code()
        # Cần custom_fieldname của các pricing dimension để nhận diện dòng giá
        # GỐC (dòng "trần" — không set dimension nào).
        all_fieldnames = set()
        for code in item_codes:
            all_fieldnames |= set(
                self._dim_fieldnames_for_category(category_by_code.get(code, "")).values())

        base_rows = frappe.get_all(
            "Item Price",
            filters={"item_code": ("in", item_codes), "price_list": price_list},
            fields=["name", "item_code", "price_list_rate", "currency",
                    "valid_from", "valid_upto"] + list(all_fieldnames),
        )
        rows_by_item = defaultdict(list)
        for r in base_rows:
            rows_by_item[r["item_code"]].append(r)

        base_price_by_item = {}
        base_row_by_item = {}
        for item_code in item_codes:
            dim_fieldnames = self._dim_fieldnames_for_category(
                category_by_code.get(item_code, ""))
            rows = self._filter_price_rows(
                rows_by_item.get(item_code, []), price_list)
            base_price, is_base_row = pick_base_price(rows, dim_fieldnames)
            # Dòng giá GỐC đã dùng (cho vết tra cứu) — cùng quy tắc chọn với
            # `pick_base_price`: dòng "trần" nếu có, không thì dòng đầu.
            base_row = None
            if rows:
                if is_base_row:
                    base_row = next(
                        (r for r in rows
                         if all(not r.get(fn)
                                for fn in (dim_fieldnames or {}).values())),
                        rows[0])
                else:
                    base_row = rows[0]
            base_row_by_item[item_code] = base_row
            if rows and not is_base_row:
                # Không có dòng "trần" → đành lấy dòng đầu (không trả 0) nhưng
                # phải báo: giá gốc đang lẫn phụ phí composite.
                _record_engine_warning(
                    "gia_goc_thieu_dong_tran:%s" % item_code,
                    "Item '%s' không có dòng Item Price nào KHÔNG gắn pricing "
                    "dimension trong bảng giá '%s' — multiplier_chain tạm lấy "
                    "dòng '%s' làm giá gốc, giá có thể đã gồm phụ phí dimension."
                    % (item_code, price_list, rows[0].get("name", "?"))
                )
            base_price_by_item[item_code] = base_price

        mappings, dims_raw = self._get_dim_mappings_raw()
        dim_codes = list({m["pricing_dimension"] for m in mappings})
        dim_link_doctype = {}
        if dim_codes:
            for d in frappe.get_all(
                "AL Pricing Dimension",
                filters={"name": ("in", dim_codes)},
                fields=["name", "link_doctype"],
            ):
                dim_link_doctype[d["name"]] = d.get("link_doctype")

        prices = {}
        for item_code in item_codes:
            base_price = base_price_by_item.get(item_code)
            if not base_price:
                # F5-7: thiếu giá gốc KHÔNG trả 0 im lặng — ghi cảnh báo engine.
                prices[item_code] = 0
                self._record_price_info(
                    item_code, price_list=price_list,
                    row=base_row_by_item.get(item_code), price=0,
                    dim_fieldnames=dim_fieldnames,
                    price_match="none")
                _record_engine_warning(
                    "thieu_gia_goc:%s" % item_code,
                    "Không tìm được dòng Item Price còn hiệu lực làm giá GỐC cho "
                    "'%s' trong bảng giá '%s' — tạm tính giá 0."
                    % (item_code, price_list)
                )
                continue
            category = category_by_code.get(item_code, "")
            total_multiplier = 1.0
            for m in mappings:
                if category and m.get("material_category") != category:
                    continue
                var_value = self.inputs.get(m["variable_name"])
                if var_value is None or var_value == "":
                    continue
                map_mult = m.get("price_multiplier", 1.0) or 1.0
                link_doctype = dim_link_doctype.get(m["pricing_dimension"])
                # F5-4: PHÂN BIỆT "multiplier vắng mặt" với "multiplier = 1.0".
                # Trước đây `... or 1.0` rồi `linked_mult != 1.0` gộp cả 3 giá
                # trị vắng mặt / 0 / 1.0 làm một → màu KHÔNG phụ phí (khai đúng
                # 1.0) bị thay bằng multiplier của mapping (sai giá).
                linked_mult = None
                if link_doctype and var_value:
                    try:
                        linked_raw = frappe.get_cached_value(
                            link_doctype, var_value, "price_multiplier")
                        # 0/rỗng = chưa khai (không dùng để nhân ra giá 0)
                        linked_mult = float(linked_raw) if linked_raw else None
                    except Exception as exc:
                        # D9: nuốt lỗi im lặng trước đây → ghi log, luồng không đổi
                        frappe.logger("alumglass").error(
                            "AlumGlass: không đọc được price_multiplier của %s "
                            "'%s' — %s" % (link_doctype, var_value, exc))
                effective_mult = (
                    linked_mult if linked_mult is not None else map_mult)
                total_multiplier *= effective_mult
            prices[item_code] = base_price * total_multiplier
            self._record_price_info(
                item_code, price_list=price_list,
                row=base_row_by_item.get(item_code),
                price=base_price * total_multiplier,
                base_price=base_price, multiplier=total_multiplier,
                dim_fieldnames=dim_fieldnames,
                price_match="multiplier_chain")
        return prices

    def _fetch_composite_prices(self, item_codes, price_list=None, allow_missing=False):
        """Tra Item Price theo composite key, trả về {item_code: price_list_rate}.

        ★ LƯỚI AN TOÀN — chỉ chạy khi _fetch_composite_prices_via_fb trả None.
        Caller mặc định (allow_missing=False, price_list=None): 100% golden cũ.

        Args (MỚI): price_list — ghi đè _default_price_list(), cho phép FB-max
        truyền price_list từ binding.source_config. allow_missing — True: item
        không khớp giá (kể cả 0 dòng Item Price) trả 0 thay vì throw, khớp đúng
        hành vi fb_handlers.aluminum_price_composite.
        """
        if not item_codes:
            return {}
        price_list = price_list or self._default_price_list()

        category_by_code = self._category_by_code()
        color_category_by_code = self._color_category_by_code()
        color_overrides = self._compute_color_price_overrides()

        all_fieldnames = set()
        for code in item_codes:
            fns = self._dim_fieldnames_for_category(category_by_code.get(code, ""))
            all_fieldnames |= set(fns.values())
        price_fields = ["name", "item_code", "price_list_rate", "currency",
                        "valid_from", "valid_upto"] + list(all_fieldnames)

        rows_by_item = defaultdict(list)
        for ip in frappe.get_all(
            "Item Price",
            filters={"item_code": ("in", item_codes), "price_list": price_list},
            fields=price_fields,
        ):
            rows_by_item[ip["item_code"]].append(ip)

        prices = {}
        # SỬA: loop TOÀN BỘ item_codes yêu cầu, không chỉ rows_by_item.keys() —
        # item 0 dòng Item Price trước đây bị THIẾU khỏi kết quả (không 0, không throw).
        for item_code in item_codes:
            # F5-3: chỉ giữ dòng còn hiệu lực (valid_from/valid_upto, chấp nhận
            # NULL) + đúng tiền tệ — trước đây lấy cả dòng đã hết hạn/khác tiền tệ.
            rows = self._filter_price_rows(
                rows_by_item.get(item_code, []), price_list)
            dim_fieldnames = self._dim_fieldnames_for_category(
                category_by_code.get(item_code, ""))
            row_inputs = dict(self.inputs)
            color_var = self._color_variable_for_category(
                color_category_by_code.get(item_code, ""))
            if color_var:
                override_val = color_overrides.get((item_code, color_var))
                if override_val:
                    row_inputs[color_var] = override_val
            price, matched_row = self._match_composite_price(
                item_code, rows, dim_fieldnames, row_inputs,
                allow_missing=allow_missing, return_row=True)
            prices[item_code] = price
            # Vết tra cứu: `name` của dòng Item Price đã dùng (additive).
            # `price_match` phân loại ĐÚNG nhánh vừa chạy: khớp đủ tiêu chí
            # dimension ⇒ composite; rơi về dòng giá "trần" ⇒ base_row.
            match = self._classify_price_match(
                rows, matched_row, dim_fieldnames, row_inputs)
            self._record_price_info(
                item_code, price_list=price_list, row=matched_row,
                price=price, dim_fieldnames=dim_fieldnames,
                price_match=match,
                # `matched` chỉ đúng nghĩa "được dùng để khớp" ở nhánh
                # composite — các nhánh khác dimension chỉ là thuộc tính của
                # dòng giá ⇒ ⛔ không đánh dấu khớp.
                match_inputs=row_inputs if match == "composite" else None)
        return prices

    def _record_price_info(self, item_code, price_list=None, row=None,
                           price=None, base_price=None, multiplier=None,
                           dim_fieldnames=None, price_match="",
                           match_inputs=None):
        """Lưu vết tra giá của 1 mã (additive — KHÔNG tham gia tính toán).

        Giữ NGUYÊN dict dòng Item Price + map dimension để biên API/engine dựng
        nhãn nghiệp vụ (bảng giá, màu, độ dày…). `row_name` vẫn lưu riêng cho
        dữ liệu kỹ thuật (support), ⛔ không dùng làm chuỗi hiển thị.

        `price_match` = NHÁNH TRA GIÁ THẬT đã chạy (`composite` / `base_row` /
        `multiplier_chain` / `plain_row` / `none`); `match_inputs` = composite
        key lúc khớp, để đánh dấu từng dimension `matched` (có dùng để khớp
        hay chỉ là thuộc tính của dòng giá). Cả hai chỉ phục vụ giải thích.
        """
        if not item_code:
            return
        raw_row = dict(row) if isinstance(row, dict) else {}
        row_name = raw_row.get("name") or ""
        self._price_rows[item_code] = row_name
        self._price_info[item_code] = {
            "price_list": price_list or "",
            "row": raw_row,
            "row_name": row_name,
            "dim_fieldnames": dict(dim_fieldnames or {}),
            "price": price,
            "base_price": base_price,
            "multiplier": multiplier,
            "price_match": price_match or "",
            "match_inputs": dict(match_inputs or {}),
        }

    def _match_composite_price(self, item_code, rows, dim_fieldnames,
                               inputs=None, allow_missing=False,
                               return_row=False):
        """Chọn dòng Item Price khớp nhất — thuật toán thật ở engine/composite_
        pricing.best_partial_match (dùng chung với fb_handlers.aluminum_price_composite).
        allow_missing=True: trả 0 thay vì throw khi không khớp. Mặc định False =
        hành vi golden cũ.
        return_row=True: trả cặp `(price, row)` — `row` là dict Item Price đã
        chọn (None khi không khớp) để ghi vết tra cứu. Mặc định False giữ
        nguyên hợp đồng cũ (chỉ trả price).
        """
        from alumglass.engine.composite_pricing import (
            best_partial_match, best_partial_match_row)

        row_inputs = inputs if inputs is not None else self.inputs
        if return_row:
            row = best_partial_match_row(rows, dim_fieldnames, row_inputs)
            if row is not None:
                return row["price_list_rate"], row
            if allow_missing:
                # F5-7: KHÔNG trả 0 im lặng — ghi cảnh báo vào túi lỗi engine
                # (đi ra `al_bom_result["errors"]`), vẫn trả 0 để cả BOM
                # không chết.
                _record_engine_warning(
                    "thieu_gia_item:%s" % item_code,
                    "Không tìm được dòng Item Price còn hiệu lực khớp composite "
                    "key cho '%s' — tạm tính giá 0. Kiểm tra bảng giá hoặc thêm "
                    "dòng giá mặc định không gắn dimension." % item_code,
                )
                return 0, None
            self._throw_missing_price(item_code)

        price = best_partial_match(rows, dim_fieldnames, row_inputs)
        if price is not None:
            return price
        if allow_missing:
            # F5-7: KHÔNG trả 0 im lặng — ghi cảnh báo vào túi lỗi engine (đi ra
            # `al_bom_result["errors"]`), vẫn trả 0 để cả BOM không chết.
            _record_engine_warning(
                "thieu_gia_item:%s" % item_code,
                "Không tìm được dòng Item Price còn hiệu lực khớp composite key "
                "cho '%s' — tạm tính giá 0. Kiểm tra bảng giá hoặc thêm dòng giá "
                "mặc định không gắn dimension." % item_code,
            )
            return 0
        self._throw_missing_price(item_code)

    def _classify_price_match(self, rows, row, dim_fieldnames, inputs):
        """Phân loại NHÁNH tra giá đã chạy cho 1 mã (ghi vào vết giải thích).

        - `none`       — không chọn được dòng giá nào.
        - `plain_row`  — chỉ có 1 dòng giá (hoặc category không khai dimension)
                         ⇒ engine lấy nguyên dòng, ⛔ không khớp theo tiêu chí.
        - `composite`  — dòng được chọn có ≥1 tiêu chí dimension TRÙNG input
                         (chính là các tiêu chí đã dùng để khớp).
        - `base_row`   — nhiều dòng nhưng dòng được chọn KHÔNG gắn tiêu chí nào
                         (dòng giá gốc), tức không khớp đủ tiêu chí.
        """
        if row is None:
            return "none"
        if not dim_fieldnames or len(rows or []) <= 1:
            return "plain_row"
        for var_name, fieldname in dim_fieldnames.items():
            row_val = row.get(fieldname)
            if row_val and str(row_val) == str((inputs or {}).get(var_name, "")):
                return "composite"
        return "base_row"

    def _price_match_sentence(self, info):
        """Câu nói ĐÚNG cách engine chọn ra dòng giá — ⛔ không câu chung.

        `multiplier_chain` tự có câu riêng (giá gốc × hệ số) và engine dừng
        sớm ở nhánh đó; ở đây chỉ xử lý 2 nhánh còn lại.
        """
        match = (info or {}).get("price_match") or ""
        if match == "composite":
            labels = [e["label"] for e in self._matched_dim_entries(info)
                      if e["matched"]]
            if not labels:
                # ⛔ Không có tiêu chí nào khớp được thì ⛔ không bịa câu.
                return ""
            return "khớp theo %s" % ", ".join(labels)
        if match == "base_row":
            return ("không có dòng giá khớp đủ tiêu chí — dùng dòng giá gốc "
                    "của mã")
        return ""

    def _code_source(self, item):
        """Mã dùng để tra giá đến từ đâu — ĐÚNG thứ tự `_price_code_for_trace`."""
        if item.get("unit_price") not in (None, "", 0):
            return "manual_price"
        if item.get("item_selection_mode") == "Rule" and item.get("item_rule"):
            return "rule"
        if item.get("price_base_item"):
            return "price_base_item"
        return "item_code"

    def _build_lookup_facts(self, item, price_code, price_base_item,
                            glass_used):
        """`lookup_facts` — SỰ THẬT tra cứu của 1 dòng (additive).

        `explain_bom_line` dựng câu giải thích từ đây thay vì khuôn 6 bước:
        bước nào không xảy ra thì ⛔ không dựng, và nội dung là việc engine
        ĐÃ làm cho đúng dòng này.
        """
        code_source = self._code_source(item)
        info = {}
        if code_source != "manual_price":
            info = getattr(self, "_price_info", {}).get(price_code) or {}
        return {
            "code_source": code_source,
            "price_match": info.get("price_match") or "",
            "match_dims": self._matched_dim_entries(info) if info else [],
            "glass_used": bool(glass_used),
            "price_base_item": price_base_item or "",
            "price_base_item_name": (
                self._item_names.get(price_base_item) or ""),
        }

    def _throw_missing_price(self, item_code):
        """Lỗi thiếu giá ở đường KHÔNG allow_missing (giữ nguyên câu cũ)."""
        frappe.throw(
            f"Không tìm được Item Price khớp cho '{item_code}' với composite "
            f"key hiện tại. Kiểm tra lại bảng giá (Item Price) hoặc thêm 1 "
            f"dòng giá mặc định không gắn dimension nào."
        )

    def _resolve_glass_override(self, rep, is_real_master=True):
        """Trả về mã kính THỰC TẾ dùng để tra giá/thông số cho 1 dòng KINH.

        `rep`/`is_real_master` PHẢI tính từ `glass_group_rep(item)` (dùng
        CHUNG công thức với api.get_variable_set_for_bom) — đảm bảo khớp
        đúng key mà dialog "Kính theo vị trí" đã lưu vào `glass_master_map`.

        Ưu tiên:
          1. glass_master_map[rep] — user đã chọn kính cho đúng vị trí này
             trong dialog (hỗ trợ N kính khác nhau/BOM, kể cả khi BOM Set
             KHÔNG cấu hình default_glass_master nào).
          2. glass_master_override — mã global cũ (1 kính cho toàn BOM,
             backward-compat khi dialog/BOM chưa có glass_groups).
          3. rep — CHỈ dùng làm fallback khi rep là mã Glass Master THẬT
             (is_real_master=True, tức default_glass_master đã cấu hình
             sẵn trên AL Bom Set). Khi rep chỉ là khoá tổng hợp theo slug
             (is_real_master=False) mà user CHƯA chọn kính cho vị trí này
             → trả None (an toàn) thay vì coi khoá đó là 1 item_code.
        """
        if not rep:
            return None
        if self.glass_master_map:
            mapped = self.glass_master_map.get(rep)
            if mapped:
                return mapped
        if self.glass_master_override:
            return self.glass_master_override
        return rep if is_real_master else None

    # ══════════════════════════════════════════════════════════════════
    # Q2: Màu sắc theo vị trí — cùng mô hình với glass_group_rep/
    # _resolve_glass_override, nhưng ĐƠN GIẢN hơn: `default_color` trên
    # AL Bom Item/AL Accessory Item PHẢI trỏ tới 1 bản ghi AL Color Standard
    # ĐÃ tích "Mau dai dien" (lọc qua get_query ở form) — khác kính, rep ở
    # đây LUÔN là 1 mã màu THẬT (không có khoá tổng hợp theo slug), nên có
    # thể fallback thẳng về rep khi user chưa chọn override (an toàn, vì rep
    # chính là màu "đại diện/mặc định" admin đã cấu hình sẵn cho dòng đó).
    # Dòng KHÔNG cấu hình default_color (rep rỗng) = luôn dùng 1 màu cố định
    # (không tham gia nhóm, không có selector, không bị override ở đây).
    # ══════════════════════════════════════════════════════════════════
    def _resolve_color_override(self, rep):
        """Trả về mã màu (AL Color Standard) THỰC TẾ dùng để tra giá cho 1
        dòng có tham gia nhóm màu (rep = default_color của dòng đó, rỗng
        nghĩa là dòng không tham gia — caller phải tự bỏ qua trước khi gọi).
        """
        if not rep:
            return None
        if self.color_master_map:
            mapped = self.color_master_map.get(rep)
            if mapped:
                return mapped
        if self.color_master_override:
            return self.color_master_override
        return rep

    def _color_variable_for_category(self, category):
        """Tên biến (variable_name) đại diện cho dimension "màu sắc" của ĐÚNG
        material_category — data-driven qua AL Variable Dimension Mapping +
        AL Pricing Dimension.represents_color (KHÔNG còn hardcode "MAU_SAC")."""
        if not category:
            return None
        mappings, _dims = self._get_dim_mappings_raw()
        color_dim_codes = self._get_color_dimension_codes()
        for m in mappings:
            if m.get("pricing_dimension") in color_dim_codes and m.get("material_category") == category:
                return m.get("variable_name")
        return None

    def _get_color_dimension_codes(self):
        """{dimension_code} có represents_color=1 — cache theo instance."""
        if getattr(self, "_color_dim_codes_cache", None) is not None:
            return self._color_dim_codes_cache
        codes = {
            d["name"] for d in frappe.get_all(
                "AL Pricing Dimension", filters={"represents_color": 1}, fields=["name"])
        }
        self._color_dim_codes_cache = codes
        return codes

    def _rule_input_config(self, rule_code):
        """Cấu hình "tra theo dữ liệu gì" của quy tắc — cache theo instance.

        `{}` khi quy tắc chưa khai `input_variable` (giữ nguyên hành vi cũ),
        khi mã rỗng, hoặc khi không đọc được rule (mã sai) — nơi gọi rơi về
        đường `rule_input_expr` cũ, ⛔ chết lượt tính.
        """
        if not rule_code:
            return {}
        cache = getattr(self, "_rule_input_cfg", None)
        if cache is None:
            cache = {}
            self._rule_input_cfg = cache
        if rule_code not in cache:
            config = {}
            try:
                doc = frappe.get_cached_doc("AL Rule", rule_code)
                config = rule_input_lib.rule_input_config(doc)
            except Exception:  # noqa: BLE001 — thiếu rule đã có cảnh báo riêng
                config = {}
            cache[rule_code] = config
        return cache[rule_code]

    @staticmethod
    def _rule_input_parts(expr, ref_slug, ref_field, value, found, scope,
                          missing=""):
        """Bộ dữ liệu 1 lần cho cả resolve lẫn câu trace.

        `missing` (§7.6 — `docs/design/tra-cuu-quy-tac-de-hieu.md`) phân loại
        vì sao KHÔNG có đầu vào: `no_source_row` / `row_gone` / `row_no_data` /
        `no_global_value`; rỗng = có đầu vào, hoặc quy tắc chưa khai gì.
        """
        return {
            "expr": expr,
            "ref_slug": ref_slug,
            "ref_field": ref_field,
            "var_name": ref_field if scope else "",
            "input_scope": scope,
            "input_value": value if found else None,
            "input_found": bool(found),
            "input_missing": missing or "",
        }

    def _rule_name_for(self, rule_code):
        """Tên quy tắc (nhãn người đọc) — cache theo instance.

        Dùng cho cảnh báo phát sinh TRƯỚC bước resolve (`_resolve_dynamic_item`
        mới điền `_rule_names`) — vd dòng thiếu nguồn dữ liệu tra. `rule_code`
        rỗng / rule không tồn tại ⇒ "" (⛔ phơi mã rule ra người dùng).
        """
        if not rule_code:
            return ""
        names = getattr(self, "_rule_cfg_names", None)
        if names is None:
            names = {}
            self._rule_cfg_names = names
        if rule_code not in names:
            try:
                names[rule_code] = frappe.get_cached_doc(
                    "AL Rule", rule_code).get("rule_name") or ""
            except Exception:  # noqa: BLE001 — thiếu rule đã có cảnh báo riêng
                names[rule_code] = ""
        return names[rule_code]

    def _rule_input_row_exists(self, row_slug, glass_data=None):
        """Slug dòng nguồn còn trong bộ BOM không (glass_data ∪ row_literals)."""
        if not row_slug:
            return False
        if glass_data and row_slug in glass_data:
            return True
        return row_slug in (getattr(self, "row_literals", {}) or {})

    def _rule_input_legacy(self, expr, glass_data=None):
        """Đường lùi CŨ `rule_input_expr = items.<slug>.<field>`.

        Trả `None` khi biểu thức không parse được (nơi gọi tự quyết định) —
        tách ra để `_describe_rule_input` giữ ĐÚNG hành vi cũ mà vẫn gắn được
        `input_missing` cho nhánh khai báo nhưng thiếu nguồn.
        """
        ref_match = re.match(
            r'items\.(\w[\w-]*)\.(\w+)', expr) if expr else None
        if not ref_match:
            return None
        ref_slug, ref_field = ref_match.group(1), ref_match.group(2)
        if glass_data and ref_slug in glass_data:
            value = glass_data[ref_slug].get(ref_field, 0)
        else:
            ref_lit = self.row_literals.get(ref_slug, {})
            value = ref_lit.get(ref_field, 0)
        return self._rule_input_parts(
            expr, ref_slug, ref_field, value, True, "")

    def _rule_input_from_row(self, row_slug, var_name, glass_data=None):
        """Đọc biến `var_name` của dòng `row_slug` — glass_data trước, rồi
        row_literals; alias độ dày kính do `rule_input.read_row_value` lo."""
        sources = []
        if glass_data:
            sources.append(glass_data)
        sources.append(getattr(self, "row_literals", {}) or {})
        for source in sources:
            value, found = rule_input_lib.read_row_value(
                source.get(row_slug), var_name)
            if found:
                return value, True
        return None, False

    def _rule_input_global(self, var_name, item):
        """Đọc biến TOÀN CỤC từ inputs của lượt tính; thiếu thì thử dữ liệu
        của CHÍNH dòng đó (`row_literals`) — §7.2 bước 3."""
        inputs = getattr(self, "inputs", {}) or {}
        if var_name in inputs and inputs.get(var_name) not in (None, ""):
            return inputs.get(var_name), True
        literals = getattr(self, "row_literals", {}) or {}
        value, found = rule_input_lib.read_row_value(
            literals.get(item.get("slug") or ""), var_name)
        if found:
            return value, True
        return None, False

    def _describe_rule_input(self, item, glass_data=None):
        """Phân giải đầu vào tra quy tắc cho ĐÚNG dòng `item` — §7.2.

        Thứ tự:
          1. quy tắc chưa khai `input_variable` ⇒ đường cũ `rule_input_expr`;
          2. biến THEO DÒNG (`ROW`): đọc dòng `rule_input_row`; thiếu dòng
             (hoặc dòng không mang biến đó) ⇒ lùi về `rule_input_expr` cũ;
          3. biến TOÀN CỤC (`GLOBAL`): đọc `inputs`, thiếu thì `row_literals`
             của chính dòng.

        ⚠ ALIAS độ dày kính (`glass_thick` ↔ `total_thick_mm`) do
        `rule_input.read_row_value` xử lý — rule cũ/mới đọc ra cùng một số.

        §7.6 — THIẾU NGUỒN ⛔ phải gộp với "không khớp": khi quy tắc CÓ khai
        biến mà không phân giải được, kết quả vẫn giữ `var_name` + `input_scope`
        (nếu không, câu giải thích quay về "chưa khai báo quy tắc" — SAI) và
        gắn `input_missing`:
          - `no_source_row`: ROW, `rule_input_row` rỗng, không có biểu thức lùi;
          - `row_gone`: slug đã chọn không còn trong bộ BOM;
          - `row_no_data`: dòng nguồn có nhưng không mang biến đó;
          - `no_global_value`: GLOBAL, `inputs` không có giá trị.
        Phạm vi ROW mà có `rule_input_expr` lùi được ⇒ giữ NGUYÊN hành vi cũ
        (không gắn missing). ⚠ GLOBAL KHÔNG có đường lùi đó — engine chỉ đọc
        `inputs` của lượt tính, nên thiếu giá trị vẫn là `no_global_value` dù
        dòng còn biểu thức cũ. Riêng biểu thức CÓ nhưng KHÔNG parse được thì
        vẫn là "không có nguồn" — giữ `var_name` và gắn missing, vì đường lùi
        không chạy.

        Trả dict `{expr, ref_slug, ref_field, var_name, input_scope,
        input_value, input_found, input_missing}` — resolve và trace dùng CHUNG
        một lần phân giải, ⛔ viết lại logic lần hai.
        """
        expr = str(item.get("rule_input_expr") or "").strip()
        config = self._rule_input_config(item.get("item_rule") or "")
        var_name = config.get("input_variable") or ""
        scope = config.get("input_scope") or ""

        if var_name and scope == rule_input_lib.ROW_SCOPE:
            row_slug = str(item.get("rule_input_row") or "").strip()
            if row_slug:
                value, found = self._rule_input_from_row(
                    row_slug, var_name, glass_data)
                if found:
                    return self._rule_input_parts(
                        expr, row_slug, var_name, value, True, scope)
                missing = ("row_no_data"
                           if self._rule_input_row_exists(row_slug, glass_data)
                           else "row_gone")
            else:
                missing = "no_source_row"
            if not expr:
                return self._rule_input_parts(
                    expr, row_slug, var_name, None, False, scope, missing)
            # Có biểu thức để lùi ⇒ đường CŨ (không gắn missing).
            legacy = self._rule_input_legacy(expr, glass_data)
            if legacy is not None:
                return legacy
            # Biểu thức hỏng ⇒ vẫn chưa có nguồn; giữ var_name/scope để câu
            # giải thích ⛔ quay về "chưa khai báo quy tắc".
            return self._rule_input_parts(
                expr, row_slug, var_name, None, False, scope, missing)
        if var_name:
            value, found = self._rule_input_global(var_name, item)
            # GLOBAL: `rule_input_expr` ⛔ phải đường lùi (engine đọc `inputs`
            # của lượt tính) ⇒ thiếu giá trị LÀ thiếu nguồn thật, kể cả khi
            # dòng còn biểu thức cũ — câu "không có mã nào khớp" ở đây là
            # giải thích SAI (bảng quy tắc chưa hề được hỏi).
            missing = "" if found else "no_global_value"
            return self._rule_input_parts(
                expr, "", var_name, value, found, scope, missing)

        legacy = self._rule_input_legacy(expr, glass_data)
        if legacy is not None:
            return legacy
        return self._rule_input_parts(expr, "", "", None, False, "")

    # ── §7.6 — cảnh báo "dòng chọn mã thiếu nguồn dữ liệu tra" ──────
    @staticmethod
    def _rule_source_line_label(item):
        """Tên DÒNG cho câu cảnh báo — ⛔ slug (kỹ thuật, khó tìm lại)."""
        name = str(item.get("line_name") or "").strip()
        if name:
            return name
        idx = item.get("idx")
        code = str(item.get("item_code") or "").strip()
        if idx and code:
            return "Dòng %s — %s" % (idx, code)
        if idx:
            return "Dòng %s" % idx
        return code or "Dòng chọn mã"

    @staticmethod
    def _rule_missing_reader_label(parts):
        """Nhãn dữ liệu đem tra cho câu người đọc.

        Uỷ quyền cho `rule_input.readable_input_label` — MỘT BẢN dùng chung
        với `rule_engine`/controller (⛔ chép chuỗi ở đây): `input_label` rỗng
        hoặc trùng đúng tên biến ⇒ "dữ liệu quy tắc đọc", ⛔ tên field kỹ
        thuật / slug.
        """
        parts = parts or {}
        return rule_input_lib.readable_input_label(
            parts.get("input_label"), parts.get("input_variable"))

    def _warn_missing_rule_source(self, item, glass_data=None):
        """Ghi cảnh báo engine khi dòng chọn mã KHÔNG có đầu vào tra — §7.6.

        Trước bản vá, b2 `continue` im lặng ⇒ dòng hàng mất mã mà ⛔ ai biết
        vì sao. Key theo (rule, slug) nên cùng một lỗi chỉ cảnh báo MỘT lần
        cho mỗi dòng. Câu nêu tên dòng + nhãn dữ liệu thiếu + việc phải làm +
        hậu quả tiền; ⛔ slug, ⛔ mã rule, ⛔ tên field kỹ thuật.
        """
        parts = self._describe_rule_input(item, glass_data)
        if parts.get("input_found"):
            return  # đối chứng: có đầu vào ⇒ ⛔ cảnh báo
        rule_code = item.get("item_rule") or ""
        # Nhãn dữ liệu đem tra KHÔNG nằm trong `_describe_rule_input` (nó chỉ
        # lo phân giải) — lấy từ cấu hình quy tắc đã cache, ⛔ thêm query.
        parts = dict(parts, input_label=(
            self._rule_input_config(rule_code).get("input_label") or ""))
        rule_name = self._rule_names.get(rule_code) \
            or self._rule_name_for(rule_code)
        rule_phrase = ('quy tắc "%s"' % rule_name) if rule_name \
            else "quy tắc chọn mã"
        line_name = self._rule_source_line_label(item)
        reason = parts.get("input_missing") or ""
        if reason:
            label = self._rule_missing_reader_label(parts)
            if reason == "no_source_row":
                detail = ("chưa chọn dòng lấy %s nên chưa chọn được mã vật tư. "
                          'Bấm "Chọn dòng lấy dữ liệu" rồi chọn dòng chứa dữ '
                          "liệu trong bộ BOM." % label)
            elif reason == "row_gone":
                detail = ("dòng đã chọn để lấy %s không còn trong bộ BOM nên "
                          "chưa chọn được mã vật tư. Chọn lại dòng lấy dữ liệu."
                          % label)
            elif reason == "row_no_data":
                source_name = self._rule_ref_line_name(parts.get("ref_slug"))
                where = ('dòng "%s"' % source_name) if source_name \
                    else "dòng đã chọn"
                detail = ("%s không có %s nên chưa chọn được mã vật tư. Chọn "
                          "dòng khác hoặc bổ sung dữ liệu cho dòng đó."
                          % (where, label))
            else:  # no_global_value
                detail = ("chưa có %s cho lượt tính này nên chưa chọn được mã "
                          "vật tư. Kiểm tra thông số đầu vào của báo giá."
                          % label)
            message = "Dòng \"%s\": %s %s — dòng này tạm không có mã vật tư, " \
                      "thành tiền chưa đúng." % (line_name, rule_phrase, detail)
        else:
            # `input_missing` rỗng mà vẫn ⛔ có đầu vào: quy tắc CŨ chưa khai
            # "tra theo" gì (hoặc biểu thức nâng cao không trỏ tới dòng nào).
            # Nếu biểu thức đường lùi chạy được thì b2 đã ⛔ tới đây.
            if parts.get("expr"):
                message = (
                    "Dòng \"%s\": %s có biểu thức nâng cao nhưng không xác "
                    "định được lấy dữ liệu từ dòng nào — dòng này tạm không "
                    "có mã vật tư, thành tiền chưa đúng. Báo quản trị kiểm "
                    "tra lại phần nâng cao của dòng." % (line_name,
                                                         rule_phrase))
            else:
                message = (
                    "Dòng \"%s\": %s chưa khai tra theo dữ liệu nào — dòng "
                    "này tạm không có mã vật tư, thành tiền chưa đúng. Báo "
                    "quản trị bổ sung ô \"Tra theo\" trong quy tắc."
                    % (line_name, rule_phrase))
        _record_engine_warning(
            "dynamic_rule_thieu_nguon:%s:%s" % (
                rule_code, item.get("slug") or item.get("idx") or ""),
            message,
        )

    def _resolve_rule_input_for_item(self, item, glass_data=None):
        """Tìm rule_input cho ĐÚNG dòng `item` này, dùng `rule_input_expr` CỦA
        CHÍNH nó — KHÔNG dò/mượn input từ dòng khác dù cùng `item_rule`
        (xem chú thích ở nơi gọi trong b2_prefetch_master_data để hiểu bug cũ
        đã sửa: cache theo rule_code DUY NHẤT làm mọi dòng cùng rule dùng
        chung 1 input của dòng đầu tiên tìm thấy).

        Chặng 3: quy tắc tự khai `input_variable` (`AL Rule`) thì lấy theo
        khai báo — xem `_describe_rule_input`. Quy tắc CHƯA khai ⇒ giữ NGUYÊN
        hành vi cũ (`rule_input_expr`).

        ALIAS độ dày kính: `glass_data[slug]` có CẢ `total_thick_mm` (tên
        chuẩn) lẫn `glass_thick` (tên cũ) cùng giá trị ⇒
        `items.kinh.total_thick_mm` và `items.kinh.glass_thick` resolve ra
        cùng một số, không phải sửa rule đã viết.
        """
        return self._describe_rule_input(item, glass_data)["input_value"]

    def _resolve_rule_input(self, item, lit):
        """Phân giải rule_input_expr: 'items.kinh_tren.glass_thick' → giá trị.

        ⚠️ HÀM CHẾT — không còn nơi nào gọi (đã `grep` toàn repo). Đường
        resolve thật là `_resolve_rule_input_for_item` ở trên (biết `glass_data`
        nên đọc được cả `total_thick_mm` lẫn alias `glass_thick`). Giữ lại chỉ
        để không phá ai đang import trực tiếp; ⛔ đừng dùng cho code mới.
        """
        expr = item.get("rule_input_expr", "")
        ref_match = re.match(
            r'items\.(\w[\w-]*)\.(\w+)', expr) if expr else None
        if ref_match:
            ref_slug, ref_field = ref_match.group(1), ref_match.group(2)
            ref_lit = self.row_literals.get(ref_slug, {})
            return ref_lit.get(ref_field, 0)
        return lit.get("glass_thick") if lit.get("glass_thick") else lit.get("glass_type", "")

    def _resolve_dynamic_item(self, rule_code, input_value):
        """Gọi AL Rule (rule chọn MÃ) để resolve item_code từ input.

        2026-10 (fix hiệu năng #1 — đã điều chỉnh sau kiểm chứng): KHÔNG xoá
        `item_name` khỏi `resolve_item()` — hàm đó còn là API whitelist công
        khai `alumglass.api.resolve_item_rule` (hooks.py), hợp đồng trả
        `{item_code, item_name}`, xoá field sẽ phá hợp đồng cho integration/
        caller ngoài engine. Thay vào đó, đường gọi NỘI BỘ của engine (chỉ
        cần `item_code`) bỏ qua `resolve_item()` và gọi thẳng `doc.resolve()`
        — rule doc đã `frappe.get_cached_doc` sẵn bên trong `resolve_item()`
        nên không mất cache; chỉ bớt đi 1 `frappe.db.get_value("Item", ...,
        "item_name")` bị query xong rồi vứt (item_name không được dùng ở
        đây — xem `resolved_items`/`resolved_item_names` ở B2, chỉ cần
        item_code để tra weight/price ở Batch query #6).

        Phase 2 (UX): hàm này ĐÃ có sẵn doc rule → cache luôn `rule_name` và
        khoảng/dòng khớp để câu giải thích dùng nhãn người đọc, ⛔ không phơi
        `rule_code`/`items.…` ra màn hình.
        """
        try:
            doc = frappe.get_cached_doc("AL Rule", rule_code)
        except frappe.DoesNotExistError:
            # Mã rule sai trong cấu hình ⛔ được làm CHẾT cả lượt tính giá (cùng
            # triết lý với `_lookup_rule`): ghi cảnh báo để người dùng thấy rồi
            # bỏ qua dòng này. Rule không tồn tại nên ⛔ có tên để nêu — chỉ mã.
            _record_engine_warning(
                "dynamic_rule_thieu_ma:%s" % rule_code,
                "Không tìm thấy quy tắc chọn mã '%s' (cấu hình tham chiếu "
                "sai?) — dòng này tạm không có mã vật tư, thành tiền chưa "
                "đúng. Báo quản trị kiểm tra ô Item Rule của dòng này."
                % rule_code,
            )
            return None
        # Nhãn NGƯỜI-ĐỌC-ĐƯỢC: `rule_name`, fallback mã khi chưa đặt tên.
        rule_label = doc.get("rule_name") or rule_code
        if (doc.get("result_type") or "") != "ITEM":
            # Chặng 2B: `AL Rule` gộp 2 loại — rule trả SỐ lọt vào ô "quy tắc
            # chọn mã" là lỗi cấu hình. Nói đúng việc phải làm, ⛔ lặng lẽ bỏ
            # mã khiến dòng hàng mất tiền mà không ai biết vì sao.
            _record_engine_warning(
                "dynamic_rule_sai_loai:%s" % rule_code,
                "Quy tắc \"%s\" là quy tắc tính giá trị, không phải quy tắc "
                "chọn mã — dòng này tạm không có mã vật tư, thành tiền chưa "
                "đúng. Báo quản trị sửa ô Item Rule của dòng này."
                % rule_label,
            )
            return None
        if not rule_engine.rule_is_active(doc):
            # Rule đã TẮT nhưng item_rule còn trỏ tới: ⛔ im lặng bỏ mã.
            _record_engine_warning(
                "dynamic_rule_da_tat:%s" % rule_code,
                "Quy tắc chọn mã \"%s\" đã TẮT nhưng công thức còn dùng — "
                "dòng này tạm không có mã vật tư, thành tiền chưa đúng. Báo "
                "quản trị bật lại quy tắc này." % rule_label,
            )
            return None
        # ⛔ KHÔNG fallback về `doc.name`: đó chính là mã rule (`RULE-NEP`) và
        # sẽ lọt vào câu hiển thị. Để rỗng — hàm dựng câu đã có fallback
        # "Quy tắc chọn mã".
        self._rule_names[rule_code] = doc.get("rule_name") or ""
        # Nhãn TỰ MÔ TẢ của quy tắc (AL Rule): câu trace ưu tiên `input_label`
        # thay cho tên field kỹ thuật; `rule_description` đi vào kết quả để
        # `explain_bom_line` nối thêm câu giải thích. Chỉ đổi CHỮ — ⛔ đổi
        # kết quả tính tiền/mã.
        self._rule_meta[rule_code] = {
            "rule_name": self._rule_names[rule_code],
            # ⛔ Lưu nguyên nhãn có thể là TÊN BIẾN (dữ liệu cũ điền tay):
            # `rule_input_label` của dòng đi thẳng ra client hiển thị ⇒ phải
            # đọc được. Quy tắc CHƯA khai biến ⇒ giữ "" để giữ nguyên đường
            # nhãn cũ (suy từ field của biểu thức).
            "input_label": (
                rule_input_lib.readable_input_label(
                    doc.get("input_label"), doc.get("input_variable"))
                if (doc.get("input_variable") or "").strip() else ""),
            "input_unit": doc.get("input_unit") or "",
            "input_variable": doc.get("input_variable") or "",
            "input_scope": doc.get("input_scope") or "",
            "output_label": doc.get("output_label") or "",
            "rule_description": doc.get("rule_description") or "",
        }
        resolved = doc.resolve(input_value)
        if resolved:
            self._rule_matches[(rule_code, input_value)] = {
                "rule_name": self._rule_names[rule_code],
                "rule_type": doc.get("rule_type") or "",
                "match": self._describe_rule_match(doc, input_value),
            }
        else:
            # Rule ĐANG BẬT nhưng không dòng nào khớp giá trị tra cứu: dòng
            # hàng mất mã vật tư ⇒ thành tiền 0. Trước bản vá chỗ này trả None
            # IM LẶNG (câu "không có mã nào khớp" chỉ nằm trong rule_trace,
            # phải bấm "Vì sao ra số này?" mới thấy) ⇒ banner trống, người
            # dùng tưởng giá đúng. Rule TẮT đã báo riêng ở trên ⇒ ⛔ báo trùng.
            _record_engine_warning(
                "dynamic_rule_khong_khop:%s" % rule_code,
                "Quy tắc \"%s\" không có dòng nào khớp giá trị tra cứu — dòng "
                "này tạm không có mã vật tư, thành tiền chưa đúng. Báo quản "
                "trị kiểm tra lại dải/bảng tra của quy tắc." % rule_label,
            )
        return resolved

    @staticmethod
    def _describe_rule_match(doc, input_value):
        """Mô tả dòng/ngưỡng ĐÃ KHỚP (cho bước 3) — chỉ dùng dữ liệu có sẵn."""
        try:
            if (doc.get("rule_type") or "") == "THRESHOLD":
                val = float(input_value)
                rows = sorted(
                    doc.get("threshold_rows") or [],
                    key=lambda r: r.get("from_value"))
                for row in rows:
                    start = row.get("from_value")
                    end = row.get("to_value")
                    if start is None or end is None:
                        continue
                    if (start <= val < end) or val == end:
                        return "dải %s – %s" % (_round_num(start),
                                                _round_num(end))
            elif (doc.get("rule_type") or "") == "LOOKUP":
                for row in (doc.get("lookup_rows") or []):
                    if str(row.get("key_field")) == str(input_value):
                        return "giá trị khớp %s" % input_value
        except (ValueError, TypeError):
            pass
        return ""

    # ══════════════════════════════════════════════════════════════════
    # B1 (thiết kế "gộp nơi cấu hình biến và tính toán", 2026-11-27)
    # MỘT nguồn duy nhất cho "field nào là field công thức".
    # ══════════════════════════════════════════════════════════════════
    def _read_legacy_formula_fields(self, bom_set):
        """Đọc danh sách RIÊNG của bộ: `AL Bom Set.formula_fieldnames`.

        Field này đã ngừng dùng (thiết kế B1) nhưng vẫn được TÔN TRỌNG khi
        có giá trị: B0 (đo trên site) chưa chạy, nên đổi nguồn cho các bộ
        đang khai danh sách riêng có thể đổi SỐ TIỀN của báo giá đang chạy.
        Bộ nào còn khai ⇒ giữ nguyên hành vi cũ + cảnh báo, để quản trị bỏ
        dần (xem `_resolve_formula_fieldnames`).

        Chấp nhận JSON string (kiểu lưu của field) hoặc list/dict đã parse.
        Hỏng/không phải danh sách ⇒ [] (coi như bộ KHÔNG khai danh sách riêng).
        """
        if not bom_set:
            return []
        try:
            raw = (bom_set.get("formula_fieldnames")
                   if hasattr(bom_set, "get")
                   else getattr(bom_set, "formula_fieldnames", None))
        except Exception:
            return []
        if not raw:
            return []
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (ValueError, TypeError):
                return []
        if not isinstance(raw, (list, tuple)):
            return []
        return [str(f).strip() for f in raw
                if isinstance(f, str) and str(f).strip()]

    def _read_registry_formula_fields(self):
        """Đọc sổ đăng ký `AL Formula Field` qua hàm DÙNG CHUNG.

        Import muộn (trong hàm): `alumglass.api` import engine này ở top-level
        ⇒ import sớm sẽ thành vòng. Lỗi bất kỳ (site chưa migrate, app `api`
        lỗi, bảng thiếu cột) ⇒ [] để engine rơi lưới dự phòng VÀ KÊU.
        """
        try:
            from alumglass.api.formula_registry import get_formula_fieldnames
            return get_formula_fieldnames(
                FORMULA_REGISTRY_DOCTYPE,
                child_table=FORMULA_REGISTRY_CHILD_TABLE,
            )
        except Exception:
            try:
                frappe.logger("alumglass").warning(
                    "Không đọc được sổ đăng ký AL Formula Field cho %s:\n%s"
                    % (FORMULA_REGISTRY_DOCTYPE, frappe.get_traceback()))
            except Exception:
                pass
            return []

    def _warn_unregistered_formula_fields(self, registered):
        """KÊU khi dòng BOM có công thức ở field mà registry KHÔNG khai.

        Trước đây loại hỏng này hoàn toàn im lặng: nhập công thức thành công,
        engine không bao giờ đánh giá field đó ⇒ số ra sai mà không ai biết
        (thiết kế B1, mục P1 — ca 2 field `panel_count_formula` /
        `qty_per_panel_formula`, đã bị gỡ khỏi dòng BOM ở R5 2026-11-27).

        ⛔ KHÔNG tự thêm field thiếu vào danh sách tính: sổ đăng ký là nguồn
        duy nhất; cảnh báo cho quản trị biết để THÊM BẢN GHI (mở rộng bằng
        dữ liệu), ⛔ vá bằng danh sách cứng.
        """
        registered = set(registered or ())
        for item in self.bom_items or []:
            for field in FORMULA_FIELD_CANDIDATES:
                if field in registered:
                    continue
                expr = item.get(field)
                if not (expr and str(expr).strip()):
                    continue
                key = "formula_fields_registry_thieu:%s" % field
                if key in self.bom_engine_errors:
                    continue
                self.bom_engine_errors[key] = (
                    "Cảnh báo: dòng BOM '%s' đang có công thức ở ô '%s' nhưng "
                    "sổ đăng ký field công thức (AL Formula Field) không khai "
                    "ô này — công thức đó sẽ KHÔNG được tính. Thêm bản ghi "
                    "AL Formula Field (Doctype: %s, Child table: %s, "
                    "Fieldname: %s) hoặc bỏ công thức khỏi ô đó."
                    % (item.get("slug") or "?", field,
                       FORMULA_REGISTRY_DOCTYPE, FORMULA_REGISTRY_CHILD_TABLE,
                       field)
                )

    def _resolve_formula_fieldnames(self):
        """Chọn danh sách field công thức theo ĐÚNG thứ tự ưu tiên (B1).

        1. `AL Bom Set.formula_fieldnames` CÓ giá trị ⇒ giữ hành vi cũ (danh
           sách riêng của bộ) + cảnh báo `formula_fields_legacy_list:<mã bộ>`.
           Lý do: B0 chưa đo trên site, đổi nguồn có thể đổi số tiền.
        2. Không có danh sách riêng ⇒ sổ đăng ký `AL Formula Field`
           (child_table = items, is_active = 1, thứ tự `sort_order`).
        3. Sổ đăng ký RỖNG (chưa migrate / đọc lỗi) ⇒ `DEFAULT_FORMULA_FIELDS`
           + cảnh báo TO `formula_fields_fallback_registry` (⛔ im lặng).
        4. Sổ đăng ký có dữ liệu nhưng THIẾU field mà dòng BOM đang có công
           thức ⇒ dùng đúng registry + cảnh báo
           `formula_fields_registry_thieu:<field>` (⛔ tự thêm lại).

        Kết quả được cache vào `self._formula_fieldnames` (b3 chỉ chạy 1 lần
        mỗi lượt tính, nhưng nhiều đường gọi thẳng được b3).
        """
        if getattr(self, "_formula_fieldnames", None) is not None:
            return self._formula_fieldnames

        bom_set = self._get_bom_set()
        set_code = ""
        if bom_set is not None:
            try:
                set_code = (bom_set.get("name")
                            if hasattr(bom_set, "get")
                            else getattr(bom_set, "name", "")) or ""
            except Exception:
                set_code = ""

        legacy = self._read_legacy_formula_fields(bom_set)
        if legacy:
            self.bom_engine_errors[
                "formula_fields_legacy_list:%s" % (set_code or "?")] = (
                "Cảnh báo: bộ BOM '%s' đang dùng danh sách field công thức "
                "riêng (ô Formula Fieldnames) — nên bỏ để dùng sổ đăng ký "
                "chung (AL Formula Field), tránh 2 danh sách lệch nhau."
                % (set_code or "?")
            )
            self._formula_fieldnames = legacy
            return legacy

        registry = self._read_registry_formula_fields()
        if not registry:
            self.bom_engine_errors["formula_fields_fallback_registry"] = (
                "Cảnh báo: chưa đọc được sổ đăng ký field công thức "
                "(AL Formula Field) — đang dùng danh sách dự phòng. Kiểm tra "
                "bảng AL Formula Field (đã migrate chưa, có bản ghi cho %s/%s "
                "chưa)."
                % (FORMULA_REGISTRY_DOCTYPE, FORMULA_REGISTRY_CHILD_TABLE)
            )
            try:
                # Ghi cả log phía máy chủ: cảnh báo trên UI chỉ tới người đang
                # tính giá, quản trị cần thấy cả ở bench log.
                frappe.logger("alumglass").warning(
                    "Rơi lưới dự phòng DEFAULT_FORMULA_FIELDS: sổ đăng ký "
                    "AL Formula Field rỗng cho %s/%s (mã bộ: %s)."
                    % (FORMULA_REGISTRY_DOCTYPE,
                       FORMULA_REGISTRY_CHILD_TABLE, set_code or "?"))
            except Exception:
                pass
            self._formula_fieldnames = list(DEFAULT_FORMULA_FIELDS)
            return self._formula_fieldnames

        self._warn_unregistered_formula_fields(registry)
        self._formula_fieldnames = registry
        return registry

    # ══════════════════════════════════════════════════════════════════
    # B3: Build Formulas — tạo formula list cho FormulaEngine (FB)
    # ══════════════════════════════════════════════════════════════════
    def b3_build_formulas(self):
        """Build list of {name, formula} dicts cho FormulaEngine.

        Danh sách field công thức lấy từ `_resolve_formula_fieldnames()` —
        sổ đăng ký `AL Formula Field` là nguồn duy nhất, danh sách riêng của
        bộ chỉ còn để tương thích (có cảnh báo), `DEFAULT_FORMULA_FIELDS` chỉ
        là lưới an toàn có cảnh báo.

        V6 Phase 1d: với line có calc_pattern, đọc `input_vars` (danh sách biến
        phụ) từ AL Quantity Calc Method → resolve giá trị từ (1) input_vars của
        line, (2) biến global user đã nhập, (3) row_literals, (4) default 0 →
        truyền vào lookup_calc_pattern dưới dạng keyword:
        lookup_calc_pattern(code, w, h, tlr, piece_length=...).
        Pattern không có biến phụ → formula giữ nguyên (backward-compat).
        """
        self.bom_formulas = []
        formula_fields = self._resolve_formula_fieldnames()

        # ── 2026-09 (nâng cấp #1 — hao hụt cắt vật tư thật): áp dụng
        # `AL Material Category.default_scrap_pct` (đã fetch vào context
        # {slug}__scrap_pct từ B2) vào total_qty — PHẢN ÁNH đúng thực tế
        # ngành nhôm kính: cắt thanh nhôm từ cây 6m / cắt kính từ tấm jumbo
        # LUÔN có hao hụt (kerf lưỡi cưa, mép biên, đầu mẩu không đủ dùng
        # lại) — trước bản vá này, `scrap_pct` được fetch vào context
        # nhưng KHÔNG hàm nào thực sự nhân vào số lượng → giá thành bị
        # tính THIẾU so với thực tế thu mua.
        #
        # OPT-IN qua `AL Bom Set.apply_scrap_pct` (Check, default 0) — theo
        # đúng quy ước OPT-IN xuyên suốt codebase này (không có cờ = giữ
        # nguyên 100% hành vi cũ, golden test không đổi). Bật cờ này cho
        # từng Bom Set sau khi đã review lại giá bán với đội kinh doanh —
        # đây là THAY ĐỔI SỐ LIỆU THẬT (tăng giá thành), không bật tràn lan.
        bom_set_for_scrap = self._get_bom_set()
        apply_scrap = bool(bom_set_for_scrap and bom_set_for_scrap.get("apply_scrap_pct"))

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
            # `total_thick_mm` / `max_area_m2`: bơm vào context để công thức
            # width/height/qty dùng `items.X.total_thick_mm` /
            # `items.X.max_area_m2` ra ĐÚNG số (trước đây chỉ glass_data có,
            # nên công thức đọc bị 0). `glass_thick` giữ làm alias cũ.
            #
            # B3a: bơm THÊM mọi biến theo dòng khai trong Library (category
            # Row Literals) — nhờ vậy `items.<dòng>.<biến mới>` chạy được mà
            # ⛔ phải sửa tệp này. Tên chưa khai trong Library vẫn không bơm
            # (tránh đưa rác vào namespace công thức).
            declared = {d["name"] for d in self._row_literal_defs()}
            for key in tuple(declared | {
                    "weight_per_unit", "unit_price", "calc_pattern",
                    "total_thick_mm", "glass_thick", "glass_type",
                    "max_area_m2", "scrap_pct"}):
                if key in lit:
                    self.inputs[f"{slug}__{key}"] = lit[key]

            # Pre-set defaults cho các field (tránh NameError trong engine)
            for field in ("width", "height", "qty", "calc_pattern",
                          "weight_per_unit", "unit_price", "scrap_pct",
                          "total_thick_mm", "glass_thick", "max_area_m2"):
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
                    # Chặng 3 (§7.2 bước 4): `lookup_rule('MÃ')` một tham số
                    # → chèn biến TOÀN CỤC mà quy tắc tự khai TRƯỚC khi
                    # normalize. Quy tắc ROW/chưa khai ⇒ giữ nguyên, để
                    # validation cảnh báo (⛔ đoán dòng nào).
                    expr = self._inject_declared_rule_input(str(expr))
                    # B4 FB-max: items.X.Y → items['X']['Y'] bằng
                    # DotToSubscriptTransformer (thay regex thủ công).
                    normalized = self._normalize_items_ref(expr)
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
            # 2026-09 (nâng cấp #1): total_qty = unit_qty × qty × (1 + scrap%)
            # khi Bom Set bật apply_scrap_pct — scrap_pct lưu dạng % nguyên
            # (vd 3 = 3%, xem AL Material Category.default_scrap_pct), nên
            # chia 100 tại đây. scrap_pct=0 (mặc định PK/phụ kiện) → hệ số
            # nhân = 1, KHÔNG đổi kết quả — an toàn cho category chưa cấu
            # hình hao hụt.
            if apply_scrap:
                total_qty_formula = (
                    f"({slug}__unit_qty * {slug}__qty) * "
                    f"(1 + {slug}__scrap_pct/100)")
            else:
                total_qty_formula = f"{slug}__unit_qty * {slug}__qty"
            self.bom_formulas.append({
                "name": f"{slug}__total_qty",
                "formula": total_qty_formula,
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

    def _inject_declared_rule_input(self, expr):
        """`lookup_rule('MÃ')` → `lookup_rule('MÃ', <biến>)` khi quy tắc khai
        biến TOÀN CỤC — chặng 3 §7.2 bước 4.

        Chỉ thay lời gọi ĐÚNG MỘT tham số (mã literal). Quy tắc khai biến
        THEO DÒNG hoặc chưa khai biến ⇒ giữ nguyên: engine ⛔ đoán dòng nào,
        validation (`validate_lookup_rule_codes`) sẽ cảnh báo người cấu hình.
        ⛔ đổi số tiền: biến chèn vào chính là biến quy tắc đã tuyên bố dùng.
        """
        if not expr or "lookup_rule" not in expr:
            return expr

        def _replace(match):
            code = match.group("code")
            config = self._rule_input_config(code)
            if config.get("input_scope") != rule_input_lib.GLOBAL_SCOPE:
                return match.group(0)
            var_name = config.get("input_variable")
            if not var_name:
                return match.group(0)
            quote = match.group("quote")
            return "lookup_rule(%s%s%s, %s)" % (quote, code, quote, var_name)

        return _ONE_ARG_LOOKUP_RULE_RE.sub(_replace, expr)

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
        except Exception as exc:
            # D9: fallback regex thủ công giữ nguyên hành vi DB cũ, nhưng lỗi
            # (thiếu module FB) không được biến mất. Dùng logger (không phải
            # log_error) vì hàm này chạy cho TỪNG formula — tránh ngập Error Log.
            frappe.logger("alumglass").error(
                "AlumGlass: normalize_global không dùng được, fallback regex — %s"
                % exc)
            return re.sub(r'items\.(\w[\w-]*)\.(\w+)', r'\1__\2', expr)

    # ══════════════════════════════════════════════════════════════════
    # B4: Calculate Bom Items — dùng FormulaEngine (FB)
    # ══════════════════════════════════════════════════════════════════
    @staticmethod
    def _trace_value(value):
        """Định dạng giá trị cho dữ liệu KỸ THUẬT (*_raw) — support đối chiếu."""
        if value is None:
            return "?"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(_round_num(value))
        text = str(value).strip()
        return text or "?"

    # ── Nhãn người đọc cho câu giải thích (Phase 2 / UX) ────────────
    #: Link dimension → field chứa TÊN hiển thị (⛔ không lấy docname).
    _LINK_DISPLAY_FIELDS = {
        "AL Color Standard": "color_name",
        "AL Glass Type": "type_name",
        "AL Glass Master": "glass_name",
        "Item": "item_name",
    }

    def _price_list_display(self, price_list):
        """Tên bảng giá để hiển thị (fallback chính tên bảng giá)."""
        if not price_list:
            return ""
        if price_list in self._price_list_names:
            return self._price_list_names[price_list]
        label = ""
        try:
            label = frappe.db.get_value(
                "Price List", price_list, "price_list_name") or ""
        except Exception:
            label = ""
        self._price_list_names[price_list] = label or price_list
        return self._price_list_names[price_list]

    def _display_link_value(self, link_doctype, value):
        """Tên hiển thị của 1 giá trị Link — rỗng nếu không suy được (caller bỏ
        dimension đó thay vì phơi docname/mã enum)."""
        key = (link_doctype, value)
        if key in self._link_value_cache:
            return self._link_value_cache[key]
        field = self._LINK_DISPLAY_FIELDS.get(link_doctype) or ""
        label = ""
        if field:
            try:
                label = frappe.db.get_value(
                    link_doctype, value, field) or ""
            except Exception:
                label = ""
        self._link_value_cache[key] = label
        return label

    def _dimension_display_map(self):
        """variable_name → {label, link_doctype} cho câu giải thích giá."""
        if self._dimension_meta is not None:
            return self._dimension_meta
        mappings, _dims = self._get_dim_mappings_raw()
        dim_codes = list({
            m.get("pricing_dimension") for m in mappings
            if m.get("pricing_dimension")})
        metas = {}
        if dim_codes:
            try:
                for d in frappe.get_all(
                        "AL Pricing Dimension",
                        filters={"name": ("in", dim_codes)},
                        fields=["name", "dimension_name", "link_doctype"]):
                    metas[d["name"]] = d
            except Exception:
                metas = {}
        out = {}
        for m in mappings:
            var_name = m.get("variable_name")
            if not var_name:
                continue
            meta = metas.get(m.get("pricing_dimension")) or {}
            out[var_name] = {
                "label": meta.get("dimension_name") or display_label(var_name),
                "link_doctype": meta.get("link_doctype") or "",
            }
        self._dimension_meta = out
        return out

    def _dimension_display(self, value, var_name, meta):
        """Chuỗi hiển thị của 1 giá trị dimension — "" nghĩa là KHÔNG in.

        - `None`/rỗng và `0` ⇒ "" (0 = "không dùng tiêu chí này").
        - Value nhiều dòng ⇒ dòng giá áp cho NHIỀU lựa chọn → "nhiều lựa chọn"
          (⛔ không cắt thành 1 giá trị — đó là bịa; ⛔ không in chuỗi thô).
        - Dimension Link: resolve tên người đọc; không resolve được ⇒ "".
        """
        lines = _dimension_value_lines(value)
        if not lines:
            return ""
        if len(lines) > 1:
            return "nhiều lựa chọn"
        if _is_zero_dimension_value(value):
            return ""
        link_doctype = (meta or {}).get("link_doctype") or ""
        if link_doctype:
            return self._display_link_value(link_doctype, value)
        return _format_number_vi(value, display_unit(var_name))

    def _matched_dim_entries(self, info):
        """Dimension của DÒNG GIÁ ĐÃ CHỌN → [{label, display, matched}].

        `matched` = tiêu chí đó có ĐƯỢC DÙNG ĐỂ KHỚP (`value == input`) hay
        chỉ là thuộc tính kèm theo của dòng giá (vd dòng gốc / dòng duy nhất).
        ⛔ Không đoán: chỉ so đúng composite key đã dùng lúc tra.
        """
        row = info.get("row") if isinstance(info, dict) else None
        if not isinstance(row, dict):
            return []
        fieldnames = info.get("dim_fieldnames") or {}
        inputs = info.get("match_inputs") or {}
        meta_map = self._dimension_display_map()
        out = []
        for var_name, fieldname in fieldnames.items():
            value = row.get(fieldname)
            meta = meta_map.get(var_name) or {}
            shown = self._dimension_display(value, var_name, meta)
            if not shown:
                continue
            out.append({
                "label": meta.get("label") or display_label(var_name),
                "display": shown,
                "matched": bool(value)
                and str(value) == str(inputs.get(var_name, "")),
            })
        return out

    def _dimension_values_display(self, info):
        """Các dimension của dòng giá đã chọn → ["Màu sắc: Trắng", …]."""
        return ["%s: %s" % (e["label"], e["display"])
                for e in self._matched_dim_entries(info)]

    # ── Chọn mã để TRA GIÁ (đúng thứ tự B2) ─────────────────────────
    def _price_code_for_trace(self, item, lit):
        """Trả (price_code, display_code, price_base_item) — mã thực dùng để
        lấy tiền. B2: Rule resolved > price_base_item > item_code."""
        display_code = lit.get("item_code") or item.get("item_code") or ""
        price_base_item = item.get("price_base_item") or ""
        resolved_code = None
        if item.get("item_selection_mode") == "Rule" and item.get("item_rule"):
            rule_input = self._resolve_rule_input_for_item(
                item, getattr(self, "_glass_data", None))
            if rule_input not in (None, ""):
                resolved_code = getattr(self, "_resolved_rule_items", {}).get(
                    (item.get("item_rule"), rule_input))
        if item.get("item_selection_mode") == "Rule" and resolved_code:
            price_code = resolved_code
        elif price_base_item:
            price_code = price_base_item
        else:
            price_code = display_code or item.get("item_code") or ""
        return price_code, display_code, price_base_item

    # ── Rule: lấy phần dữ liệu 1 lần, in 2 dạng (raw / người đọc) ───
    def _rule_trace_parts(self, item):
        rule_code = item.get("item_rule") or ""
        info = self._describe_rule_input(item, getattr(self, "_glass_data", None))
        input_value = info.get("input_value")
        resolved = None
        if input_value not in (None, ""):
            resolved = getattr(self, "_resolved_rule_items", {}).get(
                (rule_code, input_value))
        match_info = {}
        if input_value not in (None, ""):
            match_info = getattr(self, "_rule_matches", {}).get(
                (rule_code, input_value)) or {}
        meta = getattr(self, "_rule_meta", {}).get(rule_code) or {}
        config = self._rule_input_config(rule_code)
        # Nhãn dữ liệu đem tra: nhãn của quy tắc có thể là TÊN BIẾN (dữ liệu
        # cũ điền tay) ⇒ qua hàm đọc-được dùng chung. Quy tắc CHƯA khai biến
        # ⇒ để "" (đường cũ: nhãn suy từ field của biểu thức).
        input_var = (config.get("input_variable")
                     or info.get("var_name") or "").strip()
        input_label = meta.get("input_label") or config.get("input_label") or ""
        if input_var:
            input_label = rule_input_lib.readable_input_label(
                input_label, input_var)
        return {
            "rule_code": rule_code,
            "expr": info.get("expr") or "",
            "ref_slug": info.get("ref_slug") or "",
            "ref_field": info.get("ref_field") or "",
            "input_variable": info.get("var_name") or "",
            "input_scope": info.get("input_scope") or "",
            "input_value": input_value,
            "input_found": info.get("input_found"),
            # §7.6 — vì sao KHÔNG có đầu vào (rỗng = có, hoặc chưa khai gì).
            "input_missing": info.get("input_missing") or "",
            # Tên DÒNG nguồn (đã resolve) — ⛔ slug ra câu người đọc.
            "ref_line_name": self._rule_ref_line_name(info.get("ref_slug")),
            "resolved": resolved,
            # Tên quy tắc cho câu người đọc. `_rule_names` chỉ được điền khi
            # resolve THÀNH CÔNG (trong `_resolve_dynamic_item`) — dòng thiếu
            # nguồn ⛔ đi qua đó, nên lùi về cache `_rule_name_for` (§7.6).
            "rule_name": (self._rule_names.get(rule_code)
                          or self._rule_name_for(rule_code)),
            # Nhãn tự mô tả của quy tắc (rỗng với rule cũ chưa khai).
            "input_label": input_label,
            "input_unit": meta.get("input_unit") or "",
            "output_label": meta.get("output_label") or "",
            "rule_description": meta.get("rule_description") or "",
            "match": match_info.get("match") or "",
        }

    def _rule_ref_line_name(self, ref_slug):
        """Tên dòng được tham chiếu — ⛔ fallback slug (kỹ thuật) ra màn hình."""
        if not ref_slug:
            return ""
        for row in self.bom_items:
            if (row.get("slug") or "") == ref_slug:
                return row.get("line_name") or ""
        return ""

    @staticmethod
    def _rule_source_flags(rule_parts, is_rule_row):
        """Cờ trạng thái NGUỒN TRA của 1 dòng kết quả — §7.6.

        Tách khỏi vòng lặp B4 để test được bằng hàm thuần, và để client/API
        đọc MỘT nguồn duy nhất thay vì tự suy từ chữ nghĩa câu trace:

          - `rule_input_missing` = 1: dòng Rule ⛔ khai gì cả (không biểu thức,
            không biến) ⇒ câu "chưa khai báo quy tắc";
          - `rule_source_missing` = 1: quy tắc ĐÃ khai nhưng lượt tính thiếu
            nguồn (`no_source_row` / `row_gone` / `row_no_data` /
            `no_global_value`) ⇒ câu "chưa chọn dòng lấy dữ liệu…";
          - `rule_missing_reason` = lý do cụ thể (rỗng khi không thiếu);
          - `rule_input_found` = đã có giá trị đem tra hay chưa;
          - `rule_input_label` = nhãn dữ liệu đem tra (client hiển thị).
        """
        if not is_rule_row:
            return {
                "rule_input_missing": 0,
                "rule_source_missing": 0,
                "rule_missing_reason": "",
                "rule_input_found": False,
                "rule_input_label": "",
            }
        parts = rule_parts or {}
        has_declared = bool(parts.get("input_variable"))
        has_expr = bool(parts.get("expr"))
        reason = parts.get("input_missing") or ""
        return {
            "rule_input_missing": 0 if (has_declared or has_expr) else 1,
            "rule_source_missing": 1 if reason else 0,
            "rule_missing_reason": reason,
            "rule_input_found": bool(parts.get("input_found")),
            "rule_input_label": parts.get("input_label") or "",
        }

    def _rule_input_display(self, parts):
        """Giá trị đầu vào dạng người đọc (đơn vị + nhãn loại kính)."""
        value = parts.get("input_value")
        field = parts.get("ref_field") or ""
        if field == "glass_type":
            gd = (getattr(self, "_glass_data", {}) or {}).get(
                parts.get("ref_slug") or "") or {}
            shown = gd.get("glass_type_name") or ""
            if shown:
                return shown
        return _format_number_vi(value, display_unit(field))

    def _rule_missing_trace_text(self, parts, missing):
        """Câu giải thích khi THIẾU nguồn dữ liệu tra — §7.6.

        Bốn trạng thái, bốn câu, bốn hành động khác nhau; ⛔ mã rule, ⛔ slug,
        ⛔ tên field kỹ thuật. Nhãn dữ liệu lấy từ `input_label` của quy tắc.
        """
        label = self._rule_missing_reader_label(parts)
        rule_name = (parts.get("rule_name") or "").strip()
        rule_phrase = ('quy tắc "%s"' % rule_name) if rule_name \
            else "quy tắc"
        if missing == "no_source_row":
            return ('Chọn mã theo %s nhưng chưa chọn dòng lấy %s — chọn dòng '
                    "chứa dữ liệu trong bộ BOM." % (rule_phrase, label))
        if missing == "row_gone":
            return ("Dòng đã chọn để lấy %s không còn trong bộ BOM — chọn lại "
                    "dòng lấy dữ liệu." % label)
        if missing == "row_no_data":
            source_name = (parts.get("ref_line_name") or "").strip() \
                or self._rule_ref_line_name(parts.get("ref_slug"))
            where = ('Dòng "%s"' % source_name) if source_name \
                else "Dòng đã chọn"
            return ("%s không có %s — chọn dòng khác hoặc bổ sung dữ liệu cho "
                    "dòng đó." % (where, label))
        # no_global_value
        return ("Chưa có %s cho lượt tính này nên chưa chọn được mã — kiểm tra "
                "thông số đầu vào của báo giá." % label)

    def _rule_trace_text(self, parts):
        """Câu giải thích chọn mã — nhãn nghiệp vụ, ⛔ không mã rule/biểu thức.

        Thứ tự câu: **giá trị đem tra → mã chọn được** đứng TRƯỚC, quy tắc
        đứng SAU (`· theo quy tắc "…"`). Client hiển thị tối đa 2 dòng: nếu
        bị cắt đuôi thì mất tên quy tắc, ⛔ mất con số/mã — phần người dùng
        cần để đối chiếu giá.

        Chặng 3: đầu vào có thể đến từ BIẾN TỰ KHAI của quy tắc thay vì
        `rule_input_expr` ⇒ câu vẫn đọc được, ⛔ phơi `items.…`. Biến toàn
        cục không có "dòng" để nêu — câu chỉ còn `Chiều cao = 3200`.

        §7.6: THIẾU NGUỒN ⛔ được giải thích bằng "không có mã nào khớp" —
        người dùng sẽ đi sửa bảng quy tắc trong khi việc thật là chưa chọn
        dòng lấy dữ liệu. Câu riêng theo `input_missing`, chỉ nêu việc phải
        làm (⛔ mã rule / slug / tên field kỹ thuật).
        """
        if not parts:
            return ""
        has_legacy = bool(parts.get("expr") and parts.get("ref_field")
                          and not parts.get("input_variable"))
        has_declared = bool(parts.get("input_variable"))
        if not (has_legacy or has_declared):
            return "Dòng này chưa khai báo quy tắc chọn mã."
        # Thiếu nguồn dữ liệu tra ⇒ câu RIÊNG, trước mọi câu "không khớp".
        missing = (parts.get("input_missing") or "").strip()
        if missing and not parts.get("input_found"):
            return self._rule_missing_trace_text(parts, missing)
        rule_name = parts.get("rule_name") or ""
        # Rule chưa đặt tên ⇒ nhãn chung, ⛔ bọc ngoặc kép rỗng.
        tail = ('theo quy tắc "%s"' % rule_name) if rule_name \
            else "theo quy tắc chọn mã"
        # Ưu tiên nhãn NGHIỆP VỤ do rule tự khai (`input_label`, vd "Độ dày
        # kính"). Rule cũ chưa khai ⇒ giữ nhãn suy từ tên field như trước.
        # ⛔ hạ chữ thường nhãn người đặt (đó là tên riêng, không phải field).
        input_label = (parts.get("input_label") or "").strip()
        if input_label:
            field_label = input_label
        else:
            field_key = parts.get("ref_field") or parts.get("input_variable") or ""
            # ⛔ Fallback về `field_key` trần (tên field/biến kỹ thuật): không
            # tra được nhãn người đọc ⇒ câu chung dùng chung.
            field_label = (display_label(field_key).lower()
                           or rule_input_lib.INPUT_LABEL_FALLBACK)
        ref_name = self._rule_ref_line_name(parts.get("ref_slug"))
        if parts.get("input_found") and parts.get("input_value") is not None:
            shown_value = self._rule_input_display(parts)
            if ref_name:
                left = 'của dòng "%s" = %s' % (ref_name, shown_value)
                left = "%s %s" % (field_label, left)
            else:
                left = "%s = %s" % (field_label, shown_value)
        else:
            # Chưa có giá trị đầu vào: nêu nhãn dữ liệu đem tra, ⛔ bịa "= 0".
            left = "theo %s" % field_label
        resolved = parts.get("resolved")
        if not resolved:
            return '%s → không có mã nào khớp · %s.' % (left, tail)
        item_name = self._item_names.get(resolved) or ""
        target = ('"%s" (%s)' % (item_name, resolved)) if item_name \
            else ('"%s"' % resolved)
        return '%s → %s · %s.' % (left, target, tail)

    def _rule_trace_text_raw(self, parts):
        """Dữ liệu kỹ thuật (support) — GIỮ NGUYÊN dạng cũ.

        §7.6: có `input_missing` ⇒ giá trị hiện `(chưa có nguồn)` thay cho
        "None", để support phân biệt "ô trống" với "chưa chọn dòng nguồn".
        ⛔ Không đổi hợp đồng các key khác của chuỗi.
        """
        if not parts:
            return ""
        ref_slug = parts.get("ref_slug") or ""
        ref_field = parts.get("ref_field") or ""
        if ref_slug and ref_field:
            lhs = "items.%s.%s" % (ref_slug, ref_field)
        elif parts.get("input_variable"):
            lhs = parts.get("input_variable")
        else:
            return ""
        target = parts.get("resolved") or "(không khớp)"
        value = ("(chưa có nguồn)" if (parts.get("input_missing")
                                      and not parts.get("input_found"))
                 else self._trace_value(parts.get("input_value")))
        return "%s = %s → %s → %s" % (
            lhs, value, parts.get("rule_code"), target)

    def _build_rule_trace(self, item):
        """Câu chọn mã cho người đọc (dòng Fixed / không Rule → "")."""
        if item.get("item_selection_mode") != "Rule" or not item.get("item_rule"):
            return ""
        return self._rule_trace_text(self._rule_trace_parts(item))

    def _build_rule_trace_raw(self, item):
        if item.get("item_selection_mode") != "Rule" or not item.get("item_rule"):
            return ""
        return self._rule_trace_text_raw(self._rule_trace_parts(item))

    # ── Vết "quy tắc tính số lượng" (qty formula dạng đơn giản) ──────
    #: qty = lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel — người đọc cần
    #: thấy "chiều cao → mấy bản lề/cánh → nhân số cánh = tổng" ngay trong
    #: bước "Tính số lượng" của hộp giải thích giá. CHỈ dựng khi công thức
    #: khớp ĐÚNG dạng đơn giản (1 lời gọi, tham số là biến/số); dạng phức tạp
    #: ⇒ để trống (⛔ đoán số).
    def _qty_rule_trace(self, slug, qty_value, trace_ctx):
        """Trả `(chuỗi hiển thị, chuỗi kỹ thuật)`; ("", "") khi không khớp dạng."""
        expr = (self._line_formulas.get(slug, {}) or {}).get("qty") or ""
        expr = str(expr).strip()
        if not expr:
            return "", ""
        match = _QTY_RULE_SIMPLE_RE.match(expr)
        if not match:
            return "", ""
        code = (match.group("code") or "").strip()
        input_token = match.group("input")
        mult_token = match.group("mult")

        try:
            rule_doc = frappe.get_cached_doc("AL Rule", code)
        except Exception:
            # Rule không tồn tại / không đọc được ⇒ ⛔ bịa tên quy tắc.
            return "", ""

        config = rule_input_lib.rule_input_config(rule_doc)
        if not input_token:
            # Chặng 3: `lookup_rule('MÃ')` MỘT tham số — chỉ giải thích được
            # khi quy tắc khai biến TOÀN CỤC (engine tự chèn biến đó). Quy
            # tắc ROW/chưa khai ⇒ ⛔ đoán, để trống vết.
            if (config.get("input_scope") != rule_input_lib.GLOBAL_SCOPE
                    or not config.get("input_variable")):
                return "", ""
            input_token = config["input_variable"]

        input_value = self._qty_token_value(input_token, trace_ctx)
        mult_value = self._qty_token_value(mult_token, trace_ctx)
        rule_name = (rule_doc.get("rule_name") or "").strip()

        # Kết quả rule: chỉ khi quy tắc ĐANG BẬT và trả SỐ. Rule tắt / trả mã
        # vật tư ⇒ KHÔNG hiện số (cảnh báo đã có ở banner engine), ⛔ bịa.
        rule_value = None
        if (rule_engine.rule_is_active(rule_doc)
                and (rule_doc.get("result_type") or "") == "NUMBER"):
            rule_value = rule_doc.resolve(input_value)

        head = ('Chọn số lượng theo quy tắc "%s"' % rule_name) if rule_name \
            else "Chọn số lượng theo quy tắc"

        input_label = (rule_doc.get("input_label") or "").strip()
        if not input_label:
            input_label = (config.get("input_label") or "").strip()
        if not input_label:
            input_label = self._qty_token_label(input_token)
        # Nhãn có thể là chính TÊN BIẾN (dữ liệu cũ điền tay / biến chưa có
        # nhãn) — câu trace đi ra client ⇒ dùng hàm đọc-được DÙNG CHUNG,
        # ⛔ phơi `input_token` trần.
        input_label = rule_input_lib.readable_input_label(
            input_label, input_token or config.get("input_variable") or "")
        input_text = self._qty_input_text(
            input_token, input_value, input_label,
            (rule_doc.get("input_unit") or "").strip())

        display = "%s: %s" % (head, input_text)
        if rule_value is not None:
            display += " → %s" % _format_number_vi(rule_value)
            if mult_token:
                if _SIMPLE_NUMBER_TOKEN_RE.match(mult_token):
                    display += " × %s" % _format_number_vi(mult_value)
                else:
                    mult_label = self._qty_token_label(mult_token)
                    display += " × %s" % _lower_first(mult_label)
                    if mult_value is not None:
                        display += " %s" % _format_number_vi(mult_value)
                if mult_value is not None and qty_value is not None:
                    display += " = %s" % _format_number_vi(qty_value)
        display += "."

        raw_parts = [
            "%s=%s" % (input_token, self._trace_value(input_value)),
            "rule=%s" % self._trace_value(rule_value),
            "qty=%s" % self._trace_value(qty_value),
        ]
        if mult_token:
            raw_parts.insert(1, "%s=%s" % (
                mult_token, self._trace_value(mult_value)))
        return display, "%s → %s" % (expr, ", ".join(raw_parts))

    @staticmethod
    def _qty_token_value(token, trace_ctx):
        """Giá trị của token biến/số lấy từ `_trace_ctx`; None nếu không có."""
        if not token:
            return None
        if _SIMPLE_NUMBER_TOKEN_RE.match(token):
            return float(token)
        value = (trace_ctx or {}).get(token)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return value

    def _qty_token_label(self, token):
        """Nhãn người đọc của token: `AL Variable Library` → `display_label`."""
        if not token or _SIMPLE_NUMBER_TOKEN_RE.match(token):
            return ""
        labels = getattr(self, "_var_labels", None)
        if labels is None:
            labels = self._percent_var_metadata()[1]
            self._var_labels = labels
        return (labels.get(token) or "").strip() or display_label(token) or token

    @staticmethod
    def _qty_input_text(token, value, label, unit):
        """Vế "Chiều cao = 3.200 mm" / "theo Chiều cao" (khi thiếu giá trị)."""
        if _SIMPLE_NUMBER_TOKEN_RE.match(token or ""):
            return _format_number_vi(value)
        label = label or token or ""
        if value is None:
            return "theo %s" % label
        if unit and "(" not in label:
            return "%s = %s" % (label, _format_number_vi(value, " " + unit))
        return "%s = %s" % (label, _format_number_vi(value))

    # ── Giá: 2 dạng (raw kỹ thuật / hiển thị nghiệp vụ) ─────────────
    def _build_price_trace_raw(self, item, lit):
        """Dữ liệu kỹ thuật (support): mã + bảng giá + docname Item Price."""
        if item.get("unit_price") not in (None, "", 0):
            return "Giá nhập tay trên dòng '%s': %s" % (
                item.get("slug") or "",
                self._trace_value(item.get("unit_price")))
        price_code, display_code, price_base_item = self._price_code_for_trace(
            item, lit)
        if not price_code:
            return ""
        price = lit.get("unit_price", 0) or 0
        info = getattr(self, "_price_info", {}).get(price_code) or {}
        parts = ["Mã '%s'" % price_code]
        if price_base_item and display_code and price_base_item != display_code:
            parts.append("giá tra theo mã đại diện '%s'" % price_base_item)
        if info.get("price_list"):
            parts.append("bảng giá '%s'" % info.get("price_list"))
        if info.get("row_name"):
            parts.append("dòng Item Price '%s'" % info.get("row_name"))
        parts.append("giá %s" % self._trace_value(price))
        return " · ".join(parts)

    def _build_price_trace(self, item, lit):
        """Câu tra giá cho người đọc — không docname, không mã enum."""
        if item.get("unit_price") not in (None, "", 0):
            return "Giá nhập tay: %s" % _format_money_vi(
                item.get("unit_price"))
        price_code, display_code, price_base_item = self._price_code_for_trace(
            item, lit)
        if not price_code:
            return ""
        price = lit.get("unit_price", 0) or 0
        info = getattr(self, "_price_info", {}).get(price_code) or {}

        parts = []
        price_list = self._price_list_display(info.get("price_list"))
        if price_list:
            parts.append('Bảng giá "%s"' % price_list)
        parts.extend(self._dimension_values_display(info))
        if price_base_item and display_code and price_base_item != display_code:
            base_name = self._item_names.get(price_base_item) or price_base_item
            parts.append('Giá tra theo mã đại diện "%s"' % base_name)

        if info.get("multiplier") is not None \
                and info.get("base_price") is not None:
            parts.append("giá gốc %s × hệ số %s = %s" % (
                _format_money_vi(info.get("base_price")),
                _format_number_vi(info.get("multiplier")),
                _format_money_vi(price)))
            return " · ".join(parts)
        # Câu KHỚP: kể đúng nhánh engine đã chạy để ra dòng giá này.
        match_sentence = self._price_match_sentence(info)
        if match_sentence:
            parts.append(match_sentence)
        if info.get("row") or price:
            parts.append("giá %s" % _format_money_vi(price))
        else:
            # Câu cảnh báo, KHÔNG phải "giá 0 đ" — người dùng phải thấy đây
            # là số tạm và biết chỗ sửa. Tên bảng giá đã resolve (nếu có).
            warning = (
                "%s — đang tạm tính 0 đ, thành tiền chưa đúng." %
                ZERO_PRICE_TRACE_PREFIX)
            if price_list:
                warning += ' Kiểm tra bảng giá "%s" hoặc báo quản trị.' % (
                    price_list)
            else:
                warning += " Báo quản trị để bổ sung giá."
            parts.append(warning)
        return " · ".join(parts)


    def b4_calculate_bom_items(self):
        from formula_builder.formula_utils.engine_public import FormulaEngine
        from alumglass.engine.engine_cache import BOM_ENGINE_CACHE, make_key

        # Cache engine theo NỘI DUNG công thức: cùng một BOM thì công thức y hệt
        # nhau dù sản phẩm khác kích thước/đầu vào ⇒ khỏi biên dịch lại DAG cho
        # từng dòng báo giá. Khởi tạo engine chiếm 97 % thời gian ở bước này.
        # Sửa công thức trong Bom Item ⇒ vân tay đổi ⇒ tự dựng engine mới.
        engine = BOM_ENGINE_CACHE.get_or_build(
            make_key(
                "bom_items", self.bom_formulas, "bom_safe_funcs_v1",
                on_error="default", default_value=0, deterministic=True,
            ),
            lambda: FormulaEngine(
                formulas=self.bom_formulas,
                safe_funcs=_engine_safe_funcs(),
                on_error="default",
                default_value=0,
                deterministic=True,
            ),
        )

        result = engine.calculate(dict(self.inputs))
        # B5 FB-max: thu thập lỗi structured — 1 dòng lỗi KHÔNG chết cả BOM.
        # Div-by-zero vẫn fatal (errors.py) → phải chặn ở nguồn data.
        # F2/D9: MERGE (không gán đè) — cảnh báo đã ghi từ B2 (tra giá/rule)
        # nằm trong self.bom_engine_errors phải được giữ lại.
        self.bom_engine_errors.update(
            self._readable_formula_errors(engine.last_errors))
        # Cảnh báo phát sinh TRONG lúc engine tính (lookup_rule thiếu mã...) —
        # hút về túi BOM trước khi ghi kết quả.
        self._drain_engine_warnings()
        self.inputs.update(result)

        # 2026-09 (nâng cấp #3): validate diện tích kính đã tính KHÔNG vượt
        # khổ tối đa nhà cung cấp (AL Glass Master.max_area_m2) — tránh báo
        # giá 1 sản phẩm không sản xuất được (kính quá khổ phải ghép/đổi độ
        # dày). CHỈ WARN (structured error, không throw) — không chặn tính
        # toán, vì có thể admin đã biết và chủ động chấp nhận đặt hàng riêng.
        self._validate_glass_max_area(result)

        # V6 P8 (Phase 1e): batch-fetch output_unit theo calc_pattern (cho cột
        # ĐVT = output_unit của AL Quantity Calc Method).
        pattern_codes = list({
            item.get("calc_pattern", "") for item in self.bom_items
            if item.get("calc_pattern")})
        pattern_units = {}
        pattern_names = {}
        if pattern_codes:
            for pu in frappe.get_all(
                    "AL Quantity Calc Method",
                    filters={"name": ("in", pattern_codes)},
                    fields=["name", "output_unit", "calc_pattern_name"]):
                pattern_units[pu["name"]] = pu.get("output_unit", "") or ""
                pattern_names[pu["name"]] = pu.get("calc_pattern_name", "") or ""

        # Build bom_result
        # V6 P8: ctx = inputs đã merge kết quả → build trace line vật tư
        # (width/height/qty formula → thay biến → kết quả).
        self.bom_result = []
        _trace_ctx = dict(self.inputs)
        items_by_slug = {it.get("slug"): it for it in self.bom_items}
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
            is_glass_row = item.get("category") in getattr(
                self, "_glass_categories", set())
            # Phase 2 (UX): dựng CẢ 2 dạng vết — chuỗi hiển thị (nhãn nghiệp
            # vụ) và dữ liệu kỹ thuật `*_raw` (support đối chiếu). API/client
            # chỉ dùng chuỗi hiển thị.
            is_rule_row = (item.get("item_selection_mode") == "Rule"
                           and bool(item.get("item_rule")))
            rule_parts = self._rule_trace_parts(item) if is_rule_row else {}
            rule_trace = (self._rule_trace_text(rule_parts)
                          if is_rule_row else "")
            rule_trace_raw = (self._rule_trace_text_raw(rule_parts)
                              if is_rule_row else "")
            # §7.6: `rule_input_missing` = chưa khai gì cả; `rule_source_missing`
            # = ĐÃ khai nhưng thiếu nguồn (hai trạng thái, hai câu khác nhau).
            rule_flags = self._rule_source_flags(rule_parts, is_rule_row)
            # Mã vật tư của dòng Rule CHỈ lấy từ kết quả resolve (§7.6 điểm 3):
            # ⛔ slug, ⛔ mã giữ chỗ của dòng khác, ⛔ số 0 giả. Client hiện
            # "Chưa tra được mã" và vẫn mở được hộp giải thích.
            if is_rule_row:
                item_code_resolved = rule_parts.get("resolved") or ""
            else:
                item_code_resolved = (lit.get("item_code")
                                      or item.get("item_code") or "")

            # Vết "quy tắc tính số lượng": chỉ có khi `qty`/`qty_formula` là
            # dạng đơn giản `lookup_rule('MÃ', INPUT) [* MULT]`. Dòng không
            # dùng dạng đó ⇒ chuỗi rỗng (API ⛔ thêm bước giải thích).
            qty_value = result.get(f"{slug}__qty")
            qty_rule_trace, qty_rule_trace_raw = self._qty_rule_trace(
                slug, qty_value, _trace_ctx)

            # "Dòng này có dùng dữ liệu kính không" — dòng nhôm/phụ kiện ⛔
            # không có bước nguồn kính trong hộp giải thích. Rule đọc thông số
            # của dòng kính (rule_input_expr trỏ `items.<slug>.<field>`) ⇒ có.
            glass_used = is_glass_row
            if not glass_used and is_rule_row:
                ref_item = items_by_slug.get(rule_parts.get("ref_slug") or "")
                glass_used = bool(
                    ref_item
                    and ref_item.get("category") in self._glass_categories)

            price_code, _display_code, price_base_item = (
                self._price_code_for_trace(item, lit))

            self.bom_result.append({
                "slug": slug,
                "item_code": item_code_resolved,
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
                # Q2: cột hiển thị mới trong Preview — màu sắc (đã resolve
                # theo vị trí nếu dòng tham gia nhóm màu), nơi cấp vật tư,
                # vị trí lắp đặt, góc cắt, ghi chú (khai báo tĩnh trên
                # AL Bom Item/AL Accessory Item).
                "color": lit.get("color", ""),
                "supplier_location": lit.get("supplier_location", ""),
                "install_position": lit.get("install_position", ""),
                "cut_angle": lit.get("cut_angle", ""),
                "note": lit.get("note", ""),
                # Phase 2 (2026-11-20): vết tra cứu + dữ liệu để API
                # `explain_bom_line` giải thích mà KHÔNG tính lại engine.
                # Tất cả additive — client cũ bỏ qua key lạ.
                # `rule_trace`/`price_trace` = chuỗi HIỂN THỊ (đã resolve nhãn);
                # `*_raw` = dữ liệu KỸ THUẬT cho support (⛔ không hiển thị).
                "item_name": self._item_names.get(item_code_resolved) or "",
                "line_label": (
                    item.get("line_name")
                    or self._item_names.get(item_code_resolved)
                    or lit.get("glass_name")
                    or ""),
                "item_selection_mode": item.get("item_selection_mode", "") or "",
                "rule_trace": rule_trace,
                "rule_trace_raw": rule_trace_raw,
                "rule_name": rule_parts.get("rule_name") or "",
                "rule_match": rule_parts.get("match") or "",
                # Nhãn tự mô tả của quy tắc (additive; rule cũ ⇒ rỗng).
                # `explain_bom_line` nối `rule_description` vào bước giải
                # thích; `input_label`/`output_label` cho client hiển thị.
                "rule_description": rule_parts.get("rule_description") or "",
                "rule_input_label": rule_parts.get("input_label") or "",
                "rule_output_label": rule_parts.get("output_label") or "",
                # Căn cứ SỐ LƯỢNG khi qty formula dùng `lookup_rule(...)`
                # dạng đơn giản — bước "Quy tắc tính số lượng" của
                # `explain_bom_line`. Rỗng với công thức khác.
                "qty_rule_trace": qty_rule_trace,
                "qty_rule_trace_raw": qty_rule_trace_raw,
                # §7.6 — cờ trạng thái nguồn tra của dòng (xem
                # `_rule_source_flags`): `rule_input_missing` = chưa khai gì
                # cả; `rule_source_missing` = đã khai nhưng thiếu nguồn;
                # `rule_missing_reason` = no_source_row | row_gone |
                # row_no_data | no_global_value.
                "rule_input_missing": rule_flags["rule_input_missing"],
                "rule_source_missing": rule_flags["rule_source_missing"],
                "rule_missing_reason": rule_flags["rule_missing_reason"],
                "rule_input_found": rule_flags["rule_input_found"],
                "price_trace": self._build_price_trace(item, lit),
                "price_trace_raw": self._build_price_trace_raw(item, lit),
                # Sự thật tra cứu của ĐÚNG dòng này — API `explain_bom_line`
                # dựng câu giải thích từ đây (⛔ không khuôn cố định):
                # `code_source` (rule | price_base_item | item_code |
                # manual_price), `price_match` (composite | base_row |
                # multiplier_chain | plain_row | none), `match_dims`
                # [{label, display, matched}], `glass_used`.
                "price_base_item": price_base_item or "",
                "lookup_facts": self._build_lookup_facts(
                    item, price_code, price_base_item, glass_used),
                "calc_pattern": item.get("calc_pattern", "") or "",
                "calc_pattern_name": pattern_names.get(
                    item.get("calc_pattern", ""), "") or "",
                "scrap_pct": lit.get("scrap_pct", 0) or 0,
                # Nguồn giá trị kính của CHÍNH dòng: dòng kính ⇒ mã kính đã
                # resolve + thông số đọc từ AL Glass Master; dòng khác ⇒
                # rỗng (API tự suy từ dòng kính mà rule_input_expr trỏ tới).
                "glass_master": (
                    lit.get("item_code", "") if is_glass_row else ""),
                "glass_master_name": (
                    lit.get("glass_name", "") if is_glass_row else ""),
                "glass_type_name": lit.get("glass_type_name", "") or "",
                # `glass_thick` = alias cũ, lưu SONG SONG với `total_thick_mm`
                # để API giải thích đọc được cả dữ liệu mới lẫn cũ.
                "glass_thick": lit.get("glass_thick", 0) or 0,
                "total_thick_mm": lit.get("glass_thick", 0) or 0,
                "glass_type": lit.get("glass_type", "") or "",
                "max_area_m2": lit.get("max_area_m2", 0) or 0,
                # Cờ nhận biết dòng kính — API dùng để KHÔNG nói sai
                # "dòng này không dùng dữ liệu kính" khi thực ra là dòng kính
                # nhưng chưa chọn kính.
                "is_glass_row": 1 if is_glass_row else 0,
            })

    def _validate_glass_max_area(self, result):
        """2026-09 (nâng cấp #3): so diện tích đã tính (`{slug}__unit_qty`,
        đơn vị m² — đúng cho mọi dòng category kính vì `calc_pattern` của
        category kính luôn là pattern nhóm B-Diện tích, xem
        `AL Material Category.default_calc_pattern`) với
        `AL Glass Master.max_area_m2` của kính đang dùng cho dòng đó.

        Data-driven: KHÔNG hardcode tên calc_pattern — chỉ dựa vào
        `self._glass_categories` (đã build ở B2 qua `requires_glass_master`,
        giống hệt cách `glass_data`/`_glass_categories` dùng ở nơi khác) và
        `self._glass_data[slug]["max_area_m2"]` (0 = glass master chưa khai
        max_area_m2 → bỏ qua, không false-positive).

        CHỈ ghi WARNING vào `self.bom_engine_errors` (không throw) — người
        dùng vẫn thấy giá, nhưng biết rõ cấu hình đang vượt khổ kính tiêu
        chuẩn nhà cung cấp, cần xác nhận lại trước khi chốt đơn.
        """
        for item in self.bom_items:
            slug = item.get("slug", "")
            if not slug or item.get("category") not in self._glass_categories:
                continue
            max_area = self._glass_data.get(slug, {}).get("max_area_m2", 0) or 0
            if not max_area:
                continue  # glass master chưa khai max_area_m2 → bỏ qua
            area = result.get(f"{slug}__unit_qty", 0) or 0
            if area > max_area:
                self.bom_engine_errors[f"{slug}__max_area_exceeded"] = (
                    "Diện tích tấm kính '%s' = %.3f m² VƯỢT khổ tối đa %.3f m² "
                    "của kính đang chọn — kiểm tra lại kích thước hoặc đổi "
                    "cấu hình (chia khung/ghép kính)." % (slug, area, max_area)
                )

    # ══════════════════════════════════════════════════════════════════
    # B5: Aggregate Cost Buckets — gom line_total theo cost_bucket
    # ══════════════════════════════════════════════════════════════════
    def b5_aggregate_cost_buckets(self):
        """Gom line_total theo cost_bucket (đọc từ Bom Item, không hardcode).

        B3 FB-max: LEAF bucket có source_type='aggregate_from_items' + source_config
        hợp lệ → resolve qua FB aggregate_from_items (sum theo key_field giống sumif,
        rows_source='resolved', rows_var='rows' — engine đặt pre_resolved['rows'],
        KHÔNG phải 'bom_result'). AGGREGATE bucket do B6 tính.
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
        qua FB aggregate_from_items (rows_source='resolved', rows_var='rows' —
        engine truyền pre_resolved['rows'] = [{cost_bucket, line_total}];
        rows_var='bom_result' là SAI, handler sẽ đọc không thấy và trả 0).

        `source_config` gửi sang FB dưới dạng JSON string (đúng contract).

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
        except Exception as exc:
            # D9: không có FB resolver → fallback sum Python (luồng không đổi),
            # nhưng ghi log để lỗi không biến mất.
            frappe.log_error(
                title="AlumGlass: không import được resolve_all_bindings_batch (B5)",
                message="Quotation Item %s — %s" % (self.quotation_item_name, exc))
            return {}

        # Đọc source_type/source_config từ AL Cost Bucket (vocabulary hiện có)
        try:
            records = frappe.get_all(
                "AL Cost Bucket",
                filters={"bucket_code": ("in", bucket_codes)},
                fields=["bucket_code", "bucket_role", "source_type", "source_config"],
            ) or []
        except Exception as exc:
            frappe.log_error(
                title="AlumGlass: đọc AL Cost Bucket lỗi (B5)",
                message="Quotation Item %s — %s" % (self.quotation_item_name, exc))
            return {}

        bindings = []
        for rec in records:
            if rec.get("source_type") != "aggregate_from_items":
                # F10: bucket khai source_type engine CHƯA hỗ trợ trước đây bị bỏ
                # qua im lặng (rơi về sum Python, không rõ vì sao). CHỈ cảnh báo
                # khi bucket CÓ khai source_type — bucket không khai (rỗng) là
                # trường hợp mặc định, vẫn sum line_total như cũ.
                if rec.get("source_type"):
                    _record_engine_warning(
                        "bucket_source_type_chua_ho_tro:%s" % rec.get("bucket_code"),
                        "Cost Bucket '%s' khai source_type '%s' chưa được engine "
                        "hỗ trợ (chỉ hỗ trợ 'aggregate_from_items') — tạm gom "
                        "bằng tổng line_total như cũ."
                        % (rec.get("bucket_code"), rec.get("source_type"))
                    )
                continue
            cfg_raw = rec.get("source_config") or ""
            cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) and cfg_raw.strip() else (
                cfg_raw if isinstance(cfg_raw, dict) else {})
            if not isinstance(cfg, dict) or not cfg:
                continue  # chưa có source_config → fallback sum Python
            binding = {
                "variable_name": rec["bucket_code"],
                "source_type": "aggregate_from_items",
                # Contract của Formula Builder: source_config là JSON STRING
                # (giống row FVB trong DB). Truyền dict Python ở đây làm
                # resolver json.loads(dict) → ném lỗi → cả nhóm binding rơi
                # về default ⇒ setting vô hiệu mà vẫn ra đúng số nhờ fallback.
                "source_config": json.dumps(cfg, ensure_ascii=False),
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
        except Exception as exc:
            # D9: lỗi resolve bucket qua FB → vẫn fallback sum Python như cũ,
            # nhưng ghi log để không biến mất.
            frappe.log_error(
                title="AlumGlass: resolve cost bucket qua FB lỗi (B5)",
                message="Quotation Item %s — %s" % (self.quotation_item_name, exc))
            return {}
        return {
            name: val for name, val in resolved.items()
            if isinstance(val, (int, float))
        }

    # ══════════════════════════════════════════════════════════════════
    # B6: Calculate Cost Template — dùng FormulaEngine (FB), có cache theo BOM
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
                    # D7: cờ dòng "giá trước VAT" (al_gia_ban) — xem
                    # _resolve_pre_vat_price. Mặc định 0 = fallback cũ.
                    "is_pre_vat_price": i.get("is_pre_vat_price", 0),
                } for i in ct.items],
            }
        elif not self.bom_version or not self.bom_version.cost_template_snapshot:
            return
        else:
            snap = json.loads(self.bom_version.cost_template_snapshot) if isinstance(
                self.bom_version.cost_template_snapshot, str
            ) else self.bom_version.cost_template_snapshot

        # D7: giữ items snapshot đang dùng để resolve dòng giá sau (sau khi
        # tính cost_result). snapshot cũ (pre-D7) thiếu is_pre_vat_price →
        # item.get trả 0 → fallback GIA_VAT/GIA_BAN (golden-safe).
        self._cost_template_snapshot_items = snap.get("items", []) or []

        from formula_builder.formula_utils.engine_public import FormulaEngine
        from alumglass.engine.engine_cache import COST_ENGINE_CACHE, make_key

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

        # ⛔ KHÔNG còn dùng FlexibleFormulaEngine ở đây.
        # VÌ SAO BỎ ĐƯỢC: FFE chỉ hơn FormulaEngine ở 4 tính năng, và cả 4 đều
        # thuộc đường `child_tables` — nhúng giá trị cột vào công thức
        # (`_inject_row_values`), ghi kết quả ngược vào dòng (`_write_back`),
        # lượt tính thứ hai cho công thức đọc-dòng (`_second_pass_formulas`), và
        # `multi_scenario`. B6 KHÔNG cấu hình `child_tables` ⇒
        # `_build_all_formulas()` trả về ĐÚNG `global_formulas` nguyên vẹn,
        # `_write_back` không có dòng nào để ghi, và `_second_pass_formulas`
        # rỗng nên FFE thoát sớm — tức là FFE chỉ chuyển tiếp rồi trả lại đúng
        # kết quả của FormulaEngine bên trong. Đối chứng A/B trên chính dạng B6:
        # cùng giá trị, cùng số khoá, cùng nhánh lỗi.
        # Đổi lại được: bỏ được một lượt dựng engine phụ mỗi lần tính, và
        # `result.errors` (CalculationResult) → `engine.last_errors` (lõi 31.x
        # trả thẳng `engine.last_errors.copy()`, xem `_collect_errors` của FFE).

        # Context = extra_context ⊕ inputs, ĐÚNG như FFE vẫn hợp nhất
        # (`context = {**extra_context, **inputs}`).
        # 🔴 ĐỪNG rút gọn thành `self.inputs`: `extra_context` còn mang
        # `self.buckets` + default 0 cho mã bucket được tham chiếu (dựng ngay
        # trên). Chỉ truyền inputs là MẤT SẠCH bucket ⇒ giá sai âm thầm, ⛔ không
        # có exception nào.
        engine = COST_ENGINE_CACHE.get_or_build(
            make_key(
                "cost_template", global_formulas, "bom_safe_funcs_v1",
                on_error="default", default_value=0, deterministic=True,
            ),
            lambda: FormulaEngine(
                formulas=global_formulas,
                safe_funcs=_engine_safe_funcs(),
                on_error="default",
                default_value=0,
                deterministic=True,
            ),
        )
        result = engine.calculate({**extra_context, **self.inputs})

        values = result
        self.cost_result = dict(values)
        # V6 P10/D7: không hardcode line_code "GIA_VAT" nữa — dòng nào có
        # is_final_price=1 trong snapshot (config hiện tại) là giá bán cuối.
        # Không có dòng flag → fallback "GIA_VAT" (hành vi cũ, golden-safe).
        self.gia_vat = self._resolve_final_price()
        # B5 FB-max: lỗi structured từ cost template — lưu trong al_bom_result.
        self.cost_engine_errors = self._readable_formula_errors(
            engine.last_errors)
        # F2/D9: cảnh báo phát sinh khi tính cost template (lookup_rule thiếu mã
        # trong calc_formula...) → túi cost_template, không bỏ rơi.
        self._drain_engine_warnings(bag=self.cost_engine_errors)

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
    # D7 (V6 P10): resolve giá từ snapshot cost template theo CỜ — không
    # hardcode line_code. Flag tương ứng trên AL Cost Template Item:
    #   - is_final_price   =1 → dòng giá bán cuối (al_gia_vat / self.gia_vat)
    #   - is_pre_vat_price =1 → dòng giá trước VAT (al_gia_ban)
    # Nếu KHÔNG có dòng nào flag (config cũ / snapshot cũ pre-flag) → fallback
    # line_code cũ ("GIA_VAT"/"GIA_BAN") — 100% hành vi trước đây (golden-safe).
    # Dùng items snapshot ĐANG tính (b6 đã set `_cost_template_snapshot_items`
    # từ nhánh override lẫn nhánh version snapshot).
    # ══════════════════════════════════════════════════════════════════
    def _resolve_final_price(self):
        """Giá bán cuối (gia_vat): dòng is_final_price=1 → line_code trong
        cost_result; không có flag → fallback cost_result["GIA_VAT"] (cũ)."""
        for item in self._cost_template_snapshot_items:
            if item.get("is_final_price"):
                code = item.get("line_code", "")
                if code and code in self.cost_result:
                    return self.cost_result.get(code, 0)
        return self.cost_result.get("GIA_VAT", 0)

    def _resolve_pre_vat_price(self):
        """Giá trước VAT (al_gia_ban): dòng is_pre_vat_price=1 → line_code
        trong cost_result; không có flag → fallback cost_result["GIA_BAN"] (cũ)."""
        for item in self._cost_template_snapshot_items:
            if item.get("is_pre_vat_price"):
                code = item.get("line_code", "")
                if code and code in self.cost_result:
                    return self.cost_result.get(code, 0)
        return self.cost_result.get("GIA_BAN", 0)

    # ══════════════════════════════════════════════════════════════════
    # B7: Save Results — SINGLE commit (B1 fix)
    # ══════════════════════════════════════════════════════════════════
    def b7_save_results(self):
        if not self.persist:
            # Lưới an toàn thứ hai: đường preview ⛔ tuyệt đối không ghi DB,
            # kể cả khi ai đó gọi thẳng b7 (run() đã bỏ qua bước này).
            return
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
            # D7: giá trước VAT resolve theo cờ is_pre_vat_price (fallback
            # GIA_BAN) — lưu kèm để get_result_display hiện ĐÚNG giá mà engine
            # đã ghi al_gia_ban (không hardcode lại line_code).
            "gia_ban": self._resolve_pre_vat_price(),
            "errors": {
                "bom_items": self.bom_engine_errors,
                "cost_template": self.cost_engine_errors,
            },
        }
        result_json = json.dumps(full_result, indent=2, default=str)

        # V5 (Owner): ConfigSnapshot CHỈ tạo khi submit Quotation (doc_events on_submit),
        # KHÔNG tạo mỗi lần tính toán. Đây là scope được Owner cho phép chạm engine —
        # chỉ bỏ phần ghi snapshot, KHÔNG đụng logic tính (B1-B5, cost engine, golden 2C/4C).
        # Chốt docstatus SÁT lệnh ghi nhất có thể: bắt cả trường hợp job nền đang chạy
        # mà báo giá bị submit giữa chừng (queue long timeout 600s — khoảng đua là thật).
        assert_quotation_item_editable(self.quotation_item_name)

        # F8: `rate` (trường chuẩn ERPNext dùng tính tổng tiền báo giá) trước
        # đây CHỈ trình duyệt ghi — trình duyệt chết/mất mạng sau khi máy chủ
        # ghi xong mà trước khi kịp ghi rate ⇒ dòng có al_gia_ban MỚI nhưng
        # rate CŨ ⇒ in/gửi khách sai giá. Giờ máy chủ ghi luôn rate = giá
        # trước VAT (CÙNG giá trị client quotation.js ghi: rate = GIA_BAN).
        pre_vat_price = self._resolve_pre_vat_price()

        # Ghi kết quả vào Quotation Item (1 lần set_value gộp multi-field)
        frappe.db.set_value("Quotation Item", self.quotation_item_name, {
            "al_gia_vat": self.gia_vat,
            "al_gia_ban": pre_vat_price,
            "al_bom_result": result_json,
            "rate": pre_vat_price,
        })

        # F8: ghi rate mà không tính lại tổng ⇒ tổng tiền báo giá CŨ, in ra
        # sai. Tính lại tổng của Quotation cha rồi ghi bằng set_value(
        # update_modified=False) — KHÔNG save() cha (Bẫy 1: đụng modified của
        # cha gây TimestampMismatchError lần Save sau).
        self._recalculate_quotation_totals(pre_vat_price)

        # B1 fix: 1 commit duy nhất
        frappe.db.commit()

    def _recalculate_quotation_totals(self, pre_vat_price):
        """F8 — ghi rate rồi tính lại tổng tiền Quotation cha (KHÔNG save cha).

        ⛔ Không gọi parent.save()/submit()/db_update()/db_set(): save() chạy
        validate + document event và cập nhật `modified` của cha — đã từng gây
        TimestampMismatchError khi user Save lần sau. Ở đây chỉ set_value các
        trường tổng với update_modified=False, cùng 1 commit duy nhất ở
        b7_save_results. Nạp cha / tính tổng thất bại ⇒ log_error rồi ĐỂ LỖI
        NỔI LÊN (trạng thái nửa vời — giá mới, tổng cũ — nguy hiểm hơn báo lỗi).
        """
        parent_name = frappe.db.get_value(
            "Quotation Item", self.quotation_item_name, "parent")
        if not parent_name:
            frappe.log_error(
                title="AlumGlass: không tìm thấy Quotation cha để tính lại tổng",
                message="Quotation Item %s" % self.quotation_item_name)
            frappe.throw(
                "Không tìm thấy báo giá cha của dòng %s để tính lại tổng tiền."
                % self.quotation_item_name)

        try:
            parent = frappe.get_doc("Quotation", parent_name)

            # Gán rate mới cho ĐÚNG dòng đang tính trong bộ nhớ (chỉ dòng này).
            updated_row = False
            for row in parent.get("items") or []:
                if row.name == self.quotation_item_name:
                    # Làm tròn rate về ĐÚNG precision của field (currency
                    # precision của site) — round_floats_in trong
                    # calculate_item_values sẽ làm tròn y như vậy; giữ số thô
                    # thì lưới an toàn phía dưới sẽ báo lỗi GIẢ.
                    rate_precision = row.precision("rate")
                    row.rate = frappe.utils.flt(pre_vat_price, rate_precision)
                    # F8-bis: vô hiệu hoá TRONG BỘ NHỚ các field ERPNext dùng
                    # để tự tính lại `rate` trong calculate_item_values
                    # (taxes_and_totals.py:176). Nếu không, ca price_list_rate
                    # > 0 + rate = 0 sẽ âm thầm thay giá hệ thống bằng giá
                    # bảng. Đây là doc dùng một lần rồi vứt — ⛔ KHÔNG ghi 5
                    # field này xuống DB (danh sách totals vẫn đúng 13 field).
                    row.price_list_rate = 0
                    row.discount_percentage = 0
                    row.discount_amount = 0
                    row.margin_type = None
                    row.margin_rate_or_amount = 0
                    updated_row = True
                    break
            if not updated_row:
                frappe.throw(
                    "Không tìm thấy dòng %s trong báo giá %s để tính lại tổng "
                    "tiền." % (self.quotation_item_name, parent_name))

            # Tính lại thuế/tổng/rounded. in_words/base_in_words chỉ được
            # validate() set nên phải gọi tường minh.
            parent.calculate_taxes_and_totals()

            # Lưới an toàn: nếu sau khi tính tổng mà rate của dòng bị đổi (còn
            # đường ghi đè nào lọt qua, ví dụ Pricing Rule ở v16), thì DỪNG và
            # kêu to thay vì âm thầm ghi tổng theo giá khác giá hiển thị.
            # So sánh SAU khi đưa CẢ HAI VỀ CÙNG precision của field rate —
            # round_floats_in đã làm tròn row.rate, so số thô sẽ báo giả.
            if frappe.utils.flt(row.rate, rate_precision) != frappe.utils.flt(pre_vat_price, rate_precision):
                frappe.throw(
                    "Gỡ Pricing Rule / giảm giá trên dòng rồi tính lại. Dòng '{0}' của báo "
                    "giá '{1}' bị chính sách giá ERPNext tính lại thành {2} khác giá hệ "
                    "thống {3}, nên hệ thống dừng để tránh lệch tiền.".format(
                        row.item_name or row.item_code,
                        parent_name,
                        frappe.utils.flt(row.rate, rate_precision),
                        frappe.utils.flt(pre_vat_price, rate_precision),
                    )
                )

            parent.set_total_in_words()

            meta = parent.meta
            totals = {}
            for fieldname in _QUOTATION_TOTAL_FIELDS:
                if meta.has_field(fieldname):
                    value = parent.get(fieldname)
                    if value is not None:
                        totals[fieldname] = value

            frappe.db.set_value(
                "Quotation", parent_name, totals, update_modified=False)
        except Exception:
            frappe.log_error(
                title="AlumGlass: tính lại tổng tiền báo giá thất bại",
                message="Quotation Item %s / Quotation %s\n%s"
                        % (self.quotation_item_name, parent_name,
                           frappe.get_traceback()))
            raise

    # ── Response builder — trả về TOÀN BỘ cost_result ────────────────
    def _build_response(self):
        """Trả về toàn bộ kết quả. Client tự chọn key cần hiển thị."""
        qi_doc = getattr(self, "_qi_doc", None)
        return {
            "buckets": self.buckets,
            "cost_template": self.cost_result,
            "lines": self.bom_result,
            # Giá bán CÓ VAT / TRƯỚC VAT — ĐÚNG giá trị `b7_save_results` đã
            # ghi vào `al_gia_vat` / `al_gia_ban` / `rate` (tôn trọng cờ
            # `is_final_price` / `is_pre_vat_price` của cost template, ⛔ không
            # hardcode dòng GIA_VAT/GIA_BAN). Client ghi 2 field này xuống dòng
            # Quotation Item ngay sau khi tính ⇒ thiếu chúng, client phải đoán
            # bằng `cost_template.GIA_VAT` và có thể ghi SAI khi template đánh
            # dấu dòng giá cuối ở line_code khác.
            "gia_vat": self.gia_vat,
            "gia_ban": self._resolve_pre_vat_price(),
            # F2/D9: lỗi/cảnh báo structured của engine — TRƯỚC ĐÂY THIẾU ở đây
            # nên đường sync (api.calculate_bom → _normalize_bom_response) luôn
            # trả `errors: {}` và mọi cảnh báo bị chôn. Giữ ĐÚNG hình dạng hợp
            # đồng đã chốt với API/frontend (khoá `bom_items` / `cost_template`).
            "errors": {
                "bom_items": self.bom_engine_errors,
                "cost_template": self.cost_engine_errors,
            },
            # Phase 1 "Preview không ghi DB": dấu vân tay THAM SỐ đã dùng để
            # tính. Chỉ GHI (client lưu kèm `al_bom_result` khi bấm Lưu báo
            # giá); phase 2 mới đọc lại để kiểm khi Lưu. ⛔ Không HMAC ở phase 1
            # (design §3: chưa bắt buộc) ⇒ đây là hash SO KHỚP, ⛔ không phải
            # lớp chống giả mạo.
            "calc_meta": {
                "params_hash": compute_params_hash(
                    qi_doc.get("al_bom") if qi_doc is not None else None,
                    qi_doc.get("al_bom_version") if qi_doc is not None else None,
                    qi_doc.get("item_code") if qi_doc is not None else None,
                    qi_doc.get("al_bom_vars") if qi_doc is not None else None,
                ),
                "computed_at": _utc_now_iso(),
                # `getattr`: một số test dựng orchestrator rỗng (`__new__`) để
                # kiểm riêng `_build_response` — coi như đường tính + lưu.
                "preview": not getattr(self, "persist", True),
                "engine": "alumglass.bom_orchestrator",
            },
        }
