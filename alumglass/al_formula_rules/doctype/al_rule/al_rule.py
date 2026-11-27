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
from alumglass.al_formula_rules import rule_input

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


def _format_number_vi(value):
    """Số hiển thị kiểu Việt cho câu thông báo: 10 → '10', 10.38 → '10,38'."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        return str(int(number))
    return ("%.6f" % number).rstrip("0").rstrip(".").replace(".", ",")


def _num_or_none(value):
    """Ép số cho `matched`/`rows`; giá trị không phải số ⇒ None (client tự xử)."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _preview_number(value):
    """Đọc số từ ô "Thử tra" — nhận cả dấu phẩy thập phân kiểu Việt.

    Người dùng gõ `10,385` (đúng cách viết trong tài liệu/nghiệp vụ) mà
    `float()` từ chối ⇒ màn thử tra báo "không phải số" oan. Quy ước:
      - có CẢ `.` và `,` ⇒ `.` là phân cách nghìn, `,` là dấu thập phân
        (`1.234,5` → 1234.5);
      - chỉ có `,` ⇒ dấu thập phân (`10,385` → 10.385);
      - không đọc được ⇒ trả NGUYÊN giá trị để câu báo lỗi nêu đúng cái đã gõ.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    text = str(value or "").strip().replace(" ", "")
    if not text:
        return value
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except (TypeError, ValueError):
        return value


def _threshold_miss_message(rows, input_value, input_label):
    """Câu người-đọc-được khi giá trị KHÔNG khớp dải ngưỡng nào.

    Nêu đúng KHE đang trống (nếu có) thay vì câu chung "không khớp" — người
    cấu hình đọc xong biết phải sửa dải nào (thiết kế §3.2: `10,385` phải
    nêu dải trống, ⛔ màn hình trống).
    """
    label = input_label or "Giá trị"
    try:
        val = float(input_value)
    except (TypeError, ValueError):
        return ('%s "%s" không phải là số — quy tắc ngưỡng cần một giá trị số. '
                'Nhập lại giá trị bằng số.' % (label, input_value))

    rows = rule_engine.sorted_threshold_rows(rows)
    for index in range(len(rows) - 1):
        to_raw = rule_engine.row_field(rows[index], "to_value")
        # Dải để trống "Đến" là dải MỞ phía trên (+∞) ⇒ ⛔ có khe phía trên
        # nó; đọc `to` rỗng thành 0 sẽ báo khe "0 – …" oan.
        if to_raw is None or to_raw == "":
            continue
        to_value = rule_engine.as_number(to_raw)
        next_from = rule_engine.as_number(
            rule_engine.row_field(rows[index + 1], "from_value"))
        if to_value < val < next_from:
            return (
                '%s %s không khớp dải nào — đang trống khoảng %s – %s. '
                'Sửa dải cho liền nhau: dải sau bắt đầu đúng bằng giá trị '
                '"đến" của dải trước.'
                % (label, _format_number_vi(val),
                   _format_number_vi(to_value),
                   _format_number_vi(next_from)))

    if rows:
        first_from = rule_engine.as_number(
            rule_engine.row_field(rows[0], "from_value"))
        last_to_raw = rule_engine.row_field(rows[-1], "to_value")
        if val < first_from:
            return (
                '%s %s nằm dưới dải thấp nhất — dải đầu bắt đầu từ %s. '
                'Thêm hoặc sửa dải để phủ giá trị này.'
                % (label, _format_number_vi(val),
                   _format_number_vi(first_from)))
        # Dải cuối MỞ phía trên (+∞) thì không có giá trị nào "nằm trên dải
        # cao nhất" — câu cũ đọc `to` rỗng thành 0 nên báo sai "kết thúc ở 0".
        if last_to_raw is not None and last_to_raw != "":
            last_to = rule_engine.as_number(last_to_raw)
            if val > last_to:
                return (
                    '%s %s nằm trên dải cao nhất — dải cuối kết thúc ở %s. '
                    'Thêm hoặc sửa dải để phủ giá trị này.'
                    % (label, _format_number_vi(val),
                       _format_number_vi(last_to)))
    return ('%s %s không khớp dải nào của quy tắc — kiểm tra lại các dải '
            'ngưỡng.' % (label, _format_number_vi(val)))


def _lookup_miss_message(rows, input_value, input_label):
    """Câu người-đọc-được khi giá trị KHÔNG có trong bảng tra.

    Nêu các khoá ĐANG CÓ để người cấu hình thấy ngay mình gõ sai hay bảng
    còn thiếu dòng.
    """
    label = input_label or "Giá trị"
    keys = []
    for row in rows or []:
        key = rule_engine.row_field(row, "key_field")
        if key is None or key == "":
            continue
        text = str(key)
        if text not in keys:
            keys.append(text)
    shown = ", ".join(keys[:10]) + (" …" if len(keys) > 10 else "")
    return (
        '%s "%s" không có trong bảng tra. Bảng đang có khoá: %s. Thêm dòng '
        'cho giá trị này hoặc sửa lại khoá.'
        % (label, input_value, shown or "(chưa có khoá nào)"))


class ALRule(Document):
    """Quy tắc CONSTANT / THRESHOLD / LOOKUP dùng chung cho số và mã Item."""

    @property
    def result_field(self):
        """Cột kết quả suy từ `result_type` (None nếu giá trị không hợp lệ)."""
        return RESULT_FIELD_BY_TYPE.get(self.result_type)

    def validate(self):
        # Chặng 3 (§7.1): suy phạm vi dữ liệu tra + điền nhãn — metadata hiển
        # thị, ⛔ đổi logic resolve/kết quả tính tiền.
        self._sync_input_variable()
        if self.result_type not in RESULT_FIELD_BY_TYPE:
            frappe.throw(
                "%s: chưa chọn đúng Loại kết quả — chọn \"%s\" nếu quy tắc "
                "tính ra số, hoặc \"%s\" nếu quy tắc chọn mã hàng."
                % (DOCTYPE_LABEL,
                   rule_engine.RESULT_TYPE_LABELS["NUMBER"],
                   rule_engine.RESULT_TYPE_LABELS["ITEM"]))
        if self.rule_type not in RULE_TYPES:
            frappe.throw(
                "%s: chưa chọn đúng Kiểu quy tắc — chọn \"%s\", \"%s\" hoặc "
                "\"%s\"."
                % (DOCTYPE_LABEL,
                   rule_engine.RULE_TYPE_LABELS["CONSTANT"],
                   rule_engine.RULE_TYPE_LABELS["THRESHOLD"],
                   rule_engine.RULE_TYPE_LABELS["LOOKUP"]))

        # CONSTANT chỉ có nghĩa với kết quả SỐ — "hằng số là một mã Item"
        # không có nghĩa nghiệp vụ nào (chọn mã phải theo ngưỡng hoặc bảng).
        if self.rule_type == "CONSTANT" and self.result_type == "ITEM":
            frappe.throw(
                "%s: quy tắc %s không dùng được với kết quả là %s — muốn chọn "
                "mã hàng thì dùng kiểu %s hoặc %s."
                % (DOCTYPE_LABEL,
                   rule_engine.RULE_TYPE_LABELS["CONSTANT"],
                   rule_engine.RESULT_TYPE_LABELS["ITEM"],
                   rule_engine.RULE_TYPE_LABELS["THRESHOLD"],
                   rule_engine.RULE_TYPE_LABELS["LOOKUP"]))

        if self.rule_type == "CONSTANT":
            if _missing(self.constant_value):
                frappe.throw(
                    "%s: quy tắc %s cần nhập Giá trị cố định — điền giá trị "
                    "vào ô \"Giá trị cố định\"."
                    % (DOCTYPE_LABEL, rule_engine.RULE_TYPE_LABELS["CONSTANT"]))
        elif self.rule_type == "THRESHOLD":
            self._require_rows(self.threshold_rows, "THRESHOLD")
            rule_engine.validate_threshold_rows(
                self.threshold_rows, self.result_field, DOCTYPE_LABEL)
            self._validate_result_columns(self.threshold_rows)
        elif self.rule_type == "LOOKUP":
            self._require_rows(self.lookup_rows, "LOOKUP")
            self._validate_result_columns(self.lookup_rows)

    def _sync_input_variable(self):
        """Suy `input_scope` từ nhóm của biến (`AL Variable Library.group_label`) + điền nhãn.

        Chặng 3 (§7.1): biến thuộc nhóm "Row Literals" ⇒ dữ liệu theo TỪNG
        DÒNG (`ROW`), còn lại ⇒ biến TOÀN CỤC (`GLOBAL`). `input_label` để
        trống ⇒ lấy `var_label` của biến (vẫn sửa tay được). Chỉ đổi
        metadata hiển thị — `resolve()`/engine giữ nguyên hành vi.

        Không đọc được `AL Variable Library` (site chưa migrate, lỗi DB) ⇒
        coi như biến toàn cục, ⛔ chặn Lưu quy tắc.
        """
        var = (self.get("input_variable") or "").strip()
        if not var:
            if not (self.get("input_scope") or "").strip():
                self.input_scope = rule_input.GLOBAL_SCOPE
            return
        meta = rule_input.variable_meta(var)
        self.input_scope = (
            rule_input.ROW_SCOPE
            if (meta.get("group_label") or "").strip()
            == rule_input.ROW_LITERAL_CATEGORY
            else rule_input.GLOBAL_SCOPE)
        if not (self.get("input_label") or "").strip():
            # ⛔ Fallback về tên biến (`var`) — nhãn này hiện trên form và đi
            # vào câu cảnh báo; biến chưa có `var_label` thì dùng câu chung.
            self.input_label = (
                (meta.get("var_label") or "").strip()
                or rule_engine.INPUT_LABEL_FALLBACK)
        if (self.input_scope == rule_input.ROW_SCOPE
                and not rule_input.is_row_variable_resolvable(var)):
            # CẢNH BÁO, ⛔ throw: biến theo dòng nhưng engine KHÔNG nạp ở bước
            # chọn mã (vd `width`, `qty`, `total_qty`) ⇒ dòng hàng ra 0 âm
            # thầm. Dữ liệu cũ có thể đang ở trạng thái này nên chỉ cảnh báo.
            # Câu TRUNG TÍNH: ⛔ kể tên cụ thể ("Độ dày kính hoặc Loại kính")
            # — biến theo dòng không chỉ có 2 loại đó, và danh sách mời ở ô
            # "Tra theo" đã tự lọc đúng dữ liệu engine đọc được.
            # ⛔ Lấy tên biến kỹ thuật làm nhãn (xem `rule_input_label`).
            frappe.msgprint(
                "Dữ liệu tra '%s' chưa có giá trị ở bước chọn mã nên quy tắc "
                "sẽ không tra được — chọn một dữ liệu khác trong ô "
                "<b>Tra theo</b> (danh sách chỉ mời dữ liệu hệ thống đọc "
                "được ở bước chọn mã)."
                % rule_engine.rule_input_label({
                    "input_variable": var,
                    "input_label": (
                        (self.get("input_label") or "").strip()
                        or (meta.get("var_label") or "").strip()),
                }),
                title="AL Rule — Cảnh báo dữ liệu tra",
                indicator="orange",
            )

    def _require_rows(self, rows, rule_type):
        if not rows:
            section = ("Bảng tra" if rule_type == "LOOKUP" else "Bảng ngưỡng")
            frappe.throw(
                "%s: quy tắc %s cần ít nhất 1 dòng điều kiện — thêm dòng ở mục "
                "\"%s\"."
                % (DOCTYPE_LABEL, rule_engine.rule_type_label(rule_type).lower(),
                   section))

    def _validate_result_columns(self, rows):
        """Mỗi dòng đúng MỘT cột kết quả theo `result_type`.

        NUMBER ⇒ có `result_value`, KHÔNG có `result_item`.
        ITEM   ⇒ có `result_item`, KHÔNG có `result_value`.
        """
        field = self.result_field
        other = "result_item" if field == "result_value" else "result_value"
        field_label = rule_engine.RESULT_LABELS.get(field, field)
        other_label = rule_engine.RESULT_LABELS.get(other, other)
        result_label = rule_engine.result_type_label(
            "NUMBER" if field == "result_value" else "ITEM")

        for index, row in enumerate(rows, start=1):
            if _missing(row.get(field)):
                frappe.throw(
                    "%s dòng %d: cột \"%s\" đang để trống — điền giá trị cho "
                    "dòng này, hoặc đổi Loại kết quả của quy tắc (đang là "
                    "\"%s\") nếu chọn nhầm."
                    % (DOCTYPE_LABEL, index, field_label, result_label))
            if not _missing(row.get(other)):
                frappe.throw(
                    "%s dòng %d: Loại kết quả của quy tắc đang là \"%s\" nên "
                    "%s phải để trống (mỗi dòng chỉ dùng MỘT cột kết quả) — "
                    "xoá giá trị thừa hoặc đổi Loại kết quả."
                    % (DOCTYPE_LABEL, index, result_label, other_label))

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
            row = rule_engine.match_lookup_row(self.lookup_rows, input_value)
            return row.get(field) if row is not None else None

        return None

    # ── "Thử tra" — hợp đồng chung cho form và API (`api.preview_rule`) ──
    def preview(self, input_value=None):
        """Thử tra 1 giá trị trên chính quy tắc này — KHÔNG ghi DB.

        Hợp đồng (thiết kế `docs/design/tra-cuu-quy-tac-de-hieu.md` §3.2)::

            {success, rule_code, rule_name, rule_description,
             rule_type, result_type, input_label, input_unit, output_label,
             input_variable, input_scope, input_resolvable,
             is_active, input_value,
             matched: {kind: "range"|"key"|"constant", from, to, key} | null,
             result:  {value} | {item_code, item_name} | null,
             rows:    [{from, to, key, result_text, is_match}],
             message: "" | "<câu người-đọc-được>"}

        Trạng thái NGHIỆP VỤ (quy tắc tắt / không khớp / chưa có dòng /
        chưa nhập giá trị) ⇒ `success: True` + `message` nêu việc cần làm,
        ⛔ throw. Lỗi dữ liệu quy tắc (thiếu `result_type`...) cũng trả câu
        người-đọc-được, ⛔ phơi mã kỹ thuật.

        Logic khớp dùng ĐÚNG `rule_engine` của đường tính giá
        (`match_threshold_row` / `match_lookup_row`) — ⛔ viết lại lần hai.
        """
        rule_type = self.get("rule_type") or ""
        result_type = self.get("result_type") or ""
        field = self.result_field
        is_active = rule_engine.rule_is_active(self)
        rule_name = self.get("rule_name") or ""
        rule_label = rule_name or self.get("rule_code") or self.get("name") or ""
        input_label = self.get("input_label") or ""
        # Chặng 3: quy tắc tự khai biến đem tra — nhãn hiển thị ưu tiên
        # `input_label`, thiếu thì lấy `var_label` của biến.
        input_cfg = rule_input.rule_input_config(self)
        # Nhãn dùng trong CÂU cho người dùng: ⛔ bao giờ để lọt tên biến kỹ
        # thuật (`total_thick_mm`...) — quy tắc chưa có nhãn đọc được thì
        # dùng câu chung (xem `rule_engine.rule_input_label`).
        message_input_label = (
            rule_engine.rule_input_label(input_cfg) if input_cfg else "")
        # Biến theo dòng mà engine KHÔNG nạp ở bước chọn mã (vd `width`) ⇒
        # tra sẽ ra 0 âm thầm; client dùng cờ này để cảnh báo trước khi thử.
        input_resolvable = True
        if input_cfg.get("input_variable") and (
                input_cfg.get("input_scope") == rule_input.ROW_SCOPE):
            input_resolvable = rule_input.is_row_variable_resolvable(
                input_cfg.get("input_variable"))
        has_input = input_value is not None and input_value != ""

        if rule_type == "THRESHOLD":
            rows = rule_engine.sorted_threshold_rows(
                self.get("threshold_rows") or [])
        elif rule_type == "LOOKUP":
            rows = list(self.get("lookup_rows") or [])
        else:
            rows = []

        matched = None
        matched_row = None
        result = None
        message = ""

        if not is_active:
            message = ('Quy tắc "%s" đang tắt nên chưa tra được — bật lại quy '
                       'tắc (ô "Đang dùng?") rồi thử lại.' % rule_label)
        elif not field:
            message = ('Quy tắc chưa khai đúng "Loại kết quả" — chọn "Số" nếu '
                       'quy tắc tính ra số, hoặc "Mã vật tư" nếu quy tắc chọn '
                       'mã hàng, rồi lưu lại.')
        elif rule_type == "CONSTANT":
            if field == "result_value":
                matched = {"kind": "constant", "from": None, "to": None,
                           "key": None}
                result = {"value": self.get("constant_value")}
            else:
                message = ('Quy tắc hằng số không dùng để trả mã vật tư — '
                           'chọn loại quy tắc theo dải hoặc bảng tra, rồi lưu '
                           'lại quy tắc.')
        elif rule_type not in ("THRESHOLD", "LOOKUP"):
            message = ('Loại quy tắc chưa hợp lệ nên chưa thử tra được — mở '
                       'form quy tắc chọn lại "Kiểu quy tắc" rồi lưu.')
        elif not rows:
            if rule_type == "THRESHOLD":
                message = ('Quy tắc chưa có dòng ngưỡng nào — mở mục '
                           '"Bảng ngưỡng" và thêm dải.')
            else:
                message = ('Quy tắc chưa có dòng tra bảng nào — mở mục '
                           '"Bảng tra" và thêm khoá.')
        elif not has_input:
            if input_cfg.get("input_variable"):
                # Quy tắc đã khai biến ⇒ câu nêu ĐÚNG dữ liệu đem tra để
                # quản trị biết nhập gì, ⛔ throw (§7.3).
                message = 'Quy tắc tra theo %s — nhập giá trị để thử.' % (
                    message_input_label)
            else:
                message = 'Nhập %s cần tra để xem kết quả.' % (
                    input_label or "giá trị")

        if not message and rule_type in ("THRESHOLD", "LOOKUP"):
            if rule_type == "THRESHOLD":
                # Nhận dấu phẩy thập phân người dùng gõ trong ô "Thử tra".
                lookup_value = _preview_number(input_value)
                matched_row = rule_engine.match_threshold_row(
                    rows, lookup_value)
            else:
                lookup_value = input_value
                matched_row = rule_engine.match_lookup_row(rows, input_value)
            if matched_row is None:
                if rule_type == "THRESHOLD":
                    message = _threshold_miss_message(
                        rows, lookup_value, message_input_label)
                else:
                    message = _lookup_miss_message(
                        rows, input_value, message_input_label)
            else:
                if rule_type == "THRESHOLD":
                    matched = {
                        "kind": "range",
                        "from": _num_or_none(
                            rule_engine.row_field(matched_row, "from_value")),
                        "to": _num_or_none(
                            rule_engine.row_field(matched_row, "to_value")),
                        "key": None,
                    }
                else:
                    matched = {
                        "kind": "key",
                        "from": None,
                        "to": None,
                        "key": str(rule_engine.row_field(
                            matched_row, "key_field") or ""),
                    }
                result = self._preview_result(matched_row, field)

        item_names = self._preview_item_names(rows, field)
        rows_out = []
        for row in rows:
            if rule_type == "THRESHOLD":
                row_from = _num_or_none(
                    rule_engine.row_field(row, "from_value"))
                row_to = _num_or_none(
                    rule_engine.row_field(row, "to_value"))
                row_key = None
            else:
                row_from = None
                row_to = None
                row_key = str(
                    rule_engine.row_field(row, "key_field") or "")
            rows_out.append({
                "from": row_from,
                "to": row_to,
                "key": row_key,
                "result_text": self._preview_result_text(
                    row, field, item_names),
                "is_match": 1 if row is matched_row else 0,
            })

        return {
            "success": True,
            "rule_code": self.get("rule_code") or self.get("name") or "",
            "rule_name": rule_name,
            "rule_description": self.get("rule_description") or "",
            "rule_type": rule_type,
            "result_type": result_type,
            "input_label": input_label,
            "input_unit": self.get("input_unit") or "",
            "input_variable": self.get("input_variable") or "",
            "input_scope": self.get("input_scope") or "",
            "input_resolvable": bool(input_resolvable),
            "output_label": self.get("output_label") or "",
            "is_active": 1 if is_active else 0,
            "input_value": None if not has_input else input_value,
            "matched": matched,
            "result": result,
            "rows": rows_out,
            "message": message,
        }

    @staticmethod
    def _preview_result(row, field):
        """Kết quả của 1 dòng: `{value}` (NUMBER) hoặc `{item_code,item_name}`."""
        if field == "result_item":
            item_code = rule_engine.row_field(row, "result_item") or ""
            return {
                "item_code": item_code,
                "item_name": ALRule._preview_item_name(item_code),
            }
        return {"value": rule_engine.row_field(row, field)}

    @staticmethod
    def _preview_item_names(rows, field):
        """Tên vật tư cho MỌI dòng ITEM — mỗi mã tra 1 lần (⛔ N+1 theo dòng)."""
        if field != "result_item":
            return {}
        names = {}
        for row in rows or []:
            code = rule_engine.row_field(row, "result_item") or ""
            if code and code not in names:
                names[code] = ALRule._preview_item_name(code)
        return names

    @staticmethod
    def _preview_item_name(item_code):
        """Tên vật tư; lỗi tra cứu ⇒ chuỗi rỗng (⛔ throw khi chỉ để hiển thị)."""
        if not item_code:
            return ""
        try:
            return frappe.db.get_value("Item", item_code, "item_name") or ""
        except Exception:
            return ""

    @staticmethod
    def _preview_result_text(row, field, item_names):
        """Chuỗi kết quả 1 dòng để client vẽ bảng (⛔ phơi mã trần khi có tên)."""
        if field == "result_item":
            code = rule_engine.row_field(row, "result_item") or ""
            if not code:
                return ""
            name = (item_names or {}).get(code) or ""
            return ('%s (%s)' % (name, code)) if name else str(code)
        value = rule_engine.row_field(row, field)
        if value is None or value == "":
            return ""
        return _format_number_vi(value)


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
            "mã — không tra được mã vật tư. Chọn một quy tắc chọn mã (Loại "
            "kết quả là \"%s\")."
            % (rule_label, rule_engine.RESULT_TYPE_LABELS["ITEM"]))
    result = doc.resolve(input_value)
    if result:
        return {
            "item_code": result,
            "item_name": frappe.db.get_value("Item", result, "item_name"),
        }
    return None
