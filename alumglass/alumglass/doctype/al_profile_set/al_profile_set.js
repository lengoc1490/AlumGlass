// AL Profile Set — Client-side form script
frappe.ui.form.on('AL Profile Set', {
    refresh(frm) {},
    validate(frm) {
        const lines = frm.doc.al_lines || [];
        if (lines.length === 0) {
            frappe.msgprint(__('Profile Set must have at least one Profile Line'));
            frappe.validated = false;
            return;
        }
        const hasGlass = lines.some(l => l.line_type === 'KINH');
        if (!hasGlass) {
            frappe.msgprint(__('Profile Set must have at least one Glass (KINH) line'));
            frappe.validated = false;
        }
    }
});
