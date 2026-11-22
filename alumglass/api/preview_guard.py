# -*- coding: utf-8 -*-
"""Phase 2 (nửa MÁY CHỦ) của "Preview tính giá KHÔNG ghi DB".

BỐI CẢNH
────────
Phase 1 (design `docs/design/preview-khong-ghi-db.md` §9.1) đã bỏ mọi đường
ghi DB khỏi preview: `alumglass.api.preview_bom` chạy engine với `persist=False`
và trả kèm `calc_meta.params_hash` — SHA-256 của 4 tham số đã chuẩn hoá
(`al_bom`, `al_bom_version`, `item_code`, `al_bom_vars`). Client ghi kết quả
xuống dòng TRÊN FORM (kể cả `al_bom_result`) nên khi bấm Lưu, dòng mang kết quả
mới — nhưng DB chỉ đổi đúng lúc Lưu.

VÌ SAO CẦN TỆP NÀY
──────────────────
Sau phase 1, giá trị nằm trong DB **hoàn toàn do client gửi**. Câu hỏi duy nhất
cần trả lời lúc Lưu là: *"con số đang lưu có được tính từ đúng tham số đang lưu
không?"* — và trả lời được **mà không cần tính lại** (so `params_hash`).

Owner chốt (§9.1 câu 3): lệch ⇒ **TỰ TÍNH LẠI dòng lệch rồi mới ghi**, ⛔ không
chặn người dùng. Chỉ dòng lệch mới đi vào engine — báo giá 20 dòng đã preview
đủ thì Lưu không tốn lượt tính nào.

RÀNG BUỘC (đọc trước khi sửa)
─────────────────────────────
· ⛔ KHÔNG `frappe.db.set_value`, ⛔ KHÔNG `commit`, ⛔ KHÔNG `save()`: mọi thứ
  gán vào CHÍNH doc đang lưu để Frappe ghi khi kết thúc lượt Lưu.
· ⛔ Không đổi công thức / hình dạng `al_bom_result`; chỉ cập nhật `calc_meta`.
· ⛔ Không đụng `b7_save_results` (đường ghi cũ của engine vẫn nguyên).
· Chỉ chạy khi `docstatus == 0` (xem lý do trong hàm chính).

HAI CHỖ DỄ HIỂU SAI
───────────────────
1. **Hash tính cả VERSION HIỆU LỰC, ⛔ không chỉ field trên dòng.** Dòng để
   trống `al_bom_version` thì engine lấy `AL BOM.current_version` (hoặc version
   mới nhất — xem `b0_version_pinning`); hash chỉ có `""` sẽ khiến BOM đổi
   version hiện hành mà guard vẫn thấy "khớp" ⇒ giá cũ nằm lại im lặng. Vì vậy
   `_effective_version()` resolve đúng như engine, và sau khi tính lại thì
   **ghim** version đó xuống dòng để lần Lưu sau khớp tự nhiên.
   Hệ quả hợp đồng: client phase 1 preview dòng có version rỗng ⇒ hash client
   cũng rỗng ⇒ dòng đó LỆCH một lần ở lần Lưu đầu, guard tính lại rồi ghim
   version; từ lần sau hash hai bên khớp.
2. **Bỏ qua trong patch/install/migrate.** Patch gọi `doc.save()` trên báo giá
   cũ (chưa có `calc_meta`) sẽ đi vào engine cho TỪNG dòng — rất chậm khi chạy
   hàng loạt. Các lượt đó ⛔ KHÔNG làm mới giá: dữ liệu vẫn được làm mới ở lần
   Lưu kế tiếp của người dùng (patch nào cố ý đổi giá thì tự chịu trách nhiệm
   về số nó ghi).
"""
import json

import frappe
from frappe import _

# Field của dòng được phép chuyển vào engine qua `params` — PHẢI khớp
# `BomOrchestrator.PREVIEW_ROW_FIELDS` (engine ⛔ không nhận tiền tệ/bảng
# giá/khách hàng từ params: bối cảnh giá luôn đọc từ Quotation cha trong DB).
_PREVIEW_ROW_FIELDS = (
    "al_bom", "al_bom_version", "al_bom_vars",
    "item_code", "item_name", "qty", "uom", "stock_uom",
)

_LOG = "alumglass"


# ══════════════════════════════════════════════════════════════════════
# Doc event — `Quotation.validate`
# ══════════════════════════════════════════════════════════════════════
def validate_preview_freshness(doc, method=None):
    """Lưu báo giá: dòng nào có kết quả BOM LỆCH tham số thì tính lại tại chỗ.

    Chỉ chạy khi `doc.docstatus == 0`:

    · Frappe `Document._submit()` set `docstatus = 1` TRƯỚC khi chạy `save()`
      ⇒ lượt Submit đi qua đây với docstatus 1 và bị bỏ qua. Đó là chủ ý:
      submit có luồng riêng (`alumglass.api.quotation_events.on_submit` tạo
      `ConfigSnapshot`), và số đã chốt phải giữ nguyên — ⛔ không tính lại giá
      trong lượt submit (kể cả khi ai đó gọi submit trên form còn "dirty"):
      Frappe đã lưu (validate docstatus 0) ngay trước đó, nên số đã được làm
      mới ở lượt Lưu, ⛔ không phải lượt submit.
    · `docstatus == 2` (đã huỷ) cũng bỏ qua: huỷ không được đổi số liệu.

    Đường thường (preview rồi Lưu, mọi dòng khớp hash) ⇒ **0 lượt engine,
    0 lần ghi thêm** — chỉ đọc `al_bom_result` để so hash (và 1 lượt đọc
    `AL BOM.current_version` cho mỗi BOM có dòng để trống version).
    """
    if doc is None or _docstatus(doc) != 0:
        return
    if _in_system_operation():
        return

    rows = doc.get("items") or []
    stale = []
    version_cache = {}
    for idx, row in enumerate(rows, 1):
        # Dòng chưa chọn BOM ⇒ không có gì để tính (⛔ không tự đặt giá).
        if not row.get("al_bom"):
            continue
        effective_version = _effective_version(row, version_cache)
        params_hash = _row_params_hash(row, effective_version)
        if params_hash == _previewed_hash(row):
            # Khớp ⇒ kết quả đang lưu ĐÚNG là kết quả của bộ tham số đang lưu
            # (kể cả version hiệu lực khi dòng để trống `al_bom_version`).
            continue
        stale.append((idx, row, params_hash, effective_version))

    if not stale:
        return

    recomputed = 0
    for idx, row, params_hash, effective_version in stale:
        try:
            result = _recompute_row(row, doc)
        except Exception as exc:
            # ⛔ Không phơi traceback/lỗi kỹ thuật; ⛔ không lưu báo giá với giá
            # CŨ trong im lặng. Ghi vết đầy đủ ở log máy chủ để support lần.
            frappe.logger(_LOG).error(
                "AlumGlass preview_guard: tính lại dòng %s (mã %s) của báo giá "
                "%s thất bại — %s: %s"
                % (idx, row.get("item_code"), _doc_name(doc),
                   type(exc).__name__, exc)
            )
            frappe.throw(
                _("Dòng {0} ({1}): không tính lại được giá theo tham số mới. "
                  "Mở \"Tham số BOM\" của dòng này, bấm \"Preview tính giá\" "
                  "rồi lưu lại.").format(idx, _row_label(row)),
                frappe.ValidationError,
            )
        _apply_result(row, result, params_hash)
        # GHIM version hiệu lực xuống dòng: kết quả vừa tính là của version
        # này, ghi lại để (a) lần Lưu sau so hash là khớp ngay, (b) giá không
        # trôi theo `AL BOM.current_version` đổi sau đó. Chỉ ghim khi dòng để
        # trống — dòng đã khai version thì giữ nguyên lựa chọn của người dùng.
        if effective_version and not row.get("al_bom_version"):
            _set_field(row, "al_bom_version", effective_version)
        recomputed += 1

    # ERPNext tính tổng tiền trong `validate` của nó, TRƯỚC doc event này
    # (`AccountsController.validate` → `calculate_taxes_and_totals`) ⇒ đổi
    # `rate` xong phải tính lại tổng, nếu không báo giá lưu với tổng CŨ.
    # Cùng việc client làm sau khi nhận kết quả preview
    # (`alumglass.quotation._refresh_totals`).
    _recalculate_totals(doc)

    frappe.logger(_LOG).info(
        "AlumGlass preview_guard: tính lại %d dòng lệch tham số của báo giá %s"
        % (recomputed, _doc_name(doc))
    )


# ══════════════════════════════════════════════════════════════════════
# Tính lại một dòng
# ══════════════════════════════════════════════════════════════════════
def _recompute_row(row, doc):
    """Chạy engine ở chế độ PREVIEW (⛔ không ghi DB) cho đúng tham số của dòng.

    Dòng chưa có tên thật (`new-…`, `__islocal`) ⇒ ⛔ không truyền tên: engine
    dựng doc từ `params`, không đọc DB, và ⛔ không tạo dòng nào.
    """
    from alumglass.engine.bom_orchestrator import BomOrchestrator

    return BomOrchestrator(
        quotation_item_name=_row_db_name(row),
        params=_row_params(row, doc),
        persist=False,
    ).run()


def _row_params(row, doc):
    """`params` cho engine — đúng các field của CHÍNH DÒNG đang lưu."""
    params = {}
    for field in _PREVIEW_ROW_FIELDS:
        value = row.get(field)
        if value is not None:
            params[field] = value
    params["parent"] = _doc_name(doc)
    params["parenttype"] = "Quotation"
    return params


def _row_db_name(row):
    """Tên THẬT của dòng trong DB, hoặc None nếu dòng chưa lưu.

    `__islocal` là cờ Frappe đặt cho dòng mới; client đặt tên dòng mới dạng
    `new-quotation-item-N`. Kiểm thêm `db.exists` để dòng đến từ import/link
    mà tên chưa có trong DB vẫn tính được (engine sẽ dựng từ params thay vì
    `frappe.get_doc` thất bại).
    """
    name = row.get("name")
    if not name or row.get("__islocal") or str(name).startswith("new-"):
        return None
    try:
        if not frappe.db.exists("Quotation Item", name):
            return None
    except Exception:
        # Không dò được (bản Frappe cũ/DB đang bảo trì) ⇒ vẫn thử dùng tên như
        # hành vi cũ; nếu tên thật sự không có, engine ném và ta báo câu
        # người-đọc-được ở trên.
        pass
    return name


# ══════════════════════════════════════════════════════════════════════
# Dấu vân tay tham số
# ══════════════════════════════════════════════════════════════════════
def _effective_version(row, cache=None):
    """Version engine SẼ DÙNG cho dòng này — y hệt `b0_version_pinning`.

    Thứ tự (mirror engine, ⛔ đừng "cải tiến" lệch):
      1. `row.al_bom_version` nếu dòng đã khai;
      2. `AL BOM.current_version`;
      3. version MỚI NHẤT của BOM (F11 — BOM chưa xuất bản version hiện hành).

    Vì sao cần: hash chỉ có 4 field (design §3) trong đó `al_bom_version` là
    chuỗi RỖNG khi người dùng để trống ⇒ engine vẫn lấy version hiệu lực, còn
    guard sẽ mãi thấy "khớp" ⇒ **BOM đổi version hiện hành mà giá cũ nằm lại,
    không ai biết**. Phải hash ĐÚNG version engine dùng.

    `cache`: {bom_code: version} dùng chung trong một lượt Lưu — nhiều dòng
    cùng một BOM chỉ đọc DB 1 lần. Lỗi đọc (BOM không tồn tại…) ⇒ "" để giữ
    đường cũ; engine sẽ báo câu người-đọc-được ở bước tính.
    """
    version = row.get("al_bom_version")
    if version:
        return version
    bom = row.get("al_bom")
    if not bom:
        return ""
    if cache is not None and bom in cache:
        return cache[bom]

    resolved = ""
    try:
        resolved = frappe.db.get_value("AL BOM", bom, "current_version") or ""
    except Exception:
        resolved = ""
    if not resolved:
        # F11: chưa có `current_version` ⇒ engine tái dùng version mới nhất đã
        # có (cùng `order_by` tường minh như `_latest_existing_version`).
        try:
            found = frappe.get_all(
                "AL BOM Version",
                filters={"bom": bom},
                fields=["name"],
                order_by="creation DESC",
                limit=1,
            )
            resolved = found[0]["name"] if found else ""
        except Exception:
            resolved = ""

    if cache is not None:
        cache[bom] = resolved
    return resolved


def _row_params_hash(row, effective_version):
    """Hash của 4 tham số LẤY TỪ DÒNG đang lưu + VERSION HIỆU LỰC.

    ⚠ CỐ Ý chỉ 4 field: `qty`/`rate` KHÔNG tham gia — sửa số lượng hay đơn giá
    không làm kết quả BOM cũ sai (engine ⛔ không dùng chúng để tra giá), nên
    ⛔ không được coi là "lệch" (sẽ tính lại vô ích mỗi lần đổi số lượng).
    `al_bom_version` truyền vào là version ĐÃ RESOLVE (xem `_effective_version`).
    """
    from alumglass.engine.bom_orchestrator import compute_params_hash

    return compute_params_hash(
        row.get("al_bom"),
        effective_version,
        row.get("item_code"),
        row.get("al_bom_vars"),
    )


def _previewed_hash(row):
    """`calc_meta.params_hash` đang nằm trong `al_bom_result` của dòng ("" nếu không)."""
    raw = row.get("al_bom_result")
    if not raw:
        return ""
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            # JSON hỏng ⇒ coi như "chưa có kết quả" ⇒ dòng lệch ⇒ tính lại.
            return ""
    elif isinstance(raw, dict):
        data = raw
    else:
        return ""
    if not isinstance(data, dict):
        return ""
    meta = data.get("calc_meta")
    if not isinstance(meta, dict):
        return ""
    return meta.get("params_hash") or ""


# ══════════════════════════════════════════════════════════════════════
# Gán kết quả vào CHÍNH doc (Frappe ghi khi kết thúc lượt Lưu)
# ══════════════════════════════════════════════════════════════════════
def _apply_result(row, result, params_hash):
    """Ghi kết quả vừa tính vào dòng TRÊN DOC — ⛔ không chạm DB.

    Giữ NGUYÊN hình dạng `al_bom_result` do engine trả (buckets/cost_template/
    lines/gia_vat/gia_ban/errors) — chỉ cập nhật `calc_meta`:
      · `params_hash` = hash của tham số ĐANG LƯU (chốt lại, khỏi phụ thuộc
        engine có resolve version ngầm hay không);
      · `preview = False` — kết quả này ĐƯỢC GHI xuống dòng ngay sau đây, nên
        nó là bản đã lưu, ⛔ không còn là "preview treo trên form";
      · `recomputed_on_save = True` — dấu vết để support đối chiếu (số này do
        máy chủ tính lại lúc Lưu, ⛔ phải client gửi lên).
    """
    payload = dict(result or {})
    payload.setdefault("buckets", {})
    payload.setdefault("cost_template", {})
    payload.setdefault("lines", [])
    payload.setdefault("errors", {})

    meta = dict(payload.get("calc_meta") or {})
    meta["params_hash"] = params_hash
    meta["preview"] = False
    meta["recomputed_on_save"] = True
    payload["calc_meta"] = meta

    gia_ban = payload.get("gia_ban") or 0
    gia_vat = payload.get("gia_vat") or 0

    _set_field(row, "al_bom_result", json.dumps(payload, indent=2, default=str))
    _set_field(row, "al_gia_ban", gia_ban)
    _set_field(row, "al_gia_vat", gia_vat)
    # Giống `b7_save_results` (máy chủ): rate = giá TRƯỚC VAT, ghi cả khi 0 —
    # đây là dòng vừa được tính lại, giá cũ ⛔ được ở lại trong đơn giá.
    _set_field(row, "rate", gia_ban)
    # Trạng thái trên dòng nói ĐÚNG sự thật: dòng vừa có kết quả mới hợp lệ.
    _set_field(row, "al_calc_status", "Success")
    _set_field(row, "al_calc_error", "")


# ══════════════════════════════════════════════════════════════════════
# Tiện ích nhỏ (chịu được stub test lẫn Frappe thật)
# ══════════════════════════════════════════════════════════════════════
def _set_field(row, fieldname, value):
    """Gán field cho dòng Quotation Item (Document thật hoặc dict)."""
    setter = getattr(row, "set", None)
    if callable(setter):
        setter(fieldname, value)
    else:
        row[fieldname] = value


def _in_system_operation():
    """Đang chạy patch / install / migrate? ⇒ ⛔ tính lại giá.

    Lý do: các lượt đó gọi `doc.save()` hàng loạt trên báo giá CŨ (chưa có
    `calc_meta`) ⇒ mỗi dòng một lượt engine, migrate sẽ rất chậm. Dữ liệu vẫn
    được làm mới ở lần Lưu kế tiếp của người dùng. `frappe.flags` không có
    trong stub test ⇒ coi như không phải thao tác hệ thống.
    """
    flags = getattr(frappe, "flags", None)
    if flags is None:
        return False
    for flag in ("in_patch", "in_install", "in_migrate"):
        if getattr(flags, flag, False):
            return True
    return False


def _recalculate_totals(doc):
    """Tính lại tổng tiền báo giá sau khi `rate` đổi (nếu doc có controller).

    ⚠ CỐ Ý không làm lại mẹo của `b7_save_results._recalculate_quotation_totals`
    (tạm đưa `price_list_rate`/`discount_*`/`margin_*` về 0 RỒI tính tổng):
    ở đây doc ĐANG được lưu, gán 0 vào các field đó là ghi đè dữ liệu giảm giá
    của người dùng xuống DB. Hệ quả: nếu dòng có Pricing Rule / giảm giá, luật
    giá của ERPNext có thể tính lại `rate` y như một lượt Lưu BÌNH THƯỜNG
    (client cũng đi qua đúng luật đó khi lưu) — nghĩa là `rate` có thể khác
    `al_gia_ban`. Đó là hành vi hiện hữu, ⛔ không phải do handler này sinh ra;
    muốn chặn thì phải bàn ở tầng nghiệp vụ (b7 đã chặn cho đường `calculate_bom`).
    """
    recalculator = getattr(doc, "calculate_taxes_and_totals", None)
    if callable(recalculator):
        recalculator()


def _docstatus(doc):
    try:
        return int(doc.get("docstatus") or 0)
    except (TypeError, ValueError):
        return 0


def _doc_name(doc):
    return (doc.get("name") or "") if doc is not None else ""


def _text(value):
    return str(value).strip() if value is not None else ""


def _row_label(row):
    """Nhãn người-đọc-được cho câu lỗi: tên hàng + mã hàng (thiếu thì thôi)."""
    code = _text(row.get("item_code"))
    name = _text(row.get("item_name"))
    if name and code:
        return "{0} – {1}".format(name, code)
    return name or code or _text(row.get("al_bom"))
