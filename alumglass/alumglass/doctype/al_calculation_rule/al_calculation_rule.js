// AL Calculation Rule — Client-side form script
frappe.ui.form.on('AL Calculation Rule', {
    refresh(frm) {
        // Show/hide fields based on rule_type
        const rt = frm.doc.rule_type;
        frm.toggle_display('threshold_input_var', rt === 'THRESHOLD');
        frm.toggle_display('threshold_rows', rt === 'THRESHOLD');
        frm.toggle_display('lookup_key_1_var', rt === 'LOOKUP');
        frm.toggle_display('lookup_key_2_var', rt === 'LOOKUP');
        frm.toggle_display('lookup_key_3_var', rt === 'LOOKUP');
        frm.toggle_display('lookup_rows', rt === 'LOOKUP');
        frm.toggle_display('lookup_default', rt === 'LOOKUP');
    },
    rule_type(frm) {
        frm.refresh();
    },
    validate(frm) {
        if (frm.doc.rule_type === 'THRESHOLD') {
            if (!frm.doc.threshold_rows || frm.doc.threshold_rows.length === 0) {
                frappe.msgprint(__('THRESHOLD rule must have at least one Threshold Row'));
                frappe.validated = false;
            }
        }
        if (frm.doc.rule_type === 'LOOKUP') {
            if (!frm.doc.lookup_rows || frm.doc.lookup_rows.length === 0) {
                frappe.msgprint(__('LOOKUP rule must have at least one Lookup Row'));
                frappe.validated = false;
            }
        }
    }
});
