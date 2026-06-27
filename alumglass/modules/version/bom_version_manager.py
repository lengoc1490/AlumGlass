"""
BOM Version Manager — Snapshot, Publish, Diff, Rollback (Hook B)
"""
import frappe
import json
import hashlib
from frappe.utils import now


class BOMVersionManager:
    """Quản lý vòng đời BOM Version: Draft → Published → Deprecated."""

    def publish(self, bom_doc, change_summary="", reviewer=None):
        """Tạo AL BOM Version mới từ BOM hiện tại.

        Args:
            bom_doc: AL BOM document
            change_summary: Tóm tắt thay đổi
            reviewer: User duyệt (nếu cần)

        Returns:
            AL BOM Version document
        """
        # 1. Lấy toàn bộ snapshot
        ps = frappe.get_doc("AL Profile Set", bom_doc.profile_set)
        vs = frappe.get_doc("AL Variable Set", bom_doc.variable_set) if bom_doc.variable_set else None
        ct = frappe.get_doc("AL Cost Template", bom_doc.default_cost_template)
        pk = frappe.get_doc("AL PK Set", bom_doc.pk_set) if bom_doc.pk_set else None

        # 2. Serialize + hash
        payload = json.dumps({
            "profile_set": self._doc_to_dict(ps),
            "variable_set": self._doc_to_dict(vs) if vs else {},
            "cost_template": self._doc_to_dict(ct),
            "pk_set": self._doc_to_dict(pk) if pk else {},
        }, sort_keys=True, default=str, ensure_ascii=False)

        snap_hash = hashlib.sha256(payload.encode()).hexdigest()

        # 3. Tạo AL BOM Version
        version_number = frappe.db.count("AL BOM Version", {"bom": bom_doc.name}) + 1

        ver = frappe.new_doc("AL BOM Version")
        ver.bom = bom_doc.name
        ver.version_number = version_number
        ver.profile_set_snapshot = json.dumps(
            self._doc_to_dict(ps), default=str, ensure_ascii=False
        )
        ver.variable_set_snapshot = json.dumps(
            self._doc_to_dict(vs) if vs else {}, default=str, ensure_ascii=False
        )
        ver.cost_template_snapshot = json.dumps(
            self._doc_to_dict(ct), default=str, ensure_ascii=False
        )
        if pk:
            ver.pk_set_snapshot = json.dumps(
                self._doc_to_dict(pk), default=str, ensure_ascii=False
            )
        ver.snapshot_hash = snap_hash
        ver.change_summary = change_summary
        ver.published_by = frappe.session.user if frappe.session else None

        # Kiểm tra có cần approval không
        if bom_doc.requires_approval_for_new_version:
            ver.status = "Draft"
        else:
            ver.status = "Published"
            ver.published_on = now()

        ver.insert(ignore_permissions=True)

        # 4. Cập nhật BOM.current_version nếu Published
        if ver.status == "Published":
            frappe.db.set_value("AL BOM", bom_doc.name, "current_version", ver.name)
            frappe.db.set_value("AL BOM", bom_doc.name, "last_published_on", now())
            frappe.db.set_value(
                "AL BOM", bom_doc.name,
                "total_versions", version_number,
            )

        frappe.db.commit()
        return ver

    @staticmethod
    def link_version(result, quotation_item, bom_doc, **kwargs):
        """Hook B — Gắn al_bom_version vào Quotation Item."""
        try:
            qi_name = (
                quotation_item.get("name")
                or getattr(quotation_item, "name", None)
            )
            if not qi_name:
                return

            current_ver = bom_doc.current_version
            if current_ver:
                frappe.db.set_value(
                    "Quotation Item", qi_name,
                    "al_bom_version", current_ver,
                )
        except Exception as e:
            frappe.log_error(
                title="BOMVersionManager.link_version failed",
                message=str(e),
            )

    def compare_versions(self, ver_a_name, ver_b_name):
        """So sánh 2 version → DiffResult."""
        ver_a = frappe.get_doc("AL BOM Version", ver_a_name)
        ver_b = frappe.get_doc("AL BOM Version", ver_b_name)

        ps_a = json.loads(ver_a.profile_set_snapshot)
        ps_b = json.loads(ver_b.profile_set_snapshot)

        diff = {
            "added_lines": [],
            "removed_lines": [],
            "modified_lines": [],
            "formula_changes": [],
            "price_changes": [],
            "summary": "",
        }

        # So sánh al_lines
        lines_a = {
            l.get("slug"): l for l in (ps_a.get("al_lines") or [])
        }
        lines_b = {
            l.get("slug"): l for l in (ps_b.get("al_lines") or [])
        }

        slugs_a = set(lines_a.keys())
        slugs_b = set(lines_b.keys())

        # Added
        for slug in slugs_b - slugs_a:
            line = lines_b[slug]
            diff["added_lines"].append({
                "slug": slug,
                "line_type": line.get("line_type"),
                "line_name": line.get("line_name"),
            })

        # Removed
        for slug in slugs_a - slugs_b:
            line = lines_a[slug]
            diff["removed_lines"].append({
                "slug": slug,
                "line_type": line.get("line_type"),
                "line_name": line.get("line_name"),
            })

        # Modified
        for slug in slugs_a & slugs_b:
            la = lines_a[slug]
            lb = lines_b[slug]
            changes = []
            for field in ["qty_formula", "show_condition", "width_formula",
                          "height_formula", "panel_count_formula", "price_type"]:
                old_val = la.get(field)
                new_val = lb.get(field)
                if str(old_val) != str(new_val):
                    changes.append({"field": field, "old": old_val, "new": new_val})
            if changes:
                diff["modified_lines"].append({
                    "slug": slug,
                    "line_type": la.get("line_type"),
                    "line_name": la.get("line_name"),
                    "changes": changes,
                })

        # Summary
        parts = []
        if diff["added_lines"]:
            parts.append(f"Thêm {len(diff['added_lines'])} dòng")
        if diff["removed_lines"]:
            parts.append(f"Xóa {len(diff['removed_lines'])} dòng")
        if diff["modified_lines"]:
            parts.append(f"Sửa {len(diff['modified_lines'])} dòng")
        diff["summary"] = "; ".join(parts) if parts else "Không có thay đổi"

        return diff

    def rollback(self, target_version_name, requester=None):
        """Rollback về 1 version cũ — tạo version mới từ snapshot cũ."""
        target = frappe.get_doc("AL BOM Version", target_version_name)
        bom_doc = frappe.get_doc("AL BOM", target.bom)

        # 1. Restore Profile Set từ snapshot
        ps_snap = json.loads(target.profile_set_snapshot)
        self._restore_doc_from_snapshot("AL Profile Set", bom_doc.profile_set, ps_snap)

        # 2. Restore Variable Set nếu có
        if target.variable_set_snapshot and bom_doc.variable_set:
            vs_snap = json.loads(target.variable_set_snapshot)
            self._restore_doc_from_snapshot("AL Variable Set", bom_doc.variable_set, vs_snap)

        # 3. Restore Cost Template nếu có
        if target.cost_template_snapshot and bom_doc.default_cost_template:
            ct_snap = json.loads(target.cost_template_snapshot)
            self._restore_doc_from_snapshot("AL Cost Template", bom_doc.default_cost_template, ct_snap)

        # 4. Publish version mới với is_rollback_of
        new_ver = self.publish(
            bom_doc,
            change_summary=f"Rollback về version {target.version_number}",
        )
        new_ver.db_set("is_rollback_of", target.name)
        new_ver.db_set("status", "Published")

        # 5. Deprecate version hiện tại (không phải target)
        current = bom_doc.current_version
        if current and current != target.name:
            frappe.db.set_value("AL BOM Version", current, "status", "Deprecated")

        # 6. Cập nhật BOM.current_version
        frappe.db.set_value("AL BOM", bom_doc.name, "current_version", new_ver.name)

        # 7. Ghi change log
        self._add_change_log(new_ver.name, "ROLLBACK", requester, {
            "target_doctype": "AL BOM Version",
            "target_record": target.name,
            "old_value": f"Version {target.version_number}",
            "new_value": f"Version {new_ver.version_number} (rollback)",
        })

        return new_ver

    # ---- Helpers ----

    def _doc_to_dict(self, doc):
        """Chuyển DocType → dict (loại bỏ internal fields)."""
        if not doc:
            return {}
        d = doc.as_dict()
        # Remove internal fields
        for k in list(d.keys()):
            if k.startswith("_") or k in ("doctype", "idx", "owner", "creation", "modified", "modified_by"):
                del d[k]
        return d

    def _restore_doc_from_snapshot(self, doctype, docname, snapshot):
        """Restore 1 document từ snapshot (chỉ update scalar fields + child tables)."""
        doc = frappe.get_doc(doctype, docname)

        # Update scalar fields
        skip_fields = {"name", "doctype", "owner", "creation", "modified", "modified_by",
                       "al_lines", "al_var_details", "al_pk_lines", "al_discount_tiers",
                       "al_plan_lines", "al_change_logs"}
        for field, value in snapshot.items():
            if field in skip_fields:
                continue
            if hasattr(doc, field) and field not in [c.fieldname for c in doc.meta.get_table_fields()]:
                doc.set(field, value)

        # Restore child tables
        doc.save(ignore_permissions=True)

    def _add_change_log(self, version_name, change_type, changed_by, details):
        """Thêm 1 dòng AL BOM Change Log."""
        log = frappe.new_doc("AL BOM Change Log")
        log.parent = version_name
        log.parenttype = "AL BOM Version"
        log.parentfield = "al_change_logs"
        log.change_type = change_type
        log.changed_by = changed_by or (frappe.session.user if frappe.session else None)
        log.changed_on = now()
        log.target_doctype = details.get("target_doctype", "")
        log.target_record = details.get("target_record", "")
        log.field_name = details.get("field_name", "")
        log.old_value = str(details.get("old_value", ""))
        log.new_value = str(details.get("new_value", ""))
        log.impact_estimate = details.get("impact_estimate", "LOW")
        log.insert(ignore_permissions=True)


# Doc events cho AL BOM Version
def on_version_created(doc, method):
    """After insert: tự động ghi change log."""
    pass


def on_version_status_changed(doc, method):
    """Khi status thay đổi → cập nhật BOM.current_version."""
    if doc.status == "Published" and not doc.published_on:
        doc.db_set("published_on", now())
        frappe.db.set_value("AL BOM", doc.bom, "current_version", doc.name)
        frappe.db.set_value("AL BOM", doc.bom, "last_published_on", now())
    elif doc.status == "Deprecated":
        # Nếu version này đang là current_version của BOM
        current = frappe.db.get_value("AL BOM", doc.bom, "current_version")
        if current == doc.name:
            # Tìm version Published mới nhất khác
            latest = frappe.db.get_value(
                "AL BOM Version",
                {"bom": doc.bom, "status": "Published", "name": ["!=", doc.name]},
                "name",
                order_by="version_number desc",
            )
            frappe.db.set_value("AL BOM", doc.bom, "current_version", latest or "")
