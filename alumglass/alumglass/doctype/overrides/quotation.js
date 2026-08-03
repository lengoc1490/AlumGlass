// AlumGlass — Quotation override: Thêm nút tham số BOM + tính giá
frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (frm.is_new()) return;

        // Nút "📐 Tham số BOM" — mở dialog cho dòng được chọn
        frm.add_custom_button(__("📐 Tham số BOM"), () => {
            const grid = frm.fields_dict["items"]?.grid;
            const sel = grid?.get_selected_children?.();
            if (sel?.length) {
                new alumglass.quotation.ItemParamDialog(frm, sel[0]).show();
            } else {
                frappe.msgprint(__("Chọn 1 dòng sản phẩm trong bảng rồi bấm nút"));
            }
        }, __("AlumGlass"));

        // Nút "💰 Tính giá BOM" — tính giá cho dòng được chọn
        frm.add_custom_button(__("💰 Tính giá BOM"), () => {
            const grid = frm.fields_dict["items"]?.grid;
            const sel = grid?.get_selected_children?.();
            if (!sel?.length) {
                frappe.msgprint(__("Chọn 1 dòng sản phẩm trước"));
                return;
            }
            if (!sel[0].al_bom) {
                frappe.msgprint(__("Dòng chưa chọn BOM. Bấm 📐 Tham số BOM trước."));
                return;
            }
            new alumglass.BOMDialog(sel[0].name).show();
        }, __("AlumGlass"));

        // Gắn double-click vào dòng grid để mở nhanh dialog
        _attach_dblclick(frm);
    },

    after_save(frm) {
        setTimeout(() => _attach_dblclick(frm), 500);
    },
});

function _attach_dblclick(frm) {
    const grid = frm.fields_dict["items"]?.grid;
    if (!grid?.grid_rows) return;
    grid.grid_rows.forEach(row => {
        if (row._al_dblclick) return;
        row._al_dblclick = true;
        // Thêm icon nhỏ vào đầu dòng
        const $row = $(row.wrapper);
        const $icon = $(`<span class="al-row-icon" title="Double-click để mở tham số BOM" 
            style="cursor:pointer;opacity:0.5;margin-right:4px;">⚙️</span>`);
        $icon.on("click", (e) => {
            e.stopPropagation();
            new alumglass.quotation.ItemParamDialog(frm, row.doc).show();
        });
        const $cell = $row.find(".grid-static-col:first");
        if ($cell.length && !$cell.find(".al-row-icon").length) {
            $cell.prepend($icon);
        }
        // Double-click
        $row.on("dblclick", () => {
            new alumglass.quotation.ItemParamDialog(frm, row.doc).show();
        });
    });
}
