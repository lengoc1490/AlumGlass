# -*- coding: utf-8 -*-
"""AL Rule — DocType CHUẨN cho mọi quy tắc của AlumGlass.

Thay cho hai doctype rule song song trước đây (đã xoá 2026-11-23). Hai bên
dùng CÙNG khái niệm (CONSTANT / dải ngưỡng / tra bảng), chỉ khác cột kết
quả — nay cột kết quả do field `result_type` quyết định:

    result_type = NUMBER ⇒ `result_value` (Float)
    result_type = ITEM   ⇒ `result_item`  (Link → Item)

Hai bảng con DÙNG CHUNG (`AL Rule Threshold Row` và `AL Rule Lookup Row`)
mỗi dòng mang CẢ HAI cột kết quả, nên `validate()` bắt buộc đúng MỘT cột có
giá trị theo `result_type`.

⚠️ VERSIONING — CHỈ GIỮ PARITY, CHƯA CÓ MÃ:
    DocType `AL Rule Version` + Workflow "AL Rule Version Workflow" đã được
    tạo (dữ liệu version cũ đã được patch migrate chép sang), nhưng **hiện
    KHÔNG có mã nào tạo bản ghi version MỚI** — không hook/controller/scheduler
    nào tự sinh bản ghi khi Lưu `AL Rule`; field `current_version` sẽ để
    trống. Đây là chỗ GIỮ CHỖ để chặng sau gắn versioning thật. ⛔ được tuyên
    bố là "đã có version" cho tới khi mã đó tồn tại.
"""

import frappe
from frappe.model.document import Document

from alumglass.al_formula_rules import rule_engine

DOCTYPE_LABEL = "AL Rule"

#: `result_type` → tên cột kết quả trên 2 bảng con dùng chung.
RESULT_FIELD_BY_TYPE = {
    "NUMBER": "result_value",
    "ITEM": "result_item",
}

RULE_TYPES = ("CONSTANT", "THRESHOLD", "LOOKUP")


def _missing(value):
    """Rỗng thật sự — `0` / `0.0` là GIÁ TRỊ HỢP LỆ cho cột kết quả."""
    return value is None or value == ""


class ALRule(Document):
    """Quy tắc CONSTANT / THRESHOLD / LOOKUP dùng chung cho số và mã Item."""

    @property
    def result_field(self):
        """Cột kết quả suy từ `result_type` (None nếu giá trị không hợp lệ)."""
        return RESULT_FIELD_BY_TYPE.get(self.result_type)

    def validate(self):
        if self.result_type not in RESULT_FIELD_BY_TYPE:
            frappe.throw(
                "%s: Result Type phải là NUMBER hoặc ITEM (đang là %r)"
                % (DOCTYPE_LABEL, self.result_type))
        if self.rule_type not in RULE_TYPES:
            frappe.throw(
                "%s: Rule Type phải là CONSTANT, THRESHOLD hoặc LOOKUP "
                "(đang là %r)" % (DOCTYPE_LABEL, self.rule_type))

        # CONSTANT chỉ có nghĩa với kết quả SỐ — "hằng số là một mã Item"
        # không có nghĩa nghiệp vụ nào (chọn mã phải theo ngưỡng hoặc bảng).
        if self.rule_type == "CONSTANT" and self.result_type == "ITEM":
            frappe.throw(
                "%s: rule CONSTANT không dùng được với Result Type = ITEM — "
                "chọn mã vật tư phải theo THRESHOLD hoặc LOOKUP." % DOCTYPE_LABEL)

        if self.rule_type == "CONSTANT":
            if _missing(self.constant_value):
                frappe.throw("%s: CONSTANT rule cần Constant Value" % DOCTYPE_LABEL)
        elif self.rule_type == "THRESHOLD":
            self._require_rows(self.threshold_rows, "THRESHOLD")
            rule_engine.validate_threshold_rows(
                self.threshold_rows, self.result_field, DOCTYPE_LABEL)
            self._validate_result_columns(self.threshold_rows)
        elif self.rule_type == "LOOKUP":
            self._require_rows(self.lookup_rows, "LOOKUP")
            self._validate_result_columns(self.lookup_rows)

    def _require_rows(self, rows, rule_type):
        if not rows:
            frappe.throw(
                "%s: rule %s cần ít nhất 1 dòng" % (DOCTYPE_LABEL, rule_type))

    def _validate_result_columns(self, rows):
        """Mỗi dòng đúng MỘT cột kết quả theo `result_type`.

        NUMBER ⇒ có `result_value`, KHÔNG có `result_item`.
        ITEM   ⇒ có `result_item`, KHÔNG có `result_value`.
        """
        field = self.result_field
        other = "result_item" if field == "result_value" else "result_value"
        field_label = rule_engine.RESULT_LABELS.get(field, field)
        other_label = rule_engine.RESULT_LABELS.get(other, other)
        expected = "NUMBER" if field == "result_value" else "ITEM"

        for index, row in enumerate(rows, start=1):
            if _missing(row.get(field)):
                frappe.throw(
                    "%s dòng %d: cần %s (Result Type = %s)"
                    % (DOCTYPE_LABEL, index, field_label, expected))
            if not _missing(row.get(other)):
                frappe.throw(
                    "%s dòng %d: Result Type = %s nên %s phải để trống "
                    "(chỉ dùng MỘT cột kết quả mỗi dòng)"
                    % (DOCTYPE_LABEL, index, expected, other_label))

    def resolve(self, input_value):
        """Trả giá trị (NUMBER) hoặc mã Item (ITEM); None khi rule TẮT."""
        # Rule đã TẮT ⇒ không dùng; nơi gọi có trách nhiệm ghi cảnh báo (xem
        # chặng 1 ở `bom_orchestrator`), ⛔ được để lượt tính giá chết.
        if not rule_engine.rule_is_active(self):
            return None

        field = self.result_field
        if not field:
            return None

        if self.rule_type == "CONSTANT":
            # CONSTANT + ITEM đã bị validate chặn; ở đây trả None cho an toàn
            # với dữ liệu cũ/import tay.
            return self.constant_value if field == "result_value" else None

        if input_value is None or input_value == "":
            return None

        if self.rule_type == "THRESHOLD":
            return rule_engine.resolve_threshold(
                self.threshold_rows, input_value, field)

        if self.rule_type == "LOOKUP":
            for row in self.lookup_rows or []:
                if str(row.get("key_field")) == str(input_value):
                    return row.get(field)

        return None


@frappe.whitelist()
def resolve_item(rule_code, input_value):
    """API: Tra cứu mã Item từ `AL Rule`. Trả `{item_code, item_name}`/None.

    Chặng 2B — `AL Rule` gộp 2 loại: chỉ rule `result_type = ITEM` mới trả
    được mã vật tư. Rule trả SỐ lọt vào đây là lỗi cấu hình ⇒ throw câu
    người-đọc-được (nêu tên quy tắc + việc cần làm), ⛔ trả None im lặng.
    """
    doc = frappe.get_cached_doc(DOCTYPE_LABEL, rule_code)
    # Nhãn người-đọc-được: `rule_name`, fallback mã khi quy tắc chưa đặt tên.
    rule_label = doc.get("rule_name") or rule_code
    if (doc.get("result_type") or "") != "ITEM":
        frappe.throw(
            "Quy tắc \"%s\" là quy tắc tính giá trị, không phải quy tắc chọn "
            "mã — không tra được mã vật tư. Chọn một quy tắc chọn mã (Result "
            "Type = ITEM)." % rule_label)
    result = doc.resolve(input_value)
    if result:
        return {
            "item_code": result,
            "item_name": frappe.db.get_value("Item", result, "item_name"),
        }
    return None
