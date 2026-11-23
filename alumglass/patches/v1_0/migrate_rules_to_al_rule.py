# -*- coding: utf-8 -*-
"""CHẶNG 2A — migrate dữ liệu 2 doctype rule cũ về `AL Rule`.

    AL Calculation Rule  (cột `result_value`) ⇒ AL Rule, result_type = NUMBER
    AL Dynamic Item Rule (cột `result_item`)  ⇒ AL Rule, result_type = ITEM

Hai nguồn NUMBER dùng LẠI đúng 2 bảng con đã có (`AL Rule Threshold Row`,
`AL Rule Lookup Row` — nay mang cả 2 cột kết quả); nguồn ITEM dùng 2 bảng con
của chính nó (`AL Dynamic Item Rule Threshold Row/Lookup Row`). Việc migrate
chỉ là chép dòng sang bảng con DÙNG CHUNG của `AL Rule`, KHÔNG đổi cấu trúc.

ĐỌC BẰNG BẢNG THẬT, ⛔ QUA DOCTYPE RECORD
─────────────────────────────────────────
Patch 2C (`delete_legacy_rule_doctypes`) xoá DOC TYPE RECORD của 5 doctype cũ
nhưng CỐ Ý ⛔ DROP bảng — bảng mồ côi còn làm đường cứu hộ một chu kỳ. Vì
vậy patch này đọc thẳng `tab<doctype>` bằng `frappe.db.sql`, có kiểm
`frappe.db.table_exists` trước mỗi lần đọc. Gọi `frappe.get_all`/`get_doc`
(đường đi qua meta DocType) sẽ chết khi DocType record đã bị xoá dù bảng vẫn
còn dữ liệu — đúng lượt migrate cần cứu hộ nhất.

NGUYÊN TẮC
──────────
1. CỔNG CHẶN TRÙNG MÃ: `rule_code` giao nhau giữa 2 bảng cũ ⇒ `frappe.throw`
   nêu DANH SÁCH mã trùng + hướng dẫn đổi mã ở một trong hai bên rồi chạy
   lại. ⛔ tự đổi mã — mã rule là hợp đồng với công thức/BOM đang chạy.
2. IDEMPOTENT: `AL Rule` cùng `rule_code` + cùng `result_type` ⇒ BỎ QUA.
   Cùng mã nhưng KHÁC `result_type` ⇒ THROW nêu mã + 2 loại (một mã không
   thể vừa trả số vừa trả mã Item).
3. VERSION: chép `AL Dynamic Item Rule Version` ⇒ `AL Rule Version`, giữ
   `rule` = mã rule. ⛔ chép bản ghi version của rule KHÔNG có `AL Rule` cùng
   mã (bản ghi mồ côi — `dry_run` báo ở khoá `orphan_version_rows`).
4. ⛔ XOÁ/ĐỔI bản ghi 2 bảng cũ — giữ nguyên để còn đường rollback.
5. ⛔ `frappe.db.commit()` — patch chạy trong transaction của `bench migrate`,
   tự commit sẽ làm hỏng khả năng rollback toàn bộ lượt migrate.
6. `current_version` KHÔNG chép: nguồn trỏ `AL Dynamic Item Rule Version`
   (bảng sắp mồ côi), đích trỏ `AL Rule Version` — chép nguyên giá trị là tạo
   Link gãy. Versioning hiện chưa có mã tạo bản ghi (xem `al_rule.py`).

KIỂM TRƯỚC KHI DEPLOY
─────────────────────
`dry_run()` chạy được TRƯỚC `bench migrate`, chỉ ĐỌC: trả số rule mỗi nguồn,
mã trùng giữa 2 nguồn, số mã đã có trong `AL Rule`, mã xung đột `result_type`,
số bản ghi version nguồn + mã rule mồ côi và cờ `ok`. Mục đích: biết trước site
có dữ liệu làm patch `throw` giữa lượt migrate hay không, ⛔ để `bench migrate`
chết dở dang.
"""

import frappe

TARGET_DOCTYPE = "AL Rule"
NUMBER_SOURCE = "AL Calculation Rule"
ITEM_SOURCE = "AL Dynamic Item Rule"
VERSION_SOURCE = "AL Dynamic Item Rule Version"
VERSION_TARGET = "AL Rule Version"

NUMBER_RESULT_FIELD = "result_value"
ITEM_RESULT_FIELD = "result_item"

THRESHOLD_ROW_FIELDS = (
    "from_value", "to_value", NUMBER_RESULT_FIELD, ITEM_RESULT_FIELD)
LOOKUP_ROW_FIELDS = ("key_field", NUMBER_RESULT_FIELD, ITEM_RESULT_FIELD)

VERSION_COLUMNS = (
    "rule", "version_name", "valid_from", "workflow_state",
    "rule_snapshot_json")

#: Mô tả 1 nguồn: bảng cha + 2 bảng con THẬT và loại kết quả tương ứng.
#: `parent_columns` / `columns` là cột CÓ THẬT trên bảng đó — nguồn ITEM
#: ⛔ có `constant_value`/`result_value` (chọn sai cột là lỗi SQL).
SOURCES = (
    {
        "doctype": NUMBER_SOURCE,
        "result_type": "NUMBER",
        "result_field": NUMBER_RESULT_FIELD,
        "parent_columns": (
            "name", "rule_code", "rule_name", "rule_type", "is_active",
            "constant_value"),
        "threshold_table": {
            "doctype": "AL Rule Threshold Row",
            "columns": ("from_value", "to_value", NUMBER_RESULT_FIELD),
        },
        "lookup_table": {
            "doctype": "AL Rule Lookup Row",
            "columns": ("key_field", NUMBER_RESULT_FIELD),
        },
    },
    {
        "doctype": ITEM_SOURCE,
        "result_type": "ITEM",
        "result_field": ITEM_RESULT_FIELD,
        "parent_columns": (
            "name", "rule_code", "rule_name", "rule_type", "is_active"),
        "threshold_table": {
            "doctype": "AL Dynamic Item Rule Threshold Row",
            "columns": ("from_value", "to_value", ITEM_RESULT_FIELD),
        },
        "lookup_table": {
            "doctype": "AL Dynamic Item Rule Lookup Row",
            "columns": ("key_field", ITEM_RESULT_FIELD),
        },
    },
)


def execute():
    """Điểm vào của patch (đăng ký ở `alumglass/patches.txt`)."""
    number_codes = _rule_codes(NUMBER_SOURCE)
    item_codes = _rule_codes(ITEM_SOURCE)

    _assert_no_duplicate_codes(number_codes, item_codes)

    for source in SOURCES:
        _migrate(source)

    _migrate_versions()


# ═══════════════════════════════════════════════════════════════════
# Đọc bảng thật
# ═══════════════════════════════════════════════════════════════════
def _table_exists(doctype):
    """Bảng của doctype đã tồn tại chưa — chỉ ĐỌC, ⛔ dựng bảng.

    Dùng ở `dry_run`: hàm này có thể chạy TRƯỚC lượt migrate (bảng `AL Rule`
    chưa được tạo) hoặc SAU khi DocType cũ đã bị xoá (bảng còn nhưng meta
    không còn). Gọi `frappe.get_all` lúc đó sẽ chết bằng lỗi meta, ⛔ phải là
    lỗi nghiệp vụ.
    """
    try:
        # `cached=False`: cache `db_tables` có thể đã được nạp TRƯỚC khi
        # `bench migrate` tạo `AL Rule`/`AL Rule Version` ⇒ đọc cache sẽ
        # tưởng bảng chưa có và BỎ QUA bước chép version trong im lặng.
        return bool(frappe.db.table_exists(doctype, cached=False))
    except frappe.DoesNotExistError:
        return False


def _select(doctype, columns, where=None, values=(), order_by=None):
    """Đọc thẳng `tab<doctype>` bằng SQL thô.

    ⛔ `frappe.get_all`: đường đó đi qua meta DocType, chết khi DocType record
    đã bị xoá dù bảng còn dữ liệu. Tên bảng/cột đều là hằng số trong tệp này
    (⛔ nhận từ ngoài) nên nối chuỗi an toàn.
    """
    column_sql = ", ".join("`%s`" % column for column in columns)
    query = "select %s from `tab%s`" % (column_sql, doctype)
    if where:
        query += " where " + where
    if order_by:
        query += " order by " + order_by
    return frappe.db.sql(query, values, as_dict=True)


def _rule_codes(doctype):
    """Toàn bộ `rule_code` của một bảng nguồn (⛔ qua DocType record)."""
    if not _table_exists(doctype):
        return []
    rows = _select(doctype, ("rule_code",), order_by="`name` asc")
    return [row.get("rule_code") for row in rows if row.get("rule_code")]


def _target_rules():
    """`{rule_code: result_type}` đang có trong `AL Rule` (bảng chưa có ⇒ {})."""
    if not _table_exists(TARGET_DOCTYPE):
        return {}
    rows = _select(TARGET_DOCTYPE, ("rule_code", "result_type"))
    return {
        row.get("rule_code"): row.get("result_type")
        for row in rows if row.get("rule_code")
    }


def _child_rows(source, parent, key):
    """Dòng con THẬT của 1 rule nguồn, đọc theo `parent` + `parenttype`."""
    spec = source[key]
    if not _table_exists(spec["doctype"]):
        return []
    rows = _select(
        spec["doctype"],
        spec["columns"],
        where="`parent` = %s and `parenttype` = %s",
        values=(parent, source["doctype"]),
        order_by="`idx` asc",
    )
    return _clean_rows(rows)


# ═══════════════════════════════════════════════════════════════════
# Cổng chặn trùng mã
# ═══════════════════════════════════════════════════════════════════
def _duplicate_codes(number_codes, item_codes):
    """Mã xuất hiện ở CẢ HAI bảng nguồn — nguồn sự thật duy nhất của cổng."""
    return sorted(set(number_codes) & set(item_codes))


def _assert_no_duplicate_codes(number_codes, item_codes):
    """CỔNG CHẶN: một `rule_code` không được xuất hiện ở CẢ HAI bảng nguồn.

    Phải chặn TRƯỚC khi ghi bất cứ dòng nào: nếu lọt, mã đó sẽ thành 2 bản
    `AL Rule` khác `result_type` và lần chạy sau sẽ chết ở nhánh xung đột.
    """
    duplicates = _duplicate_codes(number_codes, item_codes)
    if not duplicates:
        return
    frappe.throw(
        "Không migrate được rule: có %d mã trùng giữa `%s` và `%s`: %s.\n"
        "Mỗi mã quy tắc chỉ được thuộc MỘT loại kết quả (số hoặc mã Item). "
        "Đổi `rule_code` ở một trong hai doctype rồi chạy lại migrate."
        % (len(duplicates), NUMBER_SOURCE, ITEM_SOURCE, ", ".join(duplicates)))


# ═══════════════════════════════════════════════════════════════════
# Migrate rule + version
# ═══════════════════════════════════════════════════════════════════
def _migrate(source):
    """Chép toàn bộ bản ghi của 1 nguồn sang `AL Rule`."""
    if not _table_exists(source["doctype"]):
        return

    existing = _target_rules()
    rows = _select(
        source["doctype"], source["parent_columns"], order_by="`name` asc")

    for source_row in rows:
        rule_code = source_row.get("rule_code")
        existing_type = existing.get(rule_code)
        if existing_type is not None:
            if existing_type == source["result_type"]:
                # Đã migrate ở lần chạy trước ⇒ bỏ qua (idempotent).
                continue
            frappe.throw(
                "Không migrate rule '%s' từ `%s`: `%s` đã có cùng `rule_code` "
                "với result_type = %s (nguồn này là %s). Cùng một mã quy tắc "
                "không thể vừa trả số vừa trả mã Item — đổi `rule_code` ở một "
                "trong hai bên rồi chạy lại migrate."
                % (rule_code, source["doctype"], TARGET_DOCTYPE,
                   existing_type, source["result_type"]))

        data = _build_data(
            source_row,
            source,
            _child_rows(source, source_row.get("name"), "threshold_table"),
            _child_rows(source, source_row.get("name"), "lookup_table"),
        )
        frappe.get_doc(data).insert(ignore_permissions=True)
        existing[rule_code] = source["result_type"]


def _build_data(source_row, source, threshold_rows, lookup_rows):
    """Dựng dict nguồn cho `AL Rule` (⛔ chép `current_version` — xem 6)."""
    return {
        "doctype": TARGET_DOCTYPE,
        "rule_code": source_row.get("rule_code"),
        # `rule_name` nay là field BẮT BUỘC (`reqd`) trên `AL Rule` — bản ghi
        # nguồn chưa đặt tên sẽ bị chặn khi insert. Điền bằng `rule_code` để
        # bản ghi migrate xong vẫn lưu được và vẫn có nhãn người-đọc-được;
        # quản trị đổi lại tên sau trên form.
        "rule_name": source_row.get("rule_name") or source_row.get("rule_code"),
        "rule_type": source_row.get("rule_type"),
        "result_type": source["result_type"],
        "is_active": source_row.get("is_active"),
        "constant_value": source_row.get("constant_value"),
        "threshold_rows": threshold_rows,
        "lookup_rows": lookup_rows,
    }


def _clean_rows(rows):
    """Bỏ field rỗng để mỗi dòng chỉ mang đúng cột kết quả của nguồn.

    `0` là giá trị HỢP LỆ cho cột kết quả, ⛔ bỏ nhầm (bẫy truthiness).
    """
    out = []
    for row in rows or []:
        data = {}
        for field in THRESHOLD_ROW_FIELDS + LOOKUP_ROW_FIELDS:
            value = row.get(field)
            if value is None or value == "":
                continue
            data[field] = value
        out.append(data)
    return out


def _version_rows():
    """Bản ghi `AL Dynamic Item Rule Version` đọc từ bảng thật (⛔ meta)."""
    if not _table_exists(VERSION_SOURCE):
        return []
    return _select(VERSION_SOURCE, VERSION_COLUMNS, order_by="`name` asc")


def _orphan_version_codes(version_rows, target_rules):
    """Mã rule của version KHÔNG có `AL Rule` cùng mã — ⛔ chép các bản ghi này."""
    return sorted({
        row.get("rule") for row in version_rows
        if row.get("rule") and row.get("rule") not in target_rules
    })


def _existing_version_keys():
    """Khoá (rule, version_name, valid_from) đã có trong `AL Rule Version`."""
    if not _table_exists(VERSION_TARGET):
        return set()
    rows = _select(VERSION_TARGET, ("rule", "version_name", "valid_from"))
    return {
        (row.get("rule"), row.get("version_name"), row.get("valid_from"))
        for row in rows
    }


def _migrate_versions():
    """Chép bản ghi version sang `AL Rule Version` (idempotent theo khoá)."""
    if not _table_exists(VERSION_TARGET):
        return

    target_rules = _target_rules()
    seen = _existing_version_keys()

    for row in _version_rows():
        rule_code = row.get("rule")
        if not rule_code or rule_code not in target_rules:
            # Version mồ côi (rule không tồn tại trong `AL Rule`) ⇒ ⛔ chép.
            continue

        key = (rule_code, row.get("version_name"), row.get("valid_from"))
        if key in seen:
            continue

        frappe.get_doc({
            "doctype": VERSION_TARGET,
            "rule": rule_code,
            "version_name": row.get("version_name"),
            "valid_from": row.get("valid_from"),
            "workflow_state": row.get("workflow_state"),
            "rule_snapshot_json": row.get("rule_snapshot_json"),
        }).insert(ignore_permissions=True)
        seen.add(key)


# ═══════════════════════════════════════════════════════════════════
# Kiểm trước khi deploy
# ═══════════════════════════════════════════════════════════════════
def _existing_conflicts(codes_by_type):
    """Đếm bản ghi đã có + mã XUNG ĐỘT loại trong `AL Rule` (chỉ đọc).

    `codes_by_type` = {rule_code: "NUMBER"|"ITEM"} suy từ 2 nguồn. Trả
    `(existing_count, conflict_codes)`:
      - `existing_count`: mã đã có trong `AL Rule` (idempotent sẽ bỏ qua);
      - `conflict_codes`: mã đã có nhưng KHÁC `result_type` (lượt migrate
        thật sẽ `throw`).
    """
    existing_map = _target_rules()
    existing = 0
    conflicts = []
    for rule_code, expected_type in sorted(codes_by_type.items()):
        current_type = existing_map.get(rule_code)
        if current_type is None:
            continue
        existing += 1
        if current_type != expected_type:
            conflicts.append(rule_code)
    return existing, sorted(conflicts)


@frappe.whitelist()
def dry_run():
    """Chạy TRƯỚC khi deploy/migrate — chỉ ĐỌC, ⛔ ghi gì.

    Vì sao cần: patch chạy ở `[post_model_sync]`; nếu site có mã trùng hoặc
    mã xung đột loại thì patch `throw` ⇒ `bench migrate` chết GIỮA lượt,
    trong khi mã mới (engine đọc `AL Rule`) đã deploy ⇒ site dở dang. Hàm
    này cho người chạy biết trước để xử lý dữ liệu trước khi migrate.

    Khoá `version_rows` = số bản ghi version nguồn đọc được;
    `orphan_version_rows` = mã rule của các bản ghi đó mà `AL Rule` KHÔNG có
    cùng mã (sẽ bị bỏ qua khi migrate). Khi bảng `AL Rule` chưa được tạo
    (`al_rule_ready = False`) thì chưa phân biệt được mồ côi ⇒ trả `[]`.

    ⛔ ném khi có xung đột (đây là hàm KIỂM, kết quả nằm trong dict):
      `ok = True` chỉ khi `duplicate_codes` và `conflict_codes` đều rỗng.
    """
    number_codes = _rule_codes(NUMBER_SOURCE)
    item_codes = _rule_codes(ITEM_SOURCE)
    duplicate_codes = _duplicate_codes(number_codes, item_codes)

    # Loại kết quả MONG ĐỢI của từng mã theo nguồn. Mã trùng (đã báo ở
    # `duplicate_codes`) giữ loại của nguồn NUMBER — vẫn đủ để phát hiện
    # xung đột với bản ghi có sẵn; `ok` đã False vì trùng mã.
    codes_by_type = {}
    for code in number_codes:
        codes_by_type.setdefault(code, "NUMBER")
    for code in item_codes:
        codes_by_type.setdefault(code, "ITEM")

    target_ready = _table_exists(TARGET_DOCTYPE)
    versions = _version_rows()
    if target_ready:
        existing_count, conflict_codes = _existing_conflicts(codes_by_type)
        orphan_version_rows = _orphan_version_codes(versions, _target_rules())
    else:
        # Bảng `AL Rule` chưa được tạo (chạy TRƯỚC migrate): chưa thể có
        # bản ghi nào để trùng/xung đột ⇒ 0, ⛔ coi là lỗi.
        existing_count, conflict_codes = 0, []
        orphan_version_rows = []

    return {
        "number_rules": len(number_codes),
        "item_rules": len(item_codes),
        "duplicate_codes": duplicate_codes,
        "existing_in_al_rule": existing_count,
        "conflict_codes": conflict_codes,
        "version_rows": len(versions),
        "orphan_version_rows": orphan_version_rows,
        "al_rule_ready": target_ready,
        "ok": not duplicate_codes and not conflict_codes,
    }
