import frappe
from frappe.model.document import Document
from frappe.utils import today


class ALSupplierPriceList(Document):
    """Bảng giá nhà cung cấp."""

    def validate(self):
        if self.expiry_date and self.effective_date:
            if self.expiry_date < self.effective_date:
                frappe.throw("Ngày hết hạn không thể trước ngày hiệu lực")

    def before_save(self):
        if self.expiry_date and str(self.expiry_date) < str(today()):
            self.status = "Expired"
        elif not self.status or self.status == "Expired":
            self.status = "Active"
        self._backfill_previous_price_and_change_pct()

    def _backfill_previous_price_and_change_pct(self):
        """Với mỗi dòng item, tìm bảng giá GẦN NHẤT TRƯỚC ĐÓ của CÙNG nhà
        cung cấp (+ cùng currency_type, nếu có) để điền `previous_unit_price`
        và `base_price_change_pct` (% thay đổi đơn giá — cùng loại tiền tệ,
        không lẫn ảnh hưởng tỷ giá).

        LƯU Ý — `fx_change_pct` KHÔNG được tính ở đây: tách bạch phần thay
        đổi do tỷ giá khỏi phần do nhà cung cấp tăng giá gốc đòi hỏi biết rõ
        quy ước quy đổi công ty dùng (vd nếu 2 bảng giá khác currency_type,
        hay so exchange_rate_snapshot theo hướng nào) — chưa có đủ thông tin
        xác nhận để suy đoán đúng công thức cho 1 field ảnh hưởng số liệu
        mua hàng. Cần xác nhận nghiệp vụ thật trước khi bổ sung logic này
        (xem README/audit đi kèm).
        """
        if not self.items or not self.supplier:
            return

        prev_list_name = frappe.db.get_value(
            "AL Supplier Price List",
            {
                "supplier": self.supplier,
                "currency_type": self.currency_type,
                "effective_date": ("<", self.effective_date),
                "name": ("!=", self.name or ""),
            },
            "name",
            order_by="effective_date desc",
        )
        if not prev_list_name:
            return

        prev_prices = {}
        for row in frappe.get_all(
            "AL Supplier Price List Item",
            filters={"parent": prev_list_name},
            fields=["item_code", "unit_price"],
        ):
            if row.get("item_code"):
                prev_prices.setdefault(row["item_code"], row.get("unit_price"))

        for item in self.items:
            prev_price = prev_prices.get(item.item_code)
            if not prev_price:
                continue
            item.previous_unit_price = prev_price
            if item.unit_price and prev_price:
                item.base_price_change_pct = round(
                    (item.unit_price - prev_price) / prev_price * 100, 4)
