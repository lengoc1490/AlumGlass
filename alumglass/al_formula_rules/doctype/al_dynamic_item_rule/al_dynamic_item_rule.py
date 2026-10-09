import frappe
from frappe.model.document import Document


class ALDynamicItemRule(Document):
    """Rule chọn Item động theo THRESHOLD hoặc LOOKUP.

    VD: chọn nẹp kính theo độ dày kính, chọn keo theo loại kính.
    """

    def validate(self):
        if self.rule_type == "THRESHOLD":
            if not self.threshold_rows:
                frappe.throw("THRESHOLD rule cần ít nhất 1 dòng")
            self._validate_threshold_rows()
        if self.rule_type == "LOOKUP":
            if not self.lookup_rows:
                frappe.throw("LOOKUP rule cần ít nhất 1 dòng")

    def _validate_threshold_rows(self):
        rows = self._sorted_threshold_rows()
        for i, row in enumerate(rows):
            if not row.result_item:
                frappe.throw(f"Threshold row {i+1}: cần Result Item")
            if row.from_value > row.to_value:
                frappe.throw(f"Threshold row {i+1}: from > to")
        for i in range(len(rows) - 1):
            # F9: quy ước biên NỬA MỞ [from, to) — DÙNG CHUNG với AL Calculation
            # Rule (al_calculation_rule._validate_no_overlap). Trước đây doctype
            # này dùng '>=' (CẤM chạm biên) còn AL Calculation Rule dùng '>'
            # (CHO PHÉP) ⇒ 2 doctype cùng khái niệm mà biên khác nhau. Nay chạm
            # biên (to == next.from) là HỢP LỆ và luôn xác định: dải TRÊN thắng,
            # xem _resolve_threshold().
            if rows[i].to_value > rows[i + 1].from_value:
                frappe.throw(
                    f"Threshold chồng lấp: [{rows[i].from_value}-{rows[i].to_value}] "
                    f"và [{rows[i+1].from_value}-{rows[i+1].to_value}]"
                )
        self._warn_threshold_gaps(rows)

    def _sorted_threshold_rows(self):
        """Dòng threshold xếp theo `from_value` — KHÔNG theo thứ tự lưu."""
        return sorted(self.threshold_rows, key=lambda r: r.from_value)

    def _warn_threshold_gaps(self, rows):
        """Cảnh báo KHE HỞ giữa 2 dải liền nhau (F9) — cùng quy ước với AL
        Calculation Rule. Quy ước [from, to) khiến 2 dải liền nhau phải khai
        `to` = `from` dải sau (vd [0,24] + [24,30]); khe 0.1 kiểu cũ (vd [0,24]
        + [24.1,30]) để lại vùng 24 → 24.1 không dải nào phủ ⇒ giá trị rơi vào
        đó (24.05) không khớp dòng nào. Cảnh báo, KHÔNG throw.
        """
        gaps = [
            f"[{rows[i].to_value} – {rows[i+1].from_value}]"
            for i in range(len(rows) - 1)
            if rows[i].to_value < rows[i + 1].from_value
        ]
        if gaps:
            frappe.msgprint(
                "Threshold có KHE HỞ — giá trị nằm trong khe sẽ không khớp dòng "
                "nào (trả rỗng): " + ", ".join(gaps) + ". Nên khai liền: dải sau "
                "bắt đầu đúng bằng `to` của dải trước.",
                title="AL Dynamic Item Rule — Cảnh báo khe hở",
                indicator="orange",
            )

    def resolve(self, input_value):
        """Tra cứu Item code từ input value."""
        if input_value is None or input_value == "":
            return None
        if self.rule_type == "THRESHOLD":
            return self._resolve_threshold(input_value)
        if self.rule_type == "LOOKUP":
            for row in self.lookup_rows:
                if str(row.key_field) == str(input_value):
                    return row.result_item
        return None

    def _resolve_threshold(self, input_value):
        """Tra 1 dòng THRESHOLD theo quy ước biên NỬA MỞ [from, to).

        Duyệt theo `from_value` TĂNG DẦN (trước đây theo thứ tự lưu ⇒ đổi thứ
        tự dòng là đổi kết quả khi 2 dải chạm biên).

        Lưới tương thích dữ liệu CŨ: rule đang khai theo lối ĐÓNG hai đầu có
        khe 0.1 — giá trị đúng bằng biên trên một dải sẽ trượt hết nếu chỉ dùng
        nửa mở. Nên nếu nửa mở không khớp dòng nào, thử lại đúng tại biên trên
        ĐÓNG. Đây là chịu-lỗi cho dữ liệu cũ, KHÔNG phải quy ước thứ hai: chỗ 2
        dải chạm biên vẫn xử theo nửa mở (dải trên thắng).
        """
        try:
            val = float(input_value)
        except (ValueError, TypeError):
            return None
        rows = self._sorted_threshold_rows()
        for row in rows:
            if row.from_value <= val < row.to_value:
                return row.result_item
        for row in rows:
            if val == row.to_value:
                return row.result_item
        return None


@frappe.whitelist()
def resolve_item(rule_code, input_value):
    """API: Tra cứu Item từ rule. Trả về {item_code, item_name}."""
    doc = frappe.get_cached_doc("AL Dynamic Item Rule", rule_code)
    result = doc.resolve(input_value)
    if result:
        return {
            "item_code": result,
            "item_name": frappe.db.get_value("Item", result, "item_name"),
        }
    return None
