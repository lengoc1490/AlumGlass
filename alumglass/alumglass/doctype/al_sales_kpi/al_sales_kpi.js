// AL Sales KPI — Client-side form script
frappe.ui.form.on('AL Sales KPI', {
    refresh(frm) {},
    validate(frm) {
        if (!frm.doc.target_amount || frm.doc.target_amount <= 0) {
            frappe.msgprint(__('Target Amount must be greater than 0'));
            frappe.validated = false;
        }
    }
});
