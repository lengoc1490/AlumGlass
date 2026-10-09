import frappe
from frappe.model.document import Document


class ALCalculationRule(Document):
    """Rule CONSTANT / THRESHOLD / LOOKUP — dùng cho offset, phụ thu giá màu."""

    def validate(self):
        if self.rule_type == "CONSTANT" and self.constant_value is None:
            frappe.throw("CONSTANT rule cần constant_value")
        if self.rule_type == "THRESHOLD":
            if not self.threshold_rows:
                frappe.throw("THRESHOLD rule cần ít nhất 1 dòng")
            self._validate_no_overlap()
        if self.rule_type == "LOOKUP" and not self.lookup_rows:
            frappe.throw("LOOKUP rule cần ít nhất 1 dòng")

    def _validate_no_overlap(self):
        rows = self._sorted_threshold_rows()
        for i in range(len(rows) - 1):
            # F9: quy ước biên NỬA MỞ [from, to) — DÙNG CHUNG với AL Dynamic
            # Item Rule (al_dynamic_item_rule._validate_threshold_rows). Chạm
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
        """Cảnh báo KHE HỞ giữa 2 dải liền nhau (F9).

        Quy ước [from, to) khiến 2 dải liền nhau phải khai `to` = `from` dải
        sau (vd [0,24] + [24,30]). Kiểu khai cũ có khe 0.1 (vd [0,24] +
        [24.1,30]) để lại vùng 24 → 24.1 KHÔNG dải nào phủ ⇒ giá trị rơi vào đó
        (vd 24.05) không khớp dòng nào và trả None âm thầm. Cảnh báo (KHÔNG
        throw — dữ liệu cũ đang chạy được) để người khai rule thấy ngay lúc save.
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
                title="AL Calculation Rule — Cảnh báo khe hở",
                indicator="orange",
            )

    def resolve(self, input_value):
        """Tra cứu giá trị từ rule. Dùng bởi BomOrchestrator."""
        if self.rule_type == "CONSTANT":
            return self.constant_value
        if self.rule_type == "THRESHOLD":
            return self._resolve_threshold(input_value)
        if self.rule_type == "LOOKUP":
            for row in self.lookup_rows:
                if str(row.key_field) == str(input_value):
                    return row.result_value
            return None

    def _resolve_threshold(self, input_value):
        """Tra 1 dòng THRESHOLD theo quy ước biên NỬA MỞ [from, to).

        Duyệt theo `from_value` TĂNG DẦN (trước đây theo thứ tự lưu ⇒ đổi thứ
        tự dòng là đổi kết quả khi 2 dải chạm biên).

        Lưới tương thích dữ liệu CŨ: rule hiện khai theo lối ĐÓNG hai đầu có
        khe 0.1 (vd seed RULE-HEIGHT-MULT [(0,10),(10.1,30)…]) — giá trị đúng
        bằng biên trên một dải (10, 2100, 2700…) sẽ trượt hết nếu chỉ dùng nửa
        mở, làm NV_LD về 0 ⇒ SAI GIÁ âm thầm. Nên nếu nửa mở không khớp dòng
        nào, thử lại đúng tại biên trên ĐÓNG. Đây là chịu-lỗi cho dữ liệu cũ,
        KHÔNG phải quy ước thứ hai: chỗ 2 dải chạm biên vẫn xử theo nửa mở.
        """
        try:
            val = float(input_value)
        except (ValueError, TypeError):
            return None
        rows = self._sorted_threshold_rows()
        for row in rows:
            if row.from_value <= val < row.to_value:
                return row.result_value
        for row in rows:
            if val == row.to_value:
                return row.result_value
        return None
