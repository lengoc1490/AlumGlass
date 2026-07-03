// AL Cost Bucket — Client-side form script
frappe.ui.form.on('AL Cost Bucket', {
    refresh(frm) {},
    validate(frm) {
        if (frm.doc.parent_bucket === frm.doc.bucket_code) {
            frappe.msgprint(__('A Cost Bucket cannot be its own parent'));
            frappe.validated = false;
        }
    }
});
