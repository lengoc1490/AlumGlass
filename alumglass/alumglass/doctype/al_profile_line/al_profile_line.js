// AL Profile Line — Client-side form script for core material line
frappe.ui.form.on('AL Profile Line', {
    refresh(frm) {
        // Show/hide sections based on line_type
        const lt = frm.doc.line_type;
        frm.toggle_display('section_aluminum', lt === 'Aluminum' || lt === 'Consumable');
        frm.toggle_display('section_glass', lt === 'Glass');
        frm.toggle_display('section_accessory_inline', lt === 'Accessory');
        frm.set_df_property('ctx_inject_prefix', 'reqd', lt === 'Glass');
        frm.set_df_property('default_glass_master', 'reqd', lt === 'Glass');
    },
    line_type(frm) {
        frm.refresh();
    },
    price_type(frm) {
        // Show/hide price fields based on price_type
        frm.toggle_display('price_rule', frm.doc.price_type === 'Rule');
        frm.toggle_display('fixed_price', frm.doc.price_type === 'Fixed');
        frm.toggle_display('price_list', frm.doc.price_type === 'Item Price');
    },
    validate(frm) {
        if (frm.doc.line_type === 'Glass') {
            const prefix = (frm.doc.ctx_inject_prefix || '').trim();
            if (!prefix) {
                frappe.msgprint(__('Context Inject Prefix is required for Glass lines'));
                frappe.validated = false;
            } else if (/[0-9]$/.test(prefix)) {
                frappe.msgprint(__('Context Inject Prefix must NOT end with a digit'));
                frappe.validated = false;
            }
            if (!frm.doc.default_glass_master) {
                frappe.msgprint(__('Default Glass Master is required for Glass lines'));
                frappe.validated = false;
            }
        }
    }
});
