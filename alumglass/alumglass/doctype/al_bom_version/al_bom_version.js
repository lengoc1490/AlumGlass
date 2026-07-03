// AL BOM Version — Client-side form script
frappe.ui.form.on('AL BOM Version', {
    refresh(frm) {
        // If Published, make read-only
        if (frm.doc.status === 'Published' && !frm.doc.__islocal) {
            frm.disable_form();
            frm.add_custom_button(__('View Snapshot Diff'), () => {
                // Navigate to diff comparison
                frappe.msgprint(__('Snapshot comparison will be available in the Version Manager.'));
            });
        }
        // Show publish button for Draft versions
        if (frm.doc.status === 'Draft' && !frm.doc.__islocal) {
            frm.add_custom_button(__('Publish'), () => {
                frm.set_value('status', 'Published');
                frm.save();
            }).addClass('btn-primary');
        }
    },
    validate(frm) {
        if (frm.doc.status === 'Published') {
            const oldStatus = frm.doc._original_status || '';
            if (oldStatus === 'Published') {
                frappe.msgprint(__('Published BOM Versions are immutable. Create a new version instead.'));
                frappe.validated = false;
            }
        }
    }
});
