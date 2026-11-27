"""API "Tạo sản phẩm từ mẫu" (B9/Đ2) — 2 endpoint cho nút trên form AL Bom Set.

  · ``preview_product_clone`` — kế hoạch nhân bản (chỉ ĐỌC, ⛔ insert).
  · ``create_product_clone``  — tạo thật (kiểm quyền tạo trên `AL Bom Set`
    TRƯỚC khi tạo).

Nguyên tắc trả lỗi: **luôn** trả ``{ok: False, error: "<câu tiếng Việt>"}``,
⛔ để traceback ra màn hình. Lỗi ngoài dự kiến vẫn được ghi Error Log để quản
trị tra khi cần.
"""
import frappe
from frappe import _

from alumglass.product_clone import BOM_SET, clone_product

# Nhãn cho câu lỗi quyền — ⛔ phơi tên DocType trần.
_DOCTYPE_LABEL = {
    BOM_SET: "bộ BOM",
}


_TECHNICAL_MARKERS = (
    "Duplicate entry", "IntegrityError", "OperationalError", "Traceback",
    "for key", "SQL", ".py", "NoneType", "KeyError", "Could not find",
    "does not exist", "Invalid", "Error:", "column", "Row #",
)


def _looks_technical(message):
    """Câu lỗi kỹ thuật (tiếng Anh/SQL/đường dẫn tệp) ⇒ ⛔ đưa cho người dùng.

    Vì sao cần: Frappe bọc nhiều lỗi DB thành `ValidationError`, nên chỉ xét
    LOẠI exception là không đủ — "Duplicate entry ... for key 'PRIMARY'" vẫn
    lọt ra màn hình người dùng.
    """
    text = (message or "").strip()
    if not text:
        return True
    if "\n" in text:
        return True
    return any(marker in text for marker in _TECHNICAL_MARKERS)


def _error_payload(exc, context):
    """Đóng gói lỗi thành câu người-đọc-được; lỗi lạ thì ghi Error Log.

    Lỗi NGHIỆP VỤ (do `frappe.throw` — đã là câu tiếng Việt) ⇒ trả nguyên văn.
    Lỗi LẠ (DB, mã nguồn…) ⇒ trả câu chung tiếng Việt, chi tiết chỉ vào Error
    Log — ⛔ phơi SQL/traceback ra màn hình người dùng.
    """
    known_types = tuple(kind for kind in (
        getattr(frappe, "ValidationError", None),
        getattr(frappe, "PermissionError", None),
    ) if kind)
    if known_types and isinstance(exc, known_types):
        message = str(exc).strip()
        if message and not _looks_technical(message):
            return {"ok": False, "error": message}
    try:
        frappe.log_error(frappe.get_traceback(), context)
    except Exception:
        pass
    return {
        "ok": False,
        "error": _("Không thực hiện được. Thử lại; nếu vẫn lỗi, báo quản trị."),
    }


def _assert_can(doctype, ptype, action):
    """Kiểm quyền trước khi đọc/ghi — câu lỗi nêu việc, không nêu mã kỹ thuật."""
    try:
        allowed = bool(frappe.has_permission(doctype, ptype))
    except Exception:
        allowed = False
    if allowed:
        return
    label = _DOCTYPE_LABEL.get(doctype, doctype)
    frappe.throw(
        _("Bạn không có quyền %(action)s %(label)s.")
        % {"action": action, "label": label},
        frappe.PermissionError)


def _suggest_code(source_set_code):
    """Mã gợi ý khi người dùng chưa nhập — chỉ là GỢI Ý cho bản xem trước."""
    base = "%s-MOI" % (source_set_code or "BO-MOI")
    code = base
    index = 2
    while index <= 50 and frappe.db.exists(BOM_SET, code):
        code = "%s%d" % (base, index)
        index += 1
    return code


@frappe.whitelist()
def preview_product_clone(source_set_code, new_code=None, new_name=None,
                          options=None):
    """Xem trước kế hoạch: bộ nào được tạo, mã gì, bao nhiêu dòng — ⛔ insert.

    ``new_code`` rỗng ⇒ dùng mã gợi ý ``<mã nguồn>-MOI`` (bỏ qua mã đã có).
    """
    try:
        _assert_can(BOM_SET, "read", "xem")
        plan = clone_product(
            source_set_code,
            new_code or _suggest_code(source_set_code),
            new_name=new_name,
            options=options,
            dry_run=True,
        )
        if plan.get("created"):
            plan["suggested_new_code"] = plan["created"][0]["code"]
        return plan
    except Exception as exc:
        return _error_payload(exc, "alumglass.api.product_clone.preview")


@frappe.whitelist()
def create_product_clone(source_set_code, new_code, new_name, options=None):
    """Tạo bộ mới từ bộ mẫu; trả ``created`` + ``redirect`` để client mở form.

    Quyền: cần quyền **tạo** trên `AL Bom Set`. Các bộ con do Frappe tự kiểm
    quyền lúc insert — lỗi quyền ở đó cũng được trả về dưới dạng câu tiếng Việt.
    """
    try:
        _assert_can(BOM_SET, "create", "tạo")
        # Mã trống ⇒ tự đặt mã chưa trùng (…-MOI2, -MOI3…). ⛔ bắt người dùng
        # tự nghĩ mã khi máy đã có sẵn hàm tìm mã trống.
        new_code = (new_code or "").strip() or _suggest_code(source_set_code)
        result = clone_product(
            source_set_code, new_code, new_name=new_name, options=options)
        if result.get("created"):
            top = result["created"][0]
            result["redirect"] = {"doctype": BOM_SET, "name": top["name"]}
        return result
    except Exception as exc:
        return _error_payload(exc, "alumglass.api.product_clone.create")
