import frappe
from frappe.model.document import Document


class ConfigSnapshot(Document):
    """ConfigSnapshot — lưu snapshot cấu hình + kết quả khi SUBMIT Quotation.

    V6 P5 (D): autoname=None trước đây → name random (vd pr3q6h0u2i).
    Nay đặt name có ý nghĩa: SNP-{item_code}-{YYMMDDHHMMSS}-{###}.
    - item_code lấy từ Quotation Item (quotation_item_name). Không có → fallback
      quotation_item_name; không có luôn → "SNP".
    - Hậu tố {###} đếm từ 1 đảm bảo UNIQUE trong cùng giây + tránh trùng name.
    - Backward compatible: snapshot cũ (name random) vẫn dùng bình thường
      (al_config_snapshot link giữ nguyên), không đụng data cũ.
    """

    def autoname(self):
        """Sinh name có ý nghĩa khi INSERT (không cần migrate).

        Frappe gọi `doc.run_method('autoname')` khi name rỗng và không có
        `autoname` format trong meta (naming.set_new_name). Đây là nơi duy nhất
        chặn được việc Frappe tự sinh hash ngẫu nhiên.
        """
        item_code = ""
        qi_name = self.get("quotation_item_name") or ""
        if qi_name:
            item_code = frappe.db.get_value(
                "Quotation Item", qi_name, "item_code") or ""
        code = (item_code or qi_name or "SNP").replace("/", "-").replace(" ", "-")[:30]
        ts = frappe.utils.now_datetime().strftime("%y%m%d%H%M%S")
        seq = 0
        while True:
            seq += 1
            candidate = f"SNP-{code}-{ts}-{seq:03d}"
            if not frappe.db.exists("ConfigSnapshot", candidate):
                self.name = candidate
                return
