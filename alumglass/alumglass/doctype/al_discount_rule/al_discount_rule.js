// AL Discount Rule — Client-side form script
frappe.ui.form.on('AL Discount Rule', {
    refresh(frm) {
        frm.toggle_display('al_discount_tiers', frm.doc.rule_type === 'VOLUME');
        frm.toggle_display('discount_pct', frm.doc.rule_type !== 'VOLUME');
        frm.toggle_display('approval_threshold_pct', frm.doc.requires_approval);
    },
    rule_type(frm) { frm.refresh(); },
    requires_approval(frm) { frm.refresh(); },
    validate(frm) {
        if (frm.doc.valid_from && frm.doc.valid_to) {
            if (new Date(frm.doc.valid_from) >= new Date(frm.doc.valid_to)) {
                frappe.msgprint(__('Valid From must be before Valid To'));
                frappe.validated = false;
            }
        }
        if (frm.doc.requires_approval && !frm.doc.approval_threshold_pct) {
            frappe.msgprint(__('Approval Threshold (%) is required when approval is enabled'));
            frappe.validated = false;
        }
    }
});
