// AL BOM — Client-side form script
frappe.ui.form.on('AL BOM', {
    refresh(frm) {
        // Show version info if available
        if (frm.doc.current_version) {
            frm.add_custom_button(__('View Current Version'), () => {
                frappe.set_route('Form', 'AL BOM Version', frm.doc.current_version);
            });
        }
        if (frm.doc.__islocal) {
            frm.set_value('total_versions', 0);
        }
    },
    validate(frm) {
        if (!frm.doc.variable_set) {
            frappe.msgprint(__('Variable Set is required'));
            frappe.validated = false;
        }
        if (!frm.doc.profile_set) {
            frappe.msgprint(__('Profile Set is required'));
            frappe.validated = false;
        }
        if (!frm.doc.default_cost_template) {
            frappe.msgprint(__('Default Cost Template is required'));
            frappe.validated = false;
        }
    }
});
