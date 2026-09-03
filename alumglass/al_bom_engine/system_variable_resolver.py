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
"""
import frappe


def resolve_source_record_names(doctype, docname, system_vars=None):
    """Trả {source_doctype: record_name} — tự dò field Link trên `doctype`
    trỏ tới từng source_doctype mà System Variable cần.

    Args:
        doctype, docname: document đang cần resolve context (vd AL Bom Set,
            hoặc bất kỳ doctype nào khác có field Link phù hợp).
        system_vars: list đã query sẵn (tránh query lại nếu caller đã có).
    """
    if system_vars is None:
        system_vars = frappe.get_all(
            "AL Variable Library", filters={"is_system": 1},
            fields=["var_name", "source_doctype", "source_field"])

    meta = frappe.get_meta(doctype)
    link_fields = {}
    for f in meta.get("fields", []):
        if f.fieldtype == "Link" and f.options and f.options not in link_fields:
            link_fields[f.options] = f.fieldname

    source_records = {}
    for sv in system_vars:
        sdt = sv.get("source_doctype")
        if not sdt or sdt in source_records:
            continue
        link_field = link_fields.get(sdt)
        if link_field:
            source_records[sdt] = frappe.db.get_value(doctype, docname, link_field)
    return source_records


def resolve_system_variable_values(source_records, system_vars=None):
    """Trả {var_name: value} đã resolve từ source_records (xem
    resolve_source_record_names) + override từ `AL Profile System`
    child table `system_variables` (ưu tiên cao nhất — V6 P5).

    KHÔNG áp fallback `default_value` / `AL Calculation Rule CONSTANT` ở
    đây — 2 fallback đó là hành vi RUNTIME riêng của
    `bom_orchestrator._resolve_system_variables()` (cần đủ ngữ cảnh 1 lần
    tính BOM: self.inputs, rule engine...), không phù hợp cho hàm thuần dùng
    chung ở đây. Caller (`get_formula_context`) đã tự có bước fallback
    default_value riêng cho MỌI system var (không chỉ loại có source_doctype).
    """
    if system_vars is None:
        system_vars = frappe.get_all(
            "AL Variable Library", filters={"is_system": 1},
            fields=["var_name", "source_doctype", "source_field"])

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
