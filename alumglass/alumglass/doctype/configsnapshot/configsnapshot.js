// ConfigSnapshot — Read-only audit trail, no editing needed
frappe.ui.form.on('ConfigSnapshot', {
    refresh(frm) {
        frm.disable_form();
        if (frm.doc.enterprise_snapshot_json) {
            frm.add_custom_button(__('View Full Snapshot'), () => {
                const data = JSON.parse(frm.doc.enterprise_snapshot_json);
                const d = new frappe.ui.Dialog({
                    title: __('Enterprise Snapshot'),
                    fields: [{fieldname: 'html', fieldtype: 'HTML', options: `<pre>${JSON.stringify(data, null, 2)}</pre>`}],
                    size: 'large'
                });
                d.show();
            });
        }
    }
});
