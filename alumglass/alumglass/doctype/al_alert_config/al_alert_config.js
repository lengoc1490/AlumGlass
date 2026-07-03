// AL Alert Config — Client-side form script
frappe.ui.form.on('AL Alert Config', {
    refresh(frm) {},
    validate(frm) {
        if (!frm.doc.threshold_value || frm.doc.threshold_value <= 0) {
            frappe.msgprint(__('Threshold Value must be greater than 0'));
            frappe.validated = false;
        }
    }
});
