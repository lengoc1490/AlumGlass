// AL Glass Master — Client-side form script with validation
frappe.ui.form.on('AL Glass Master', {
    refresh(frm) {},
    validate(frm) {
        if (frm.doc.total_thick_mm && frm.doc.total_thick_mm <= 0) {
            frappe.msgprint(__('Total Thickness (mm) must be greater than 0'));
            frappe.validated = false;
        }
    }
});
