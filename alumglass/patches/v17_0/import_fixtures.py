"""Migration v17.0: Import fixtures (AL Alert Config defaults)"""
import frappe

ALERTS = [
    {"doctype": "AL Alert Config", "alert_type": "PRICE_CHANGE", "alert_name": "Cảnh báo thay đổi giá kính", "is_active": 1, "threshold_value": 5, "notify_roles": '["AluGlass Kỹ Thuật", "AluGlass Admin"]', "notification_channel": "FRAPPE_NOTIFICATION", "frequency": "REALTIME"},
    {"doctype": "AL Alert Config", "alert_type": "LOW_STOCK", "alert_name": "Cảnh báo tồn kho thấp", "is_active": 1, "threshold_value": 50, "notify_roles": '["AluGlass Admin"]', "notification_channel": "EMAIL", "frequency": "DAILY_DIGEST"},
    {"doctype": "AL Alert Config", "alert_type": "VARIANCE_ALERT", "alert_name": "Biến động giá bất thường", "is_active": 1, "threshold_value": 15, "notify_roles": '["AluGlass Admin", "AluGlass Kế Toán"]', "notification_channel": "BOTH", "frequency": "REALTIME"},
    {"doctype": "AL Alert Config", "alert_type": "APPROVAL_PENDING", "alert_name": "Duyệt discount quá hạn", "is_active": 1, "threshold_value": 24, "notify_roles": '["AluGlass Admin"]', "notification_channel": "FRAPPE_NOTIFICATION", "frequency": "DAILY_DIGEST"},
    {"doctype": "AL Alert Config", "alert_type": "DISCOUNT_EXCEEDED", "alert_name": "Chiết khấu vượt ngưỡng", "is_active": 1, "threshold_value": 8, "notify_roles": '["AluGlass Admin"]', "notification_channel": "BOTH", "frequency": "REALTIME"},
]

def execute():
    for alert_def in ALERTS:
        if not frappe.db.exists("AL Alert Config", {"alert_type": alert_def["alert_type"]}):
            doc = frappe.new_doc("AL Alert Config")
            doc.update(alert_def)
            doc.insert(ignore_permissions=True)
            print(f"  Created alert: {alert_def['alert_name']}")
    frappe.db.commit()
    print("Fixtures import complete")
