// AL Material Plan — Client-side form script
frappe.ui.form.on('AL Material Plan', {
    refresh(frm) {
        if (frm.doc.status === 'Confirmed') {
            frm.set_df_property('al_plan_lines', 'cannot_add_rows', true);
            frm.set_df_property('al_plan_lines', 'cannot_delete_rows', true);
        }
        if (frm.doc.status === 'Draft') {
            frm.add_custom_button(__('Generate Plan Lines'), () => {
                frappe.call({
                    method: 'alumglass.modules.mrp.api.generate_plan_lines',
                    args: {plan_name: frm.doc.name},
                    callback(r) { frm.reload_doc(); }
                });
            }).addClass('btn-primary');
        }
    },
    validate(frm) {
        const qtList = frm.doc.quotation_list ? JSON.parse(frm.doc.quotation_list) : [];
        const soList = frm.doc.so_list ? JSON.parse(frm.doc.so_list) : [];
        if (qtList.length === 0 && soList.length === 0) {
            frappe.msgprint(__('Must reference at least one Quotation or Sales Order'));
            frappe.validated = false;
        }
    }
});
