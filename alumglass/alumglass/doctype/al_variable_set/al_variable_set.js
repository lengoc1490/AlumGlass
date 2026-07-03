// AL Variable Set — Client-side form script
frappe.ui.form.on('AL Variable Set', {
    refresh(frm) {},
    validate(frm) {
        if (!frm.doc.al_var_details || frm.doc.al_var_details.length === 0) {
            frappe.msgprint(__('Variable Set must have at least one Variable Detail row'));
            frappe.validated = false;
        }
    }
});
