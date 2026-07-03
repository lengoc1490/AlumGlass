// AL Dashboard Config — Client-side form script
frappe.ui.form.on('AL Dashboard Config', {
    refresh(frm) {},
    validate(frm) {
        if (frm.doc.widgets) {
            try {
                const w = JSON.parse(frm.doc.widgets);
                if (!Array.isArray(w)) {
                    frappe.msgprint(__('Widgets must be a JSON array'));
                    frappe.validated = false;
                }
            } catch(e) {
                frappe.msgprint(__('Widgets JSON is invalid'));
                frappe.validated = false;
            }
        }
    }
});
