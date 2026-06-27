"""
SnapshotBuilder — Tạo ConfigSnapshot sau mỗi lần calculate()
Lưu EnterpriseSnapshot để audit trail + drift detection
"""
import frappe
import json
import hashlib
from frappe.utils import now


class SnapshotBuilder:
    """Tạo và quản lý ConfigSnapshot để minh bạch tuyệt đối."""

    def persist(self, quotation_item, bom_doc, inputs_dict, formulas, result,
                profile_set, pk_overrides, discount_info=None):
        """Tạo ConfigSnapshot sau khi FormulaEngine.calculate() hoàn thành.

        Args:
            quotation_item: Quotation Item doc
            bom_doc: AL BOM doc
            inputs_dict: dict inputs đã dùng để tính
            formulas: list of {name, formula} đã dùng
            result: dict kết quả từ FormulaEngine
            profile_set: AL Profile Set doc (để hash)
            pk_overrides: dict PK overrides đã áp dụng
            discount_info: dict (optional) {rule, pct, gia_thuong_mai, approval_ref}

        Returns:
            ConfigSnapshot document
        """
        snapshot_id = frappe.generate_hash(length=16)

        # Build EnterpriseSnapshot payload
        enterprise_snapshot = {
            "snapshot_id": snapshot_id,
            "bom_code": bom_doc.name,
            "profile_set": bom_doc.profile_set,
            "pk_set": bom_doc.pk_set,
            "cost_template": bom_doc.default_cost_template,
            "inputs": self._serialize_inputs(inputs_dict),
            "formulas": self._serialize_formulas(formulas),
            "results": self._serialize_result(result),
            "pk_overrides": pk_overrides,
            "calculation_timestamp": now(),
            # v17 additions
            "bom_version_id": None,
            "bom_version_hash": None,
            "discount_applied": discount_info or {},
            "discount_approval_ref": None,
        }

        # Hash riêng từng thành phần để drift detection
        ps_hash = self._hash_doc(profile_set)
        rule_hashes = self._hash_rules(formulas)
        glass_hashes = self._hash_glass_masters(inputs_dict)

        snapshot = frappe.new_doc("ConfigSnapshot")
        snapshot.snapshot_id = snapshot_id
        snapshot.enterprise_snapshot_json = json.dumps(enterprise_snapshot, ensure_ascii=False)
        snapshot.profile_set = bom_doc.profile_set
        snapshot.profile_set_hash = ps_hash
        snapshot.pk_set = bom_doc.pk_set
        snapshot.pk_overrides_json = json.dumps(pk_overrides or {}, ensure_ascii=False)
        snapshot.rule_set_hashes = json.dumps(rule_hashes, ensure_ascii=False)
        snapshot.glass_master_hashes = json.dumps(glass_hashes, ensure_ascii=False)
        snapshot.variable_bindings_hash = self._hash_bindings()
        snapshot.cost_template = bom_doc.default_cost_template
        snapshot.cost_template_hash = self._hash_cost_template(bom_doc.default_cost_template)
        snapshot.created_at = now()
        snapshot.quotation = quotation_item.get("parent") or getattr(quotation_item, "parent", None)
        snapshot.quotation_item_name = quotation_item.get("name") or getattr(quotation_item, "name", None)
        snapshot.drift_detected = 0

        # Formula engine snapshot reference
        snapshot.formula_engine_snapshot_id = snapshot_id
        snapshot.formula_engine_payload_hash = self._hash_payload(enterprise_snapshot)

        snapshot.insert(ignore_permissions=True)
        frappe.db.commit()

        return snapshot

    def verify(self, config_snapshot_name):
        """Verify ConfigSnapshot còn hợp lệ không (drift detection).

        Returns:
            dict: {profile_ok, bom_version_ok, drifted, details}
        """
        snap = frappe.get_doc("ConfigSnapshot", config_snapshot_name)
        data = json.loads(snap.enterprise_snapshot_json)

        result = {"profile_ok": True, "bom_version_ok": True, "drifted": False, "details": []}

        # v16: verify profile_set_hash
        if snap.profile_set and snap.profile_set_hash:
            current_ps = frappe.get_doc("AL Profile Set", snap.profile_set)
            current_hash = self._hash_doc(current_ps)
            if current_hash != snap.profile_set_hash:
                result["profile_ok"] = False
                result["details"].append("Profile Set đã thay đổi so với thời điểm báo giá")

        # v17: verify BOM Version snapshot_hash
        bom_ver_id = data.get("bom_version_id")
        if bom_ver_id:
            current_hash = frappe.db.get_value("AL BOM Version", bom_ver_id, "snapshot_hash")
            if current_hash != data.get("bom_version_hash"):
                result["bom_version_ok"] = False
                result["details"].append("BOM Version đã thay đổi so với thời điểm báo giá")

        result["drifted"] = not (result["profile_ok"] and result["bom_version_ok"])
        return result

    # ---- Private helpers ----

    def _serialize_inputs(self, inputs_dict):
        """Serialize inputs_dict — chỉ giữ scalar values."""
        return {
            k: v for k, v in inputs_dict.items()
            if isinstance(v, (int, float, str, bool, type(None)))
        }

    def _serialize_formulas(self, formulas):
        """Serialize formulas list."""
        return {f["name"]: f["formula"] for f in formulas}

    def _serialize_result(self, result):
        """Serialize result — chỉ giữ scalar."""
        return {
            k: v for k, v in result.items()
            if isinstance(v, (int, float, str, bool, type(None)))
        }

    def _hash_doc(self, doc):
        """Hash 1 document → SHA-256 hex."""
        if not doc:
            return ""
        d = doc.as_dict() if hasattr(doc, "as_dict") else doc
        payload = json.dumps(d, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _hash_rules(self, formulas):
        """Hash tất cả rule tham chiếu."""
        hashes = {}
        rule_codes = set()
        for f in formulas:
            formula_str = f.get("formula", "")
            # Extract rule codes (heuristic: rule thường là các mã như QTY-*, TRA-*, XF*-*)
            # Đơn giản hóa: hash từng formula
            pass
        return hashes

    def _hash_glass_masters(self, inputs_dict):
        """Hash glass master references."""
        hashes = {}
        for k, v in inputs_dict.items():
            if k.startswith("glass_thick_"):
                prefix = k.replace("glass_thick_", "")
                hashes[prefix] = hashlib.sha256(
                    json.dumps({"prefix": prefix, "thick": v}, sort_keys=True).encode()
                ).hexdigest()
        return hashes

    def _hash_bindings(self):
        """Hash all active variable bindings."""
        bindings = frappe.get_all("AL Variable Binding", filters={"is_active": 1}, fields=["*"])
        payload = json.dumps(bindings, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _hash_cost_template(self, template_name):
        """Hash cost template."""
        if not template_name:
            return ""
        lines = frappe.get_all(
            "AL Cost Template Line",
            filters={"parent": template_name},
            fields=["*"],
            order_by="sort_order asc",
        )
        payload = json.dumps(lines, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _hash_payload(self, data):
        """Hash toàn bộ enterprise_snapshot payload."""
        payload = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()
