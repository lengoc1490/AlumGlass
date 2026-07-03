// AL Variable Library — Client-side form script
frappe.ui.form.on('AL Variable Library', {
    refresh(frm) {
        // Show/hide options field based on ui_widget selection
        frm.set_df_property('options', 'reqd', frm.doc.ui_widget === 'Select');
    },
    ui_widget(frm) {
        frm.set_df_property('options', 'reqd', frm.doc.ui_widget === 'Select');
    },
    validate(frm) {
        if (frm.doc.var_code && frm.doc.var_code.includes(' ')) {
            frappe.msgprint(__('Variable Code cannot contain spaces'));
            frappe.validated = false;
        }
    }
});
