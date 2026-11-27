# -*- coding: utf-8 -*-
"""Ngữ cảnh chứng từ cho Variable Catalog — phần ĐỌC DB (có import frappe).

Adapter nhận `CatalogContext` thay vì tự query loạn xạ, nhờ vậy:
- chỉ nạp document/settings MỘT lần cho mỗi lượt gọi;
- adapter không cần biết docname/child_table/row_index lấy từ đâu.

⚠️ Mọi hàm trong file này phải CHỊU ĐƯỢC lỗi (doc chưa lưu, cột chưa migrate,
site thiếu app formula_builder): catalog là lớp gợi ý — hỏng nó không được
làm hỏng form của người dùng.
"""
import frappe


def _to_int_or_none(value):
    """row_index từ query string luôn là str — ép Int an toàn."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_doc(doctype, docname):
    """Nạp document theo tên; trả None nếu chưa tồn tại (kể cả tên tạm)."""
    if not doctype or not docname:
        return None
    try:
        if not frappe.db.exists(doctype, docname):
            return None
        return frappe.get_cached_doc(doctype, docname)
    except Exception:
        return None


class CatalogContext:
    """Bối cảnh 1 lượt gọi catalog: doctype + doc + child row + field đang sửa."""

    def __init__(self, doctype, docname=None, child_table=None, row_index=None,
                 fieldname=None, profile=None):
        self.doctype = doctype or ""
        self.docname = docname or ""
        self.child_table = (child_table or "").strip()
        self.row_index = _to_int_or_none(row_index)
        self.fieldname = (fieldname or "").strip()
        # profile: Document của AL Variable Profile (đã resolve) hoặc None.
        self.profile = profile

        self._doc = None
        self._doc_loaded = False
        self._meta = None
        self._resolved = None

    # ── meta / doc ──────────────────────────────────────────────────
    @property
    def meta(self):
        if self._meta is None:
            self._meta = frappe.get_meta(self.doctype)
        return self._meta

    def get_doc(self):
        """Document hiện tại; None khi tạo mới / tên tạm / không có quyền."""
        if not self._doc_loaded:
            self._doc_loaded = True
            self._doc = _load_doc(self.doctype, self.docname)
        return self._doc

    def get_value(self, fieldname, default=None):
        doc = self.get_doc()
        if doc is None:
            return default
        try:
            return doc.get(fieldname, default)
        except Exception:
            return default

    def get_child_doctype(self, table_field):
        """Doctype con của 1 Table field (None nếu field không phải Table)."""
        if not table_field:
            return None
        try:
            field = self.meta.get_field(table_field)
        except Exception:
            return None
        if field is not None and field.fieldtype == "Table":
            return field.options
        return None

    def get_child_rows(self, table_field=None):
        table = (table_field or self.child_table or "").strip()
        doc = self.get_doc()
        if not table or doc is None:
            return []
        try:
            return list(doc.get(table) or [])
        except Exception:
            return []

    def get_current_row(self):
        """Dòng đang sửa (0-based theo `row_index`) — None nếu không xác định."""
        if not self.child_table or self.row_index is None:
            return None
        rows = self.get_child_rows()
        if self.row_index < 0 or self.row_index >= len(rows):
            return None
        return rows[self.row_index]

    def get_field_scope(self):
        """(doctype chứa field đang sửa, row|None) — phục vụ adapter doctype_field."""
        if self.child_table:
            return self.get_child_doctype(self.child_table), self.get_current_row()
        return self.doctype, None

    # ── giá trị đã resolve (system variable) ────────────────────────
    def resolve_doc_values(self):
        """{var_name: value} resolve từ chứng từ hiện tại (best-effort).

        Dùng CHUNG nguồn với engine (`system_variable_resolver`) để
        autocomplete không hiện một đằng, tính giá một nẻo.
        """
        if self._resolved is not None:
            return self._resolved
        self._resolved = {}
        if self.get_doc() is None:
            return self._resolved
        try:
            from alumglass.al_bom_engine.system_variable_resolver import (
                resolve_source_record_names, resolve_system_variable_values)
            source_records = resolve_source_record_names(
                self.doctype, self.docname)
            self._resolved = resolve_system_variable_values(source_records) or {}
        except Exception:
            # Không nuốt im lặng — ghi log đủ ngữ cảnh để chẩn đoán.
            frappe.log_error(
                frappe.get_traceback(),
                title="Variable catalog: resolve_doc_values %s %s"
                      % (self.doctype, self.docname))
        return self._resolved

    @property
    def resolved(self):
        return self.resolve_doc_values()

def get_field_label(doctype, fieldname):
    """Nhãn người-đọc-được của field; fallback chính fieldname."""
    if not doctype or not fieldname:
        return fieldname or ""
    try:
        field = frappe.get_meta(doctype).get_field(fieldname)
        if field is not None and field.label:
            return field.label
    except Exception:
        pass
    return fieldname


def get_scalar_fieldnames(doctype):
    """Field dữ liệu vô hướng của doctype (bỏ layout, Table, JSON, text dài).

    Text dài cố ý bị loại: trên AL Bom Item, `width/height/qty` là Small Text
    chứa CÔNG THỨC — gợi ý chúng như biến số sẽ sai nghĩa.
    """
    if not doctype:
        return []
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return []
    allowed = {"Data", "Int", "Float", "Currency", "Percent", "Check",
               "Select", "Link", "Date", "Datetime", "Time"}
    skip = {"name", "owner", "creation", "modified", "modified_by", "docstatus",
            "idx", "parent", "parenttype", "parentfield", "doctype",
            "amended_from"}
    out = []
    for field in meta.get("fields") or []:
        if field.fieldtype not in allowed:
            continue
        if field.fieldname in skip:
            continue
        out.append(field.fieldname)
    return out


def detect_slug_field(child_doctype):
    """Dò field định danh dòng theo thứ tự cũ: custom_slug → line_ref → *_slug → slug."""
    if not child_doctype:
        return "slug"
    try:
        meta = frappe.get_meta(child_doctype)
    except Exception:
        return "slug"

    fieldnames = {f.fieldname for f in (meta.get("fields") or [])}
    for candidate in ("custom_slug", "line_ref"):
        if candidate in fieldnames:
            return candidate
    for fieldname in sorted(fieldnames):
        if fieldname.endswith("_slug"):
            return fieldname
    return "slug"
