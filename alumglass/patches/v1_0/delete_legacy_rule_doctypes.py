# -*- coding: utf-8 -*-
"""CHẶNG 2C — xoá HẲN 2 DocType rule cũ sau khi dữ liệu đã chuyển sang `AL Rule`.

Chạy NGAY SAU `migrate_rules_to_al_rule` trong `[post_model_sync]`. Patch này
chỉ xoá **DocType record** (JSON đã bị gỡ khỏi mã nguồn), ⛔ DROP bảng dữ
liệu — xem mục "DỌN BẢNG" bên dưới.

CỔNG CHẶN (fail-fast)
─────────────────────
Trước khi xoá bất cứ gì: với MỌI `rule_code` còn trong 2 bảng cũ phải tồn tại
`AL Rule` cùng mã **và cùng `result_type`** (NUMBER cho `AL Calculation
Rule`, ITEM cho `AL Dynamic Item Rule`). Thiếu/lệch ⇒ `frappe.throw` nêu DANH
SÁCH mã, ⛔ xoá gì. Nhờ vậy xoá DocType không bao giờ làm mất đường đọc dữ
liệu: bảng `AL Rule` đã có đủ bản ghi tương ứng.

THỨ TỰ XOÁ
──────────
Con/version TRƯỚC, cha SAU — để không còn Link sống trỏ vào DocType sắp xoá:

    AL Dynamic Item Rule Version
    AL Dynamic Item Rule Threshold Row
    AL Dynamic Item Rule Lookup Row
    AL Dynamic Item Rule
    AL Calculation Rule

Dùng `frappe.delete_doc("DocType", name, force=True, ignore_permissions=True)`.
Frappe từ chối (còn Link) ⇒ `frappe.log_error` ghi rõ rồi `throw` — ⛔ nuốt
lỗi để patch "thành công" trong khi DocType vẫn còn.

DỌN WORKFLOW CŨ
───────────────
Site đã từng chạy `install_workflows()` còn bản ghi `Workflow` tên
"AL Dynamic Item Rule Version Workflow" trỏ tới DocType vừa xoá ⇒ mục gãy
trong danh sách Workflow. Gỡ entry khỏi `install_workflows.py` chỉ NGĂN TẠO
LẠI — patch này xoá bản ghi đang có (`frappe.db.exists` → `delete_doc`, cùng
kiểu log + throw). ⛔ đụng `AL Rule Version Workflow` hay Workflow nào khác.

IDEMPOTENT
──────────
DocType record / Workflow không tồn tại ⇒ bỏ qua. Chạy lại patch (qua
`bench execute`) không lỗi, không xoá nhầm gì.

⛔ DROP BẢNG TRONG PATCH NÀY
────────────────────────────
Bảng cũ (`tabAL Calculation Rule`, `tabAL Dynamic Item Rule`,
`tabAL Dynamic Item Rule Threshold Row`, `tabAL Dynamic Item Rule Lookup
Row`, `tabAL Dynamic Item Rule Version`) được GIỮ LẠI sau khi xoá DocType —
làm đường cứu hộ một chu kỳ (dữ liệu vẫn đọc được bằng SQL thô nếu cần đối
chiếu/khôi phục). Patch migrate đã được viết để đọc thẳng các bảng này kể cả
khi DocType record không còn.

DỌN BẢNG (làm TAY, sau khi đã đối chiếu `AL Rule` và hết thời gian cứu hộ):

    bench --site <site> mariadb
    -- trong phiên SQL:
    DROP TABLE `tabAL Calculation Rule`;
    DROP TABLE `tabAL Dynamic Item Rule`;
    DROP TABLE `tabAL Dynamic Item Rule Threshold Row`;
    DROP TABLE `tabAL Dynamic Item Rule Lookup Row`;
    DROP TABLE `tabAL Dynamic Item Rule Version`;

⚠️ BẮT BUỘC backup trước lượt migrate có patch này:
    bench --site <site> backup --with-files
Không còn DocType cũ để "rollback code" — đường lùi duy nhất là restore
backup (hoặc đọc lại bảng mồ côi bằng SQL thô trong một chu kỳ).
"""

import frappe

NUMBER_SOURCE = "AL Calculation Rule"
ITEM_SOURCE = "AL Dynamic Item Rule"

#: Thứ tự xoá AN TOÀN: con/version trước, cha sau.
DELETE_ORDER = (
    "AL Dynamic Item Rule Version",
    "AL Dynamic Item Rule Threshold Row",
    "AL Dynamic Item Rule Lookup Row",
    "AL Dynamic Item Rule",
    "AL Calculation Rule",
)

#: Bảng nguồn → `result_type` MONG ĐỢI của `AL Rule` cùng mã.
SOURCE_TYPES = (
    (NUMBER_SOURCE, "NUMBER"),
    (ITEM_SOURCE, "ITEM"),
)

#: Workflow cấu hình của doctype version cũ — bản ghi mồ côi cần dọn.
LEGACY_WORKFLOW = "AL Dynamic Item Rule Version Workflow"


def execute():
    """Điểm vào của patch (đăng ký ở `alumglass/patches.txt`)."""
    _assert_migrated()
    for doctype in DELETE_ORDER:
        _delete_doctype(doctype)
    _delete_legacy_workflow()


# ═══════════════════════════════════════════════════════════════════
# Cổng chặn — dữ liệu PHẢI đã nằm trong `AL Rule`
# ═══════════════════════════════════════════════════════════════════
def _table_exists(doctype):
    """Bảng của doctype đã tồn tại chưa — chỉ ĐỌC, ⛔ dựng bảng."""
    try:
        # `cached=False`: cache `db_tables` có thể đã nạp trước lượt migrate —
        # đọc cache sẽ tưởng bảng chưa có và bỏ qua cổng/dữ liệu trong im lặng.
        return bool(frappe.db.table_exists(doctype, cached=False))
    except frappe.DoesNotExistError:
        return False


def _select(doctype, columns, order_by=None):
    """Đọc thẳng `tab<doctype>` bằng SQL thô (⛔ phụ thuộc DocType record).

    Sau khi patch migrate chạy, DocType cũ có thể đã bị xoá ở lần chạy trước
    nhưng bảng vẫn còn — cổng vẫn phải đọc được để báo đúng.
    """
    column_sql = ", ".join("`%s`" % column for column in columns)
    query = "select %s from `tab%s`" % (column_sql, doctype)
    if order_by:
        query += " order by " + order_by
    return frappe.db.sql(query, as_dict=True)


def _legacy_rule_codes(doctype):
    """Toàn bộ `rule_code` còn trong bảng cũ (bảng chưa có ⇒ [])."""
    if not _table_exists(doctype):
        return []
    rows = _select(doctype, ("rule_code",), order_by="`name` asc")
    return [row.get("rule_code") for row in rows if row.get("rule_code")]


def _target_rules():
    """`{rule_code: result_type}` của `AL Rule` (bảng chưa có ⇒ {})."""
    if not _table_exists("AL Rule"):
        return {}
    rows = _select("AL Rule", ("rule_code", "result_type"))
    return {
        row.get("rule_code"): row.get("result_type")
        for row in rows if row.get("rule_code")
    }


def _mismatches():
    """Danh sách mã nguồn thiếu/lệch trong `AL Rule` — nguồn sự thật của cổng."""
    targets = _target_rules()
    missing = []
    conflicts = []
    for source_doctype, expected_type in SOURCE_TYPES:
        for rule_code in _legacy_rule_codes(source_doctype):
            current_type = targets.get(rule_code)
            if current_type is None:
                missing.append("%s (từ %s)" % (rule_code, source_doctype))
            elif current_type != expected_type:
                conflicts.append(
                    "%s (AL Rule = %s, nguồn %s = %s)"
                    % (rule_code, current_type, source_doctype, expected_type))
    return missing, conflicts


def _assert_migrated():
    """CỔNG CHẶN: mọi rule cũ phải có `AL Rule` cùng mã + cùng loại kết quả.

    Thiếu/lệch ⇒ throw nêu danh sách, ⛔ xoá DocType nào.
    """
    missing, conflicts = _mismatches()
    if not missing and not conflicts:
        return

    parts = [
        "Không xoá được 2 DocType rule cũ: dữ liệu chưa migrate đủ sang "
        "`AL Rule`."
    ]
    if missing:
        parts.append(
            "%d mã CHƯA có trong `AL Rule`: %s."
            % (len(missing), ", ".join(missing)))
    if conflicts:
        parts.append(
            "%d mã LỆCH `result_type`: %s."
            % (len(conflicts), ", ".join(conflicts)))
    parts.append(
        "Chạy lại patch `alumglass.patches.v1_0.migrate_rules_to_al_rule` "
        "(hoặc sửa dữ liệu nguồn) rồi migrate lại — ⛔ xoá DocType khi còn "
        "rule chưa có bản tương ứng.")
    frappe.throw(" ".join(parts))


# ═══════════════════════════════════════════════════════════════════
# Xoá DocType record
# ═══════════════════════════════════════════════════════════════════
def _delete_doctype(doctype):
    """Xoá DocType record; không tồn tại ⇒ bỏ qua (idempotent).

    ⛔ DROP bảng dữ liệu — xem "DỌN BẢNG" ở docstring đầu tệp.
    """
    if not frappe.db.exists("DocType", doctype):
        return False

    try:
        frappe.delete_doc(
            "DocType", doctype, force=True, ignore_permissions=True)
    except Exception as exc:  # noqa: BLE001 — ghi rõ rồi ném, ⛔ nuốt
        message = (
            "Không xoá được DocType `%s` dù dữ liệu đã migrate: %s. "
            "DocType còn bị Link/Custom Field trỏ tới — gỡ các tham chiếu đó "
            "rồi chạy lại patch." % (doctype, exc))
        frappe.log_error(
            message=message, title="Xoá DocType rule cũ thất bại")
        frappe.throw(message)
    return True


# ═══════════════════════════════════════════════════════════════════
# Dọn Workflow mồ côi của doctype version cũ
# ═══════════════════════════════════════════════════════════════════
def _delete_legacy_workflow():
    """Xoá `Workflow` cũ nếu còn; không tồn tại ⇒ bỏ qua (idempotent).

    Chỉ đúng MỘT tên trong `LEGACY_WORKFLOW` — `AL Rule Version Workflow` và
    mọi Workflow khác ⛔ bị đụng.
    """
    if not LEGACY_WORKFLOW:
        return False
    if not frappe.db.exists("Workflow", LEGACY_WORKFLOW):
        return False

    try:
        frappe.delete_doc(
            "Workflow", LEGACY_WORKFLOW, force=True, ignore_permissions=True)
    except Exception as exc:  # noqa: BLE001 — ghi rõ rồi ném, ⛔ nuốt
        message = (
            "Không xoá được Workflow `%s` của doctype version cũ: %s. "
            "Gỡ tham chiếu tới Workflow này rồi chạy lại patch."
            % (LEGACY_WORKFLOW, exc))
        frappe.log_error(
            message=message, title="Xoá Workflow rule cũ thất bại")
        frappe.throw(message)
    return True
