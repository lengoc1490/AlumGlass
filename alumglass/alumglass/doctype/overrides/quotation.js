// AlumGlass — Quotation override: Row buttons + dialog cho từng dòng sản phẩm
frappe.ui.form.on("Quotation", {
    refresh(frm) {
        // ── Toolbar buttons (toàn form) ────────────────────────────
        frm.add_custom_button(__("📐 Tham số BOM"), () => {
            const sel = _get_selected_row(frm);
            if (sel) new alumglass.quotation.ItemParamDialog(frm, sel).show();
            else frappe.msgprint(__("Chọn 1 dòng sản phẩm trong bảng rồi bấm nút"));
        }, __("AlumGlass"));

        frm.add_custom_button(__("💰 Tính giá BOM"), () => {
            const sel = _get_selected_row(frm);
            if (!sel) { frappe.msgprint(__("Chọn 1 dòng sản phẩm trước")); return; }
            if (!sel.al_bom) { frappe.msgprint(__("Dòng chưa chọn BOM. Mở 📐 Tham số BOM trước.")); return; }
            new alumglass.BOMDialog(sel.name).show();
        }, __("AlumGlass"));

        // ── Row-level buttons + double-click ───────────────────────
        _attach_row_actions(frm);
    },

    after_save(frm) {
        setTimeout(() => _attach_row_actions(frm), 600);
    },
});

// ── Helper: lấy dòng được chọn trong grid ───────────────────────────
function _get_selected_row(frm) {
    const grid = frm.fields_dict["items"]?.grid;
    if (!grid) return null;
    const sel = grid.get_selected_children?.();
    return sel?.length ? sel[0] : null;
}

// ── Gắn button + double-click cho từng dòng trong bảng Items ────────
function _attach_row_actions(frm) {
    const grid = frm.fields_dict["items"]?.grid;
    if (!grid) return;

    // Dùng grid.wrapper thay vì grid_rows để bắt cả row render sau
    const $grid = grid.wrapper ? $(grid.wrapper) : $(grid.$wrapper);
    if (!$grid.length) return;

    // ── Cách 1: Gắn button vào grid form (form mở rộng của dòng) ──
    // Mỗi lần grid render row, thêm nút vào cột đầu tiên
    $grid.find(".grid-row").each(function () {
        const $row = $(this);
        if ($row.data("_al_btn")) return;
        $row.data("_al_btn", true);

        // Thêm nút ⚙️ vào đầu dòng
        const $firstCell = $row.find(".grid-static-col:first");
        if ($firstCell.length && !$firstCell.find(".al-row-btn").length) {
            const $btn = $(`<button class="al-row-btn btn btn-xs btn-default"
                title="Mở tham số BOM"
                style="padding:0 4px;margin-right:4px;font-size:11px;line-height:18px;">📐</button>`);
            $btn.on("click", function (e) {
                e.stopPropagation();
                e.preventDefault();
                const rowDoc = _get_row_doc(frm, $row);
                if (rowDoc) new alumglass.quotation.ItemParamDialog(frm, rowDoc).show();
            });
            $firstCell.prepend($btn);
        }

        // Double-click để mở dialog
        $row.off("dblclick.alumglass").on("dblclick.alumglass", function () {
            const rowDoc = _get_row_doc(frm, $row);
            if (rowDoc) new alumglass.quotation.ItemParamDialog(frm, rowDoc).show();
        });
    });

    // ── Cách 2: Dùng open_row_button của grid form ─────────────────
    // Thêm nút vào form con khi mở rộng dòng
    if (!frm._al_grid_form_hooked) {
        frm._al_grid_form_hooked = true;
        const childDt = "Quotation Item";

        // Hook form_render của child table để thêm nút
        const orig_on = frappe.ui.form.on;
        frappe.ui.form.on(childDt, {
            form_render(innerFrm, cdt, cdn) {
                // Chỉ xử lý khi mở trong context của Quotation hiện tại
                if (innerFrm.docname !== frm.docname) return;
                setTimeout(() => {
                    const row = frappe.get_doc(cdt, cdn);
                    if (!row) return;
                    // Thêm nút vào grid form body
                    const gridBody = $(`.grid-row[data-name="${cdn}"] .grid-form-body`);
                    if (gridBody.length && !gridBody.find(".al-form-btn").length) {
                        const $formBtns = $(`<div class="al-form-btn" style="padding:6px 0;border-top:1px solid #e5e7eb;margin-top:8px;">
                            <button class="btn btn-sm btn-primary al-btn-params">
                                📐 ${__("Tham số BOM")}
                            </button>
                            <button class="btn btn-sm btn-default al-btn-preview">
                                🖥️ ${__("Preview tính giá")}
                            </button>
                        </div>`);
                        $formBtns.find(".al-btn-params").on("click", function () {
                            new alumglass.quotation.ItemParamDialog(frm, row).show();
                        });
                        $formBtns.find(".al-btn-preview").on("click", function () {
                            if (!row.al_bom) {
                                frappe.msgprint(__("Chưa chọn BOM. Vui lòng mở Tham số BOM trước."));
                                return;
                            }
                            // Lưu trước rồi preview
                            frappe.model.set_value(cdt, cdn, "al_bom_vars",
                                JSON.stringify(_collect_form_vars(innerFrm, cdn) || {}));
                            new alumglass.BOMDialog(cdn).show();
                        });
                        gridBody.append($formBtns);
                    }
                }, 400);
            },
        });
    }
}

// ── Lấy doc của row từ grid row element ────────────────────────────
function _get_row_doc(frm, $row) {
    const cdn = $row.attr("data-name");
    if (!cdn) return null;
    const rows = frm.doc?.items || [];
    return rows.find(r => r.name === cdn) || null;
}

// ── Thu thập giá trị form từ grid form con ──────────────────────────
function _collect_form_vars(innerFrm, cdn) {
    const row = frappe.get_doc("Quotation Item", cdn);
    if (!row) return {};
    // Merge với al_bom_vars hiện có
    let vars = {};
    try { vars = JSON.parse(row.al_bom_vars || "{}"); } catch (e) {}
    // Giữ nguyên vars, chỉ đảm bảo BOM version đúng
    if (row.al_bom && !vars._bom) vars._bom = row.al_bom;
    return vars;
}
