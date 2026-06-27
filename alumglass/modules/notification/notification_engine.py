"""
Notification Engine — Kiểm tra & phát cảnh báo (Hook D)
"""
import frappe
import json
from frappe.utils import flt


class NotificationEngine:
    """Kiểm tra alerts sau calculate() và phát notification."""

    @staticmethod
    def check_alerts(result, quotation_item, bom_doc, **kwargs):
        """Hook D — Kiểm tra tất cả alert configs active."""
        try:
            alerts = frappe.get_all(
                "AL Alert Config",
                filters={"is_active": 1},
                fields=["*"],
            )

            for alert in alerts:
                if alert.alert_type == "PRICE_CHANGE":
                    NotificationEngine._check_price_change(alert, bom_doc)
                elif alert.alert_type == "LOW_STOCK":
                    NotificationEngine._check_low_stock(alert)
                elif alert.alert_type == "VARIANCE_ALERT":
                    NotificationEngine._check_variance_alert(alert)
                elif alert.alert_type == "APPROVAL_PENDING":
                    NotificationEngine._check_approval_pending(alert)
        except Exception as e:
            frappe.log_error(
                title="NotificationEngine.check_alerts failed",
                message=str(e),
            )

    @staticmethod
    def _check_price_change(alert, bom_doc):
        """So sánh Item Price hiện tại vs ConfigSnapshot gần nhất."""
        recent_snaps = frappe.get_all(
            "ConfigSnapshot",
            filters={"profile_set": bom_doc.profile_set},
            fields=["name"],
            order_by="created_at desc",
            limit=1,
        )
        if not recent_snaps:
            return

        try:
            snap = frappe.get_doc("ConfigSnapshot", recent_snaps[0].name)
            data = json.loads(snap.enterprise_snapshot_json)
            old_results = data.get("results", {})
        except Exception:
            return

        # Kiểm tra KINH items trong profile set
        kinh_lines = frappe.get_all(
            "AL Profile Line",
            filters={"parent": bom_doc.profile_set, "line_type": "KINH"},
            fields=["default_glass_master"],
        )

        for kinh in kinh_lines:
            glass_code = kinh.default_glass_master
            if not glass_code:
                continue

            # Tìm item code từ glass master
            item_code = frappe.db.get_value(
                "Item", {"al_glass_master": glass_code}, "name"
            )
            if not item_code:
                continue

            current_price = flt(
                frappe.db.get_value(
                    "Item Price",
                    {"item_code": item_code, "selling": 1},
                    "price_list_rate",
                    order_by="valid_from desc",
                ) or 0
            )

            # Tìm giá cũ trong snapshot
            old_price = 0
            item_key = item_code.lower().replace("-", "_")
            for var_name, value in old_results.items():
                if var_name.endswith("_dg") and item_key in var_name.lower():
                    old_price = flt(value)
                    break

            if old_price > 0 and current_price > 0:
                change_pct = abs(current_price - old_price) / old_price * 100
                if change_pct > flt(alert.threshold_value):
                    NotificationEngine._send(alert, {
                        "item": item_code,
                        "old_price": old_price,
                        "new_price": current_price,
                        "change_pct": round(change_pct, 1),
                        "alert_type": "PRICE_CHANGE",
                    })

    @staticmethod
    def _check_low_stock(alert):
        """Kiểm tra Bin.actual_qty cho item nhôm/kính."""
        items = frappe.get_all(
            "Item",
            filters={"al_item_type": ["in", ["NHOM_PROFILE", "KINH"]]},
            fields=["name", "item_name"],
        )
        for item in items:
            qty = flt(
                frappe.db.get_value("Bin", {"item_code": item.name}, "actual_qty") or 0
            )
            if qty < flt(alert.threshold_value):
                NotificationEngine._send(alert, {
                    "item": item.name,
                    "item_name": item.item_name,
                    "qty": qty,
                    "threshold": alert.threshold_value,
                    "alert_type": "LOW_STOCK",
                })

    @staticmethod
    def _check_variance_alert(alert):
        """Kiểm tra AL Cost Variance chưa review có status=ALERT."""
        unreviewed = frappe.get_all(
            "AL Cost Variance",
            filters={
                "variance_status": "ALERT",
                "reviewed_by": ["in", ["", None]],
            },
            fields=["name", "item_code", "variance_pct", "impact_on_margin"],
            order_by="creation desc",
            limit=10,
        )
        for v in unreviewed:
            if flt(v.variance_pct) > flt(alert.threshold_value):
                NotificationEngine._send(alert, {
                    "variance_name": v.name,
                    "item": v.item_code,
                    "variance_pct": v.variance_pct,
                    "impact": v.impact_on_margin,
                    "alert_type": "VARIANCE_ALERT",
                })

    @staticmethod
    def _check_approval_pending(alert):
        """Kiểm tra approval pending quá timeout."""
        from frappe.utils import now_datetime, add_to_date
        threshold_hours = flt(alert.threshold_value or 24)
        cutoff = add_to_date(now_datetime(), hours=-threshold_hours)

        pending = frappe.get_all(
            "Quotation Item",
            filters={
                "al_approval_status": "PENDING",
                "creation": ["<", cutoff],
            },
            fields=["name", "parent", "owner", "creation"],
            order_by="creation asc",
        )

        for p in pending:
            hours_waiting = round(
                (now_datetime() - p.creation).total_seconds() / 3600, 1
            )
            NotificationEngine._send(alert, {
                "quotation_item": p.name,
                "quotation": p.parent,
                "sales_user": p.owner,
                "hours_waiting": hours_waiting,
                "alert_type": "APPROVAL_PENDING",
            })

    @staticmethod
    def _send(alert, context):
        """Gửi notification qua channel đã cấu hình."""
        roles = NotificationEngine._safe_json(alert.notify_roles)
        users = NotificationEngine._safe_json(alert.notify_users)

        # Expand roles → users
        for role in (roles if isinstance(roles, list) else []):
            role_users = frappe.get_all(
                "Has Role",
                filters={"role": role, "parenttype": "User"},
                fields=["parent"],
            )
            users.extend([u.parent for u in role_users])

        users = list(set(u for u in users if u))

        if not users:
            return

        channel = alert.notification_channel or "FRAPPE_NOTIFICATION"
        message = json.dumps(context, ensure_ascii=False)

        for user in users:
            if channel in ("FRAPPE_NOTIFICATION", "BOTH"):
                frappe.publish_realtime(
                    "aluglass_alert",
                    {"alert_type": alert.alert_type, "context": context},
                    user=user,
                )

            if channel in ("EMAIL", "BOTH"):
                try:
                    frappe.sendmail(
                        recipients=[user],
                        subject=f"AluGlass Alert: {alert.alert_name or alert.alert_type}",
                        message=f"""
                        <h3>AluGlass Alert</h3>
                        <p><strong>Type:</strong> {alert.alert_type}</p>
                        <p><strong>Details:</strong></p>
                        <pre>{message}</pre>
                        """,
                    )
                except Exception as e:
                    frappe.log_error(f"Email alert failed: {e}")

    @staticmethod
    def _safe_json(val):
        """Parse JSON safely."""
        if isinstance(val, (list, dict)):
            return val
        if isinstance(val, str) and val.strip():
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
