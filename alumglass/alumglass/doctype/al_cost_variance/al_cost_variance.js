// AL Cost Variance — Read-only form (auto-calculated)
frappe.ui.form.on('AL Cost Variance', {
    refresh(frm) {
        if (!frm.doc.__islocal) {
            frm.disable_form();
        }
    }
});
