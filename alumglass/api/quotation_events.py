# alumglass/alumglass/api/quotation_events.py
"""Doc events cho Quotation.

V5 (Owner yêu cầu): ConfigSnapshot chỉ tạo khi SUBMIT Quotation — KHÔNG tạo
mỗi lần bấm tính toán. BomOrchestrator.b7_save_results giờ chỉ ghi
al_gia_vat / al_gia_ban / al_bom_result; snapshot chuyển sang đây.

hooks.py khai báo:
    doc_events = {
        "Quotation": {
            "on_submit": "alumglass.api.quotation_events.on_submit",
        },
    }
"""

import json

import frappe


def on_submit(doc, method=None):
    """Tạo ConfigSnapshot cho từng Quotation Item đã có kết quả BOM khi submit.

    - Chỉ item có `al_bom_result` (đã tính BOM) mới tạo snapshot.
    - Item chưa tính → bỏ qua.
    - Chạy trong transaction submit (doc_events on_submit) — KHÔNG gọi
      `frappe.db.commit()` riêng, để submit gốc commit toàn bộ (atomic):
      nếu có lỗi giữa chừng, cả submit + snapshot rollback về trạng thái cũ.
    """
    items = doc.get("items")
    if not items:
        return

    # Tạo snapshot trước (1 pass), rồi link `al_config_snapshot` sau — tránh
    # set_value giữa chừng khi vòng insert còn có thể throw (rollback sạch).
    pending = []  # [(snapshot_name, quotation_item_name)]
    for item in items:
        result_json = item.get("al_bom_result")
        if not result_json:
            continue

        bom_version = item.get("al_bom_version")
        inputs_json = item.get("al_bom_vars") or "{}"

        if not isinstance(inputs_json, str):
            inputs_json = json.dumps(inputs_json, indent=2, default=str)
        if not isinstance(result_json, str):
            result_json = json.dumps(result_json, indent=2, default=str)

        snap = frappe.new_doc("ConfigSnapshot")
        snap.bom_version = bom_version
        snap.quotation_item_name = item.name
        snap.calculation_timestamp = frappe.utils.now()
        snap.inputs_json = inputs_json
        snap.result_json = result_json
        snap.insert(ignore_permissions=True)

        pending.append((snap.name, item.name))

    for snap_name, item_name in pending:
        frappe.db.set_value("Quotation Item", item_name, "al_config_snapshot", snap_name)
