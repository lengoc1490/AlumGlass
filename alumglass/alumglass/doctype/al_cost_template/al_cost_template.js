// AL Cost Template — Client-side form script
frappe.ui.form.on('AL Cost Template', {
    refresh(frm) {
        // If formula_set is set, make al_lines optional
        const hasFormulaSet = frm.doc.formula_set;
        frm.set_df_property('al_lines', 'reqd', !hasFormulaSet);
    },
    formula_set(frm) {
        frm.refresh();
    },
    validate(frm) {
        if (!frm.doc.formula_set) {
            if (!frm.doc.al_lines || frm.doc.al_lines.length === 0) {
                frappe.msgprint(__('Cost Template must have at least one Cost Line or reference a Formula Set'));
                frappe.validated = false;
            }
        }
    }
});
