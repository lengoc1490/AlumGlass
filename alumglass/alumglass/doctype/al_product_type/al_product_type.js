// AL Product Type — Client-side form script
frappe.ui.form.on('AL Product Type', {
    refresh(frm) {},
    validate(frm) {
        if (frm.doc.nc_pct < 0) {
            frappe.msgprint(__('NC Production (%) cannot be negative'));
            frappe.validated = false;
        }
    }
});
