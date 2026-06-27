"""
MRP Lite Aggregator — Tổng hợp vật tư từ pool Quotation/SO
"""
import frappe
import json
from frappe.utils import flt
from collections import defaultdict


class MRPAggregator:
    """Tổng hợp vật tư từ ConfigSnapshot của các Quotation/SO đã chọn."""

    def aggregate(self, plan_doc):
        """Tổng hợp vật tư → dict {item_code: {...}}.

        Returns:
            dict: {item_code: {qty_gross, safety, qty_net, current_stock, to_purchase, ...}}
        """
        item_acc = defaultdict(lambda: {
            "qty_gross": 0,
            "type": "",
            "uom": "",
            "sources": [],
            "estimated_unit_price": 0,
        })

        # Đọc từng source
        sources = []
        qt_list = self._safe_json(plan_doc.quotation_list)
        so_list = self._safe_json(plan_doc.so_list)

        # Hỗ trợ cả string list và dict list
        if isinstance(qt_list, list):
            sources.extend(qt_list)
        if isinstance(so_list, list):
            sources.extend(so_list)

        if not sources:
            frappe.msgprint("Không có Quotation/SO nào được chọn.")
            return {}

        for src_name in sources:
            src = str(src_name) if not isinstance(src_name, dict) else src_name.get("name", "")
            items = self._get_bom_items_from_source(src)
            for item in items:
                key = item["item_code"]
                item_acc[key]["qty_gross"] += flt(item.get("qty", 0))
                item_acc[key]["type"] = item.get("type", "")
                item_acc[key]["uom"] = item.get("uom", "")
                item_acc[key]["sources"].append(src)
                if item.get("unit_price"):
                    item_acc[key]["estimated_unit_price"] = flt(item["unit_price"])

        # Apply safety stock
        safety_pct = flt(plan_doc.include_safety_stock_pct or 0) / 100.0
        for key, data in item_acc.items():
            gross = data["qty_gross"]
            safety = gross * safety_pct
            net = gross + safety
            current_stock = flt(
                frappe.db.get_value("Bin", {"item_code": key}, "actual_qty") or 0
            )
            to_purchase = max(0, net - current_stock)
            data.update({
                "qty_gross": gross,
                "safety": safety,
                "qty_net": net,
                "current_stock": current_stock,
                "to_purchase": to_purchase,
            })

        return dict(item_acc)

    def populate_plan_lines(self, plan_doc):
        """Tổng hợp + populate al_plan_lines child table."""
        aggregated = self.aggregate(plan_doc)

        # Xóa lines cũ
        plan_doc.set("al_plan_lines", [])

        total_nhom = 0
        total_kinh = 0
        total_vtp = 0
        total_pk = 0

        for item_code, data in sorted(aggregated.items()):
            item_name = frappe.db.get_value("Item", item_code, "item_name")
            plan_doc.append("al_plan_lines", {
                "item_code": item_code,
                "item_name": item_name,
                "item_type": data["type"],
                "uom": data["uom"],
                "total_qty_gross": data["qty_gross"],
                "safety_stock_qty": data["safety"],
                "total_qty_net": data["qty_net"],
                "current_stock_qty": data["current_stock"],
                "qty_to_purchase": data["to_purchase"],
                "estimated_unit_price": data["estimated_unit_price"],
                "estimated_total": data["qty_net"] * data["estimated_unit_price"],
                "source_quotations": json.dumps(data["sources"], ensure_ascii=False),
            })

            estimated = data["qty_net"] * data["estimated_unit_price"]
            if data["type"] == "NHOM":
                total_nhom += estimated
            elif data["type"] == "KINH":
                total_kinh += estimated
            elif data["type"] == "VTP":
                total_vtp += estimated
            elif data["type"] == "PK":
                total_pk += estimated

        plan_doc.total_nhom_value = total_nhom
        plan_doc.total_kinh_value = total_kinh
        plan_doc.total_vtp_value = total_vtp
        plan_doc.total_pk_value = total_pk
        plan_doc.grand_total_value = total_nhom + total_kinh + total_vtp + total_pk

        return plan_doc

    def generate_purchase_orders(self, plan_doc):
        """Tạo ERPNext Purchase Order từ Material Plan đã Confirmed."""
        if plan_doc.status != "Confirmed":
            frappe.throw("Chỉ Material Plan ở trạng thái Confirmed mới tạo được Purchase Order.")

        from collections import defaultdict
        supplier_items = defaultdict(list)

        for line in plan_doc.al_plan_lines:
            if flt(line.qty_to_purchase) <= 0:
                continue

            # Tìm supplier
            supplier = frappe.db.get_value(
                "Item Default",
                {"parent": line.item_code, "company": frappe.defaults.get_user_default("Company")},
                "default_supplier",
            )
            if not supplier:
                supplier_row = frappe.db.get_value(
                    "Item Supplier",
                    {"parent": line.item_code},
                    "supplier",
                )
                supplier = supplier_row or None

            if supplier:
                supplier_items[supplier].append({
                    "item_code": line.item_code,
                    "qty": line.qty_to_purchase,
                    "uom": line.uom,
                    "rate": line.estimated_unit_price or 0,
                })

        pos = []
        for supplier, items in supplier_items.items():
            po = frappe.new_doc("Purchase Order")
            po.supplier = supplier
            po.schedule_date = frappe.utils.add_days(frappe.utils.today(), 7)
            for item in items:
                po.append("items", item)
            po.insert(ignore_permissions=True)
            pos.append(po.name)

        if pos:
            plan_doc.db_set("status", "Purchased")

        return pos

    def _get_bom_items_from_source(self, source_name):
        """Đọc vật tư từ ConfigSnapshot của source (Quotation/SO)."""
        items = []

        qi_list = frappe.get_all(
            "Quotation Item",
            filters={"parent": source_name},
            fields=["al_config_snapshot", "al_W_mm", "al_H_mm", "qty", "item_name"],
        )

        for qi in qi_list:
            if not qi.al_config_snapshot:
                continue

            try:
                snap = frappe.get_doc("ConfigSnapshot", qi.al_config_snapshot)
                data = json.loads(snap.enterprise_snapshot_json)
                formulas = data.get("formulas", {})

                # Trích xuất các biến _qty và _tt để lấy item + số lượng
                for var_name, formula_str in formulas.items():
                    if var_name.endswith("_tt") and not var_name.startswith("kinh_"):
                        # Resolve item_code từ slug
                        slug = var_name.replace("_tt", "")
                        item_code = self._resolve_item_from_slug(slug, snap)

                        if item_code:
                            # Lấy qty từ biến _qty tương ứng
                            qty_var = f"{slug}_qty"
                            qty_val = data.get("results", {}).get(qty_var, 0)

                            # Lấy item type
                            item_type = frappe.db.get_value("Item", item_code, "al_item_type")
                            uom = frappe.db.get_value("Item", item_code, "stock_uom")

                            items.append({
                                "item_code": item_code,
                                "item_name": qi.item_name,
                                "qty": flt(qty_val) * flt(qi.qty),
                                "type": item_type or "UNKNOWN",
                                "uom": uom or "Nos",
                                "unit_price": 0,  # Sẽ được populate từ Item Price sau
                            })
            except Exception as e:
                frappe.log_error(
                    f"MRP: Error reading ConfigSnapshot {qi.al_config_snapshot}: {e}"
                )

        return items

    def _resolve_item_from_slug(self, slug, snapshot):
        """Resolve item_code từ slug trong ConfigSnapshot."""
        # Đọc profile_set từ snapshot
        data = json.loads(snapshot.enterprise_snapshot_json)
        ps_name = data.get("profile_set")
        if not ps_name:
            return None

        # Tìm trong AL Profile Line
        item_code = frappe.db.get_value(
            "AL Profile Line",
            {"parent": ps_name, "slug": slug},
            "item_code",
        )
        return item_code

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
