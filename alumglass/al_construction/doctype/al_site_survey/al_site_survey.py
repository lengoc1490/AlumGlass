import frappe
from frappe.model.document import Document


class ALSiteSurvey(Document):
    """Khảo sát công trình - đối chiếu kích thước thực tế vs thiết kế."""

    def validate(self):
        self._calculate_deviations()

    def _calculate_deviations(self):
        """Tự động tính sai lệch và kiểm tra dung sai.
        Dung sai đọc từ AL Cutting Standard (config, không hardcode)."""
        if not self.items:
            return

        # Đọc tolerance từ DB config (AL Cutting Standard)
        tolerance = frappe.db.get_value("AL Cutting Standard",
            {"applies_to": "NHOM_PROFILE"}, "survey_tolerance_mm") or 10.0

        for item in self.items:
            if item.design_width_mm and item.actual_width_mm:
                item.width_deviation_mm = item.actual_width_mm - item.design_width_mm
            else:
                item.width_deviation_mm = 0

            if item.design_height_mm and item.actual_height_mm:
                item.height_deviation_mm = item.actual_height_mm - item.design_height_mm
            else:
                item.height_deviation_mm = 0

            item.within_tolerance = (
                abs(item.width_deviation_mm) <= tolerance
                and abs(item.height_deviation_mm) <= tolerance
            )

            if not item.within_tolerance and not item.action_required:
                item.action_required = "CHANGE_ORDER"
