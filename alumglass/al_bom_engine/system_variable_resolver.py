"""AlumGlass — System Variable Resolver (DÙNG CHUNG).

★ VẤN ĐỀ ĐÃ SỬA: có 2 bản đọc CÙNG 1 dữ liệu (`AL Variable Library`
is_system=1, `source_doctype`/`source_field`, và override qua child table
`AL Profile System.system_variables`) ở 2 nơi RIÊNG BIỆT, lệch nhau:

  - `bom_orchestrator.py::_resolve_system_variables()` — dùng khi TÍNH BOM
    thật (self.inputs). Hardcode `source_records = {"AL Profile System": ...,
    "AL Product Type": ...}` — chỉ 2 doctype cố định.
  - `api/__init__.py::_resolve_doc_values()` — dùng khi hiện GIÁ TRỊ LIVE
    cho autocomplete/preview trong Formula Builder. Hardcode
    `if doctype == "AL Bom Set": ... for f in ["offset_frame", ...]:
    vals[f.upper()] = ...` — mapping field→tên biến SAI (vd
    `"offset_crossbar".upper()` = `OFFSET_CROSSBAR`, nhưng biến THẬT seed
    trong `AL Variable Library` và dùng trong công thức là `OFFSET_DO_NGANG`
    — autocomplete từng hiện 1 biến không khớp tên thật trong công thức).

★ MODULE NÀY LÀ NGUỒN DUY NHẤT — cả 2 nơi trên gọi lại, không tự viết nữa.
Auto-discover doctype nào cần resolve bằng cách dò field Link trên chính
`doctype` đang cần context (giống hệt cách `_resolve_variable_set_name` dò
Link → AL Variable Set trong `api/__init__.py`) — thêm 1 System Variable mới
trỏ `source_doctype` khác (vd "AL Color Standard") = tự động resolve được
miễn `doctype` gọi có field Link trỏ đúng tới đó, KHÔNG cần sửa file này.

`AL Variable Library.source_link_field` (v28_14) cho phép khai TƯỜNG MINH
field Link dùng để tìm bản ghi nguồn — cần khi 1 doctype có nhiều field Link
cùng trỏ 1 target (auto-discover chỉ lấy field đầu tiên nên có thể chọn sai).
"""
import frappe

# Cột đọc từ AL Variable Library. `source_link_field` là cột MỚI (v28_14):
# khai tường minh field Link trên doctype context dùng để tìm bản ghi nguồn —
# cần khi 1 doctype có NHIỀU field Link cùng trỏ 1 target (auto-discover chỉ
# lấy field ĐẦU TIÊN nên có thể chọn sai).
_SYSTEM_VAR_FIELDS = ["var_name", "source_doctype", "source_field",
                      "source_link_field"]
_LEGACY_SYSTEM_VAR_FIELDS = ["var_name", "source_doctype", "source_field"]


def fetch_system_vars(extra_fields=None):
    """Query system vars — chịu được site CHƯA migrate cột `source_link_field`.

    Trong cửa sổ giữa "kéo code về" và "bench migrate", DB chưa có cột mới;
    query kèm cột đó sẽ ném lỗi SQL. Fallback danh sách cột cũ để luồng tính
    giá/autocomplete không chết vì lý do hạ tầng.

    Args:
        extra_fields: cột bổ sung caller cần (vd `["default_value"]` ở
            bom_orchestrator._resolve_system_variables).
    """
    extra = list(extra_fields or [])
    try:
        return frappe.get_all(
            "AL Variable Library", filters={"is_system": 1},
            fields=list(_SYSTEM_VAR_FIELDS) + extra) or []
    except Exception:
        return frappe.get_all(
            "AL Variable Library", filters={"is_system": 1},
            fields=list(_LEGACY_SYSTEM_VAR_FIELDS) + extra) or []


def resolve_source_link_fields(doctype):
    """Trả {options(doctype): fieldname} — bản đồ field Link trên `doctype`.

    Dùng chung bởi:
      - resolve_source_record_names() (engine B1 + api autocomplete) khi cần
        resolve System Variable theo link thật.
      - patch `v28_11.seed_fvb_full_from_variable_library` khi quyết định var
        nào "seed FVB được" (link_field tồn tại trên AL Bom Set → FVB
        linked_doctype_field resolve ĐÚNG nguồn như engine 1.3 cũ).
    Lấy từ META (không cần docname/record cụ thể).
    """
    meta = frappe.get_meta(doctype)
    link_fields = {}
    for f in meta.get("fields", []):
        if f.fieldtype == "Link" and f.options and f.options not in link_fields:
            link_fields[f.options] = f.fieldname
    return link_fields


def resolve_source_record_names(doctype, docname, system_vars=None):
    """Trả {source_doctype: record_name} — tự dò field Link trên `doctype`
    trỏ tới từng source_doctype mà System Variable cần.

    Thứ tự chọn field Link cho mỗi source_doctype:
      1. `AL Variable Library.source_link_field` khai TƯỜNG MINH (nếu field
         đó tồn tại trên meta của `doctype`) — thắng auto-discover, vì 1
         doctype có thể có nhiều field Link cùng trỏ 1 target và auto-discover
         chỉ lấy field đầu tiên (có thể chọn sai).
      2. Auto-discover: field Link ĐẦU TIÊN trỏ tới source_doctype
         (`resolve_source_link_fields`).
    `source_link_field` khai sai (field không tồn tại) ⇒ ghi logger warning
    rồi rơi về auto-discover — ⛔ không chặn luồng resolve.

    Args:
        doctype, docname: document đang cần resolve context (vd AL Bom Set,
            hoặc bất kỳ doctype nào khác có field Link phù hợp).
        system_vars: list đã query sẵn (tránh query lại nếu caller đã có).
    """
    if system_vars is None:
        system_vars = fetch_system_vars()

    link_fields = resolve_source_link_fields(doctype)
    meta_fields = None  # lazy — chỉ đọc meta khi có source_link_field

    # {source_doctype: (ưu tiên, fieldname)} — 0 = khai tường minh, 1 = auto.
    chosen = {}
    for sv in system_vars:
        sdt = sv.get("source_doctype")
        if not sdt:
            continue

        explicit = (sv.get("source_link_field") or "").strip()
        if explicit:
            if meta_fields is None:
                meta_fields = {
                    f.fieldname: f
                    for f in (frappe.get_meta(doctype).get("fields") or [])
                }
            # Khai tường minh chỉ được dùng khi ĐÚNG là field Link trỏ tới
            # source_doctype — fieldname tồn tại nhưng kiểu Data/trỏ nơi khác
            # mà đem query sẽ trả rỗng/gây lỗi âm thầm.
            field_meta = meta_fields.get(explicit)
            problem = ""
            if field_meta is None:
                problem = "không tồn tại trên %s" % doctype
            elif getattr(field_meta, "fieldtype", None) != "Link":
                problem = ("không phải field Link (fieldtype=%s)"
                           % getattr(field_meta, "fieldtype", None))
            elif getattr(field_meta, "options", None) != sdt:
                problem = ("trỏ tới '%s' chứ không phải '%s'"
                           % (getattr(field_meta, "options", None), sdt))
            if problem:
                frappe.logger("alumglass").warning(
                    "System variable '%s' khai source_link_field '%s' nhưng "
                    "field %s — dùng auto-discover."
                    % (sv.get("var_name"), explicit, problem))
                explicit = ""

        link_field = explicit or link_fields.get(sdt)
        if not link_field:
            continue

        priority = 0 if explicit else 1
        current = chosen.get(sdt)
        if current is None or priority < current[0]:
            chosen[sdt] = (priority, link_field)

    source_records = {}
    for sdt, (_priority, link_field) in chosen.items():
        try:
            source_records[sdt] = frappe.db.get_value(
                doctype, docname, link_field)
        except Exception as exc:
            # Cấu hình meta lệch DB (cột chưa migrate) — bỏ qua target này,
            # các target khác vẫn resolve; ghi log để chẩn đoán.
            frappe.logger("alumglass").warning(
                "Không đọc được %s.%s khi resolve system variable: %s"
                % (doctype, link_field, exc))
    return source_records


def resolve_system_variable_values(source_records, system_vars=None):
    """Trả {var_name: value} đã resolve từ source_records (xem
    resolve_source_record_names) + override từ `AL Profile System`
    child table `system_variables` (ưu tiên cao nhất — V6 P5).

    KHÔNG áp fallback `default_value` / `AL Rule` (rule CONSTANT) ở
    đây — 2 fallback đó là hành vi RUNTIME riêng của
    `bom_orchestrator._resolve_system_variables()` (cần đủ ngữ cảnh 1 lần
    tính BOM: self.inputs, rule engine...), không phù hợp cho hàm thuần dùng
    chung ở đây. Caller (`get_formula_context`) đã tự có bước fallback
    default_value riêng cho MỌI system var (không chỉ loại có source_doctype).
    """
    if system_vars is None:
        system_vars = fetch_system_vars()

    vals = {}
    for sv in system_vars:
        sdt, sf, vn = sv.get("source_doctype"), sv.get("source_field"), sv["var_name"]
        if not sdt or not sf:
            continue
        record_name = source_records.get(sdt)
        if not record_name:
            continue
        try:
            val = frappe.db.get_value(sdt, record_name, sf)
        except Exception:
            val = None
        if val is not None:
            vals[vn] = val

    ps_name = source_records.get("AL Profile System")
    if ps_name:
        try:
            ps_doc = frappe.get_cached_doc("AL Profile System", ps_name)
            for row in ps_doc.get("system_variables") or []:
                if not row.get("is_active"):
                    continue
                var_name = row.get("variable")
                val = row.get("value")
                if not var_name or val is None or str(val).strip() == "":
                    continue
                # Value lưu dạng Data (string) — parse số khi được (đa số
                # trường hợp, vd offset/percent), giữ nguyên nếu là công
                # thức/ký tự không parse được. Giữ đúng hành vi gốc của
                # bom_orchestrator._resolve_system_variables() (V6 P5).
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    pass
                vals[var_name] = val
        except frappe.DoesNotExistError:
            pass
    return vals
