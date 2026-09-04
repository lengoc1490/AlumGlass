// ═══════════════════════════════════════════════════════════════════════════
// AlumGlass — Quotation override: Row buttons + ItemParamDialog + BOMDialog
// ═══════════════════════════════════════════════════════════════════════════
// Tổ chức theo eupapp: toàn bộ logic per-doctype nằm trong 1 file override
// load qua doctype_js của "Quotation" — KHÔNG load toàn trang qua app_include_js.
//
// ── ItemParamDialog ────────────────────────────────────────────────────────
//   Dialog tham số BOM cho TỪNG dòng con Quotation Item.
//   - Biến đầu vào render động từ Variable Set (alumglass.api.get_variable_set_for_bom)
//   - Layout 2 cột thoáng, không hardcode field nào
//   - Biến mở rộng = Table field chuẩn Frappe (add/delete row)
//   - Preview tính giá async (realtime "alumglass_bom_calc_done", spinner)
//   - Đổi BOM → chỉ re-render vùng biến trong dialog CŨ (không recreate dialog)
//
// ── BOMDialog ──────────────────────────────────────────────────────────────
//   Dialog kết quả tính giá BOM (tách từ public/js/bom_dialog.js, gộp vào đây)
// ═══════════════════════════════════════════════════════════════════════════

frappe.provide("alumglass");
frappe.provide("alumglass.quotation");

// ═══════════════════════════════════════════════════════════════════════════
// Renderer dùng CHUNG cho kết quả BOM (V6 Phase 2 — A4 + B)
// ─────────────────────────────────────────────────────────────────────────────
// Nguồn dữ liệu: display model từ `alumglass.api.get_result_display` —
//   server đã resolve label + công thức + trace. ItemParamDialog (preview)
//   và BOMDialog (🖥️) cùng gọi renderer này → KHÔNG duplicate code render.
//
// opts:
//   collapsible : wrap mỗi phần trong <details> (mặc định true)
//   show_trace  : hiện trace (formula → thay biến → kết quả) mỗi dòng cost_template
//   compact     : font nhỏ hơn cho preview inline (mặc định false)
//   title       : tiêu đề in đậm đầu render (tuỳ chọn)
// ═══════════════════════════════════════════════════════════════════════════
alumglass.render_bom_result_display = function (display, opts) {
    opts = opts || {};
    display = display || {};
    const summary = display.summary || {};
    const lines = display.lines || [];
    const buckets = display.buckets || [];
    const cost_template = display.cost_template || [];

    const fs = opts.compact ? "11px" : "12px";
    const wrap = (title, body) => {
        if (opts.collapsible === false) {
            return `<div style="margin:8px 0;">${body}</div>`;
        }
        return `<details class="al-bom-collapse" style="margin:6px 0;" open>
            <summary style="cursor:pointer;font-weight:600;color:#1e293b;padding:6px 8px;
                background:#f1f5f9;border-radius:4px;font-size:${fs};">${title}</summary>
            <div style="padding:6px 4px;">${body}</div>
        </details>`;
    };

    let html = `<div class="al-bom-display" style="font-size:${fs};line-height:1.45;">`;
    if (opts.title) {
        html += `<h3 style="margin-top:0;margin-bottom:8px;color:#0f172a;font-size:14px;">${alumglass.esc(opts.title)}</h3>`;
    }

    // ── Summary bar ─────────────────────────────────────────────────
    if (summary.calculated) {
        html += `<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px;
            padding:8px 10px;background:#fffbeb;border:1px solid #fde68a;border-radius:6px;">
            <span><strong>${__("Giá bán")}:</strong>
                <span style="color:#b45309;font-weight:700;">${format_currency(summary.gia_ban || 0)}</span></span>
            <span><strong>${__("VAT")}:</strong> ${format_currency(summary.gia_vat || 0)}</span>
            <span><strong>${__("Số dòng vật tư")}:</strong> ${summary.line_count || 0}</span>
        </div>`;
    }

    // ── Chi tiết vật tư (lines) ─────────────────────────────────────
    // V6 P7 (Phase 3): tách cột Mã/Tên + thêm Trọng lượng/Khối lượng/ĐVT.
    //   Trọng lượng = weight_per_unit (kg/m) — chỉ vật tư has_weight
    //   (NHÔM/THÉP/INOX), loại khác "—". Khối lượng = total_qty (engine B4).
    //   ĐVT = output_unit từ calc_pattern (API `get_result_display`).
    //   Trace 2 tầng: line vật tư (show_trace) + cost template (cột Diễn giải).
    if (lines.length) {
        let body = `<div style="overflow-x:auto;">
            <table class="table table-condensed table-bordered" style="margin:0;font-size:${fs};min-width:900px;">
            <thead style="background:#f1f5f9;"><tr>
                <th>${__("Mã vật tư")}</th>
                <th>${__("Tên vật tư")}</th>
                <th class="text-center">${__("Rộng (mm)")}</th>
                <th class="text-center">${__("Cao (mm)")}</th>
                <th class="text-center">${__("Số lượng")}</th>
                <th class="text-center">${__("Trọng lượng")}</th>
                <th class="text-center">${__("Khối lượng")}</th>
                <th class="text-center">${__("ĐVT")}</th>
                <th class="text-right">${__("Đơn giá")}</th>
                <th class="text-right">${__("Thành tiền")}</th>
                <th>${__("Nhóm CP")}</th>
            </tr></thead><tbody>`;
        lines.forEach(function (ln) {
            const hasWeight = ln.has_weight !== undefined ? !!ln.has_weight : (Number(ln.weight_per_unit) > 0);
            const weightHtml = (hasWeight && Number(ln.weight_per_unit) > 0)
                ? `${format_number(ln.weight_per_unit)} <span style="color:#94a3b8;font-size:10px;">kg/m</span>`
                : "—";
            const qty = ln.qty || 0;
            const totalQty = ln.total_qty || 0;
            const unit = ln.unit ? alumglass.esc(ln.unit) : "—";
            const lineTrace = (opts.show_trace && ln.trace)
                ? `<details style="margin-top:3px;"><summary style="cursor:pointer;font-size:10px;color:#64748b;">${__("Xem trace")}</summary>
                    <div style="font-size:10px;color:#475569;background:#f8fafc;padding:4px 6px;border-radius:4px;
                        word-break:break-all;font-family:monospace;">${alumglass.esc(alumglass.format_trace(ln.trace))}</div></details>`
                : "";
            body += `<tr>
                <td style="color:#64748b;white-space:nowrap;">${alumglass.esc(ln.item_code || ln.slug)}</td>
                <td><strong>${alumglass.esc(ln.label || ln.slug)}</strong>${lineTrace}</td>
                <td class="text-center">${(ln.width !== undefined && ln.width !== null && ln.width !== "") ? format_number(ln.width) : "—"}</td>
                <td class="text-center">${(ln.height !== undefined && ln.height !== null && ln.height !== "") ? format_number(ln.height) : "—"}</td>
                <td class="text-center">${format_number(qty)}${ln.unit_qty ? ` <span style="color:#94a3b8;">(${format_number(ln.unit_qty)}/đv)</span>` : ""}</td>
                <td class="text-center">${weightHtml}</td>
                <td class="text-center">${format_number(totalQty)}</td>
                <td class="text-center">${unit}</td>
                <td class="text-right">${format_currency(ln.unit_price || 0)}</td>
                <td class="text-right"><strong>${format_currency(ln.line_total || 0)}</strong></td>
                <td style="font-size:10px;color:#64748b;">${alumglass.esc(ln.bucket_name || ln.cost_bucket || "")}</td>
            </tr>`;
        });
        body += `</tbody></table></div>`;
        html += wrap(`${__("Chi tiết vật tư")} <span style="font-weight:400;color:#94a3b8;">(${lines.length} dòng)</span>`, body);
    }

    // ── Tổng theo nhóm chi phí (buckets) ────────────────────────────
    if (buckets.length) {
        let body = `<table class="table table-condensed table-bordered" style="margin:0;font-size:${fs};">
            <thead style="background:#f1f5f9;"><tr>
                <th>${__("Nhóm chi phí")}</th>
                <th class="text-right">${__("Thành tiền")}</th>
            </tr></thead><tbody>`;
        buckets.forEach(function (b) {
            body += `<tr>
                <td><strong>${alumglass.esc(b.bucket_name || b.bucket_code)}</strong>
                    ${b.bucket_name && b.bucket_code ? `<div style="color:#94a3b8;font-size:10px;">${alumglass.esc(b.bucket_code)}</div>` : ""}</td>
                <td class="text-right">${format_currency(b.value || 0)}</td>
            </tr>`;
        });
        body += `</tbody></table>`;
        html += wrap(__("Tổng theo nhóm chi phí"), body);
    }

    // ── Chi phí chế tạo (cost_template) ─────────────────────────────
    // V6 P7 (Phase 3): cột Diễn giải = trace (server nâng cấp "8% × TONG_VL
    // (1,000,000) = 80,000"); cột ĐVT cho từng khoản mục. Diễn giải luôn hiện.
    if (cost_template.length) {
        let body = `<div style="overflow-x:auto;">
            <table class="table table-condensed table-bordered" style="margin:0;font-size:${fs};min-width:680px;">
            <thead style="background:#f1f5f9;"><tr>
                <th style="width:22%;">${__("Khoản mục")}</th>
                <th style="width:24%;">${__("Công thức")}</th>
                <th>${__("Diễn giải")}</th>
                <th class="text-right">${__("Giá trị")}</th>
                <th class="text-center" style="width:60px;">${__("ĐVT")}</th>
            </tr></thead><tbody>`;
        cost_template.forEach(function (c) {
            const bold = c.is_subtotal;
            const name = alumglass.esc(c.line_label || c.line_code);
            const formula = c.calc_formula ? `<code style="font-size:10px;background:#f8fafc;padding:1px 4px;border-radius:3px;color:#334155;">${alumglass.esc(c.calc_formula)}</code>` : "";
            const diengiai = c.trace
                ? `<span style="font-size:10px;color:#475569;font-family:monospace;word-break:break-all;">${alumglass.esc(alumglass.format_trace(c.trace))} <strong>= ${format_number(c.value || 0)}</strong></span>`
                : `<span style="color:#94a3b8;">—</span>`;
            const ctUnit = c.unit ? alumglass.esc(c.unit) : "—";
            body += `<tr class="${bold ? "font-weight-bold" : ""}"
                style="${bold ? "background:#fef3c7;" : ""}">
                <td>${bold ? "━━ " : ""}${name}</td>
                <td>${formula}</td>
                <td>${diengiai}</td>
                <td class="text-right">${format_currency(c.value || 0)}</td>
                <td class="text-center">${ctUnit}</td>
            </tr>`;
        });
        body += `</tbody></table></div>`;
        html += wrap(__("Chi phí chế tạo"), body);
    }

    // ── Chưa tính ───────────────────────────────────────────────────
    if (!summary.calculated && !lines.length && !cost_template.length) {
        html += `<p class="text-muted" style="margin:8px 0;">${__("Chưa có kết quả tính giá cho sản phẩm này.")}</p>`;
    }

    html += `</div>`;
    return html;
};

// Helper escape dùng chung (tránh XSS khi render label từ DB)
alumglass.esc = function (s) {
    return String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
};

// Formatter diễn giải (trace) — nâng cấp readability phần "Diễn giải":
//   - `TOKEN=value` → `TOKEN(value)` (trace cũ dạng `NC_SX_PCT=0.08`)
//   - Giá trị % dạng 0.08 → `8%` (tránh hiểu nhầm "0.08%").
// Forward-compatible: nếu server (DEV1) đã trả trace dạng đẹp
// ("8% × TONG_VL(1,000,000) = 80,000") thì các regex không đụng tới.
alumglass.format_trace = function (trace) {
    if (!trace) return "";
    let t = String(trace);
    // `TOKEN=value` (giá trị số, không phải dấu so sánh) → `TOKEN(value)`
    t = t.replace(/\b([A-Za-z_][A-Za-z0-9_]*)=(-?[0-9]*\.?[0-9]+)\b/g, "$1($2)");
    // Giá trị % dạng thập phân < 1 → phần trăm nguyên (0.08 → 8%)
    t = t.replace(/\b([A-Za-z_][A-Za-z0-9_]*?)\s*\(\s*(-?0\.\d+)\s*\)/g, function (m, token, val) {
        const v = parseFloat(val);
        if (v > 0 && v < 1) {
            const pct = Math.round(v * 10000) / 100;
            return token + "(" + pct + "%)";
        }
        return m;
    });
    // Số lớn thêm dấu phân cách nghìn (1000000 → 1,000,000) — chỉ áp trong
    // ngoặc `TOKEN(1000000)`; không đụng `%` (đã chuyển ở bước trên).
    t = t.replace(/\(\s*(-?[0-9]+(?:\.[0-9]+)?)\s*\)/g, function (m, val) {
        const num = Number(val);
        if (!isNaN(num)) return "(" + format_number(num) + ")";
        return m;
    });
    return t;
};

// Chuyển raw al_bom_result → display model tối thiểu (label = code, không trace).
// Dùng làm FALLBACK khi get_result_display không trả được label (không có API/
// lỗi mạng) — renderer chung vẫn là nơi duy nhất render HTML.
alumglass.raw_to_display = function (raw) {
    raw = raw || {};
    const lines = (raw.lines || []).map(function (l) {
        return {
            slug: l.slug, label: l.slug, item_code: l.item_code,
            width: l.width, height: l.height, qty: l.qty, unit_qty: l.unit_qty,
            total_qty: l.total_qty, unit_price: l.unit_price, line_total: l.line_total,
            cost_bucket: l.cost_bucket, bucket_name: l.cost_bucket,
            // V6 P7 (Phase 3): pass-through Trọng lượng/Khối lượng/ĐVT + trace line
            weight_per_unit: l.weight_per_unit, unit: l.unit, has_weight: l.has_weight,
            trace: l.trace,
        };
    });
    const buckets = Object.entries(raw.buckets || {}).map(function (kv) {
        return { bucket_code: kv[0], bucket_name: kv[0], value: kv[1] };
    });
    const ct = Object.entries(raw.cost_template || {}).map(function (kv) {
        const code = kv[0];
        return {
            line_code: code, line_label: code, calc_formula: "", value: kv[1],
            is_subtotal: code.indexOf("TONG_") === 0 || code.indexOf("GIA_") === 0
                || code === "PROFIT" || code.indexOf("VAT") === 0,
            bucket_code: "", bucket_name: "", trace: "",
            unit: (raw.cost_template_units || {})[code] || "",
        };
    });
    const ct_map = raw.cost_template || {};
    return {
        summary: {
            gia_vat: raw.gia_vat || 0,
            gia_ban: ct_map.GIA_BAN || 0,
            line_count: lines.length,
            calculated: !!(lines.length || ct.length),
        },
        lines: lines,
        buckets: buckets,
        cost_template: ct,
    };
};

// ═══════════════════════════════════════════════════════════════════════════
// FIX GỐC (bug "đổi kính nhưng giá/nẹp không đổi"):
// `frappe.model.set_value()` chỉ cập nhật doc TRÊN TRÌNH DUYỆT (client-side).
// Trong khi đó server API `alumglass.api.calculate_bom` / `get_result_display`
// đều đọc dữ liệu qua `frappe.get_doc("Quotation Item", name)` — tức là đọc
// từ DATABASE, KHÔNG phải từ bộ nhớ trình duyệt. Nếu user đổi kính/tham số
// trong dialog rồi bấm Preview mà TOÀN BỘ chứng từ Quotation chưa được lưu
// (Ctrl+S) trước đó → engine vẫn tính theo `al_bom_vars` CŨ trong DB
// (glass_master_map cũ) → kính/nẹp/giá không đổi dù dialog đã đổi giá trị.
// → Mọi nơi gọi calculate_bom/BOMDialog trong file này PHẢI đồng bộ dữ liệu
//   xuống DB trước, dùng 2 helper dưới đây.
// ─────────────────────────────────────────────────────────────────────────
// `_persist_row`: ghi các field chỉ định xuống DB cho 1 dòng Quotation Item.
//   - Dòng đã tồn tại trong DB (tên không phải "new-..."): ghi thẳng bằng
//     `frappe.client.set_value` — nhanh, không cần lưu (và validate) cả
//     chứng từ Quotation.
//   - Dòng MỚI thêm, chưa từng lưu (__islocal, tên dạng "new-quotation-item-N"):
//     Frappe chỉ cấp `name` thật cho child row SAU KHI cha được lưu → bắt
//     buộc phải `frm.save()` toàn bộ chứng từ, rồi tìm lại dòng theo idx.
// Trả về Promise<string> = tên THẬT của dòng sau khi đã đảm bảo tồn tại
// trong DB với dữ liệu mới nhất.
alumglass.quotation._persist_row = function (frm, cdt, cdn, fields) {
    fields = fields || {};
    const is_local = !cdn || cdn.indexOf("new-") === 0
        || (frappe.get_doc(cdt, cdn) || {}).__islocal;

    if (!is_local) {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: "frappe.client.set_value",
                args: { doctype: cdt, name: cdn, fieldname: fields },
                callback: () => resolve(cdn),
                error: (err) => reject(err),
            });
        });
    }

    // Dòng mới — chưa có trong DB → phải lưu cả chứng từ Quotation trước.
    const localRow = frappe.get_doc(cdt, cdn) || {};
    const idx = localRow.idx;
    return frm.save().then(() => {
        const rows = (frm.doc && frm.doc.items) || [];
        let row = rows.find(r => r.name === cdn);
        if (!row && idx) row = rows.find(r => r.idx === idx);
        return row ? row.name : cdn;
    });
};

// `_sync_row_to_db`: đọc trạng thái HIỆN TẠI của dòng trong bộ nhớ trình
// duyệt (đã được `frappe.model.set_value` cập nhật trước đó, ví dụ trong
// `_save()`) rồi ghi các field then chốt cho việc tính giá xuống DB.
alumglass.quotation._sync_row_to_db = function (frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn) || {};
    const fields = {
        al_bom: row.al_bom || "",
        al_bom_version: row.al_bom_version || "",
        al_bom_vars: row.al_bom_vars || "{}",
        item_code: row.item_code || "",
        item_name: row.item_name || "",
    };
    return alumglass.quotation._persist_row(frm, cdt, cdn, fields);
};

// ═══════════════════════════════════════════════════════════════════════════
// ItemParamDialog — dialog tham số BOM cho 1 dòng Quotation Item
// ═══════════════════════════════════════════════════════════════════════════
alumglass.quotation.ItemParamDialog = class ItemParamDialog {
    constructor(frm, child_doc) {
        this.frm = frm;
        this.child_doc = child_doc;
        this.dialog = null;
        this._var_controls = [];    // [{ var_name, ctrl }] — controls biến động
        this._glass_controls = [];  // [{ rep, ctrl }] — selector kính per-line (glass_groups)
        this._current_vars = [];    // Variable Set đang hiển thị
        this._realtime_handler = null;
        this._preview_seq = 0;      // Chống race: preview cũ trả về SAU preview mới → bỏ qua
        this._debounced_auto_preview = null;
        // Chỉ bật auto-preview SAU KHI dialog đã nạp xong lần đầu — tránh việc
        // set giá trị mặc định lúc mở dialog (set_value lập trình cũng kích hoạt
        // onchange) tự động bắn 1 preview thừa ngay khi vừa mở dialog.
        this._dialog_ready = false;
    }

    show() {
        this._render_dialog();
    }

    // ── Đọc Variable Set từ BOM → Bom Set → Variable Set ──────────
    async _load_variable_set() {
        const bom = this.child_doc.al_bom;
        if (!bom) { this._bom_meta = null; return []; }

        return new Promise(resolve => {
            frappe.call({
                method: "alumglass.api.get_variable_set_for_bom",
                args: { bom_code: bom },
                callback: r => {
                    this._bom_meta = r.message || null;
                    if (r.message?.variables) {
                        resolve(r.message.variables);
                    } else {
                        resolve([]);
                    }
                },
                error: () => { this._bom_meta = null; resolve([]); },
            });
        });
    }

    // ── Fields cố định của dialog (BOM + vùng biến + extra_vars + preview) ──
    // Vùng biến động là 1 HTML container → re-render khi đổi BOM mà KHÔNG
    // phải tạo lại dialog (fix lỗi render liên tục).
    // V6 Phase 1: thêm header ảnh + mã sản phẩm, các field cấu hình editable
    // (override lưu vào al_bom_vars dạng _bom_set/_accessory_set/_profile_system/
    // _cost_template — engine đọc ở Phase 4).
    _build_dialog_fields() {
        return [
            // Header sản phẩm — ảnh + mã sp (A1) hiển thị trên đầu dialog
            { fieldtype: "Section Break", label: __("Sản phẩm") },
            { fieldname: "product_header", fieldtype: "HTML", label: "" },

            { fieldtype: "Section Break", label: __("Chọn BOM") },
            {
                fieldname: "al_bom", fieldtype: "Link", label: __("BOM"),
                options: "AL BOM", default: this.child_doc.al_bom || "",
                onchange: () => this._on_bom_change(),
            },
            {
                fieldname: "al_bom_name", fieldtype: "Data", label: __("BOM Name"),
                // A2: cho phép chỉnh sửa — lưu override _bom_name vào al_bom_vars
            },
            { fieldname: "col_bom_1", fieldtype: "Column Break" },
            {
                fieldname: "al_bom_version", fieldtype: "Link", label: __("BOM Version"),
                options: "AL BOM Version",
                default: this.child_doc.al_bom_version || "",
                get_query: () => {
                    const bom = this.dialog?.get_value("al_bom");
                    if (bom) return { filters: { bom: bom } };
                    return {};
                },
                onchange: () => this._schedule_auto_preview(),
            },
            {
                fieldname: "al_brand", fieldtype: "Link", label: __("Hãng nhôm"),
                options: "Brand",
                // A2: editable — lưu override _brand
                onchange: () => this._schedule_auto_preview(),
            },

            // Cấu hình BOM — editable (A2/A3), override lưu vào al_bom_vars
            { fieldtype: "Section Break", label: __("Cấu hình BOM") },
            {
                fieldname: "al_bom_set", fieldtype: "Link", label: __("Bom Set"),
                options: "AL Bom Set",
                onchange: () => this._schedule_auto_preview(),
            },
            {
                fieldname: "al_accessory_set", fieldtype: "Link", label: __("Phụ kiện (Accessory Set)"),
                options: "AL Accessory Set",
                onchange: () => this._schedule_auto_preview(),
            },
            { fieldname: "col_cfg_1", fieldtype: "Column Break" },
            {
                fieldname: "al_profile_system", fieldtype: "Link", label: __("Hệ profile"),
                options: "AL Profile System",
                onchange: () => this._schedule_auto_preview(),
            },
            {
                fieldname: "al_cost_template", fieldtype: "Link", label: __("Cost Template"),
                options: "AL Cost Template",
                onchange: () => this._schedule_auto_preview(),
            },

            { fieldtype: "Section Break", label: __("Tham số sản phẩm") },
            { fieldname: "vars_container", fieldtype: "HTML", label: "" },

            { fieldtype: "Section Break", label: __("Biến mở rộng (tùy chọn)") },
            {
                fieldname: "extra_vars", fieldtype: "Table",
                label: __("Biến mở rộng (tùy chọn)"),
                fields: [
                    {
                        fieldname: "var_name", fieldtype: "Link", in_list_view: 1, label: __("Tên biến"),
                        options: "AL Variable Library",
                        get_query: () => ({ filters: { is_system: 0 } }),
                    },
                    {
                        fieldname: "var_type", fieldtype: "Select", in_list_view: 1, label: __("Kiểu"),
                        options: ["Data", "Float", "Int", "Select", "Link", "Check", "Currency"],
                    },
                    { fieldname: "var_value", fieldtype: "Data", in_list_view: 1, label: __("Giá trị") },
                ],
            },

            { fieldtype: "Section Break", label: __("Kết quả Preview") },
            { fieldname: "preview_html", fieldtype: "HTML", label: "" },
        ];
    }

    // ── Render dialog ───────────────────────────────────────────────
    _render_dialog() {
        this.dialog = new frappe.ui.Dialog({
            title: __("Tham số BOM — ") + (this.child_doc.item_name || this.child_doc.item_code || __("Dòng mới")),
            fields: this._build_dialog_fields(),
            size: "large",
            primary_action_label: __("💾 Lưu"),
            primary_action: () => {
                this._save();
                this.dialog.hide();
            },
            secondary_action_label: __("🖥️ Preview tính giá"),
            secondary_action: () => {
                this._save();  // Lưu trước khi preview
                this._run_preview();
            },
        });
        this.dialog.show();
        this.dialog.$wrapper.find(".modal-dialog").css("max-width", "80vw");

        // Cleanup realtime listener khi dialog đóng (tránh leak)
        $(this.dialog.$wrapper).on("hidden.bs.modal", () => this._cleanup_realtime());

        // Nạp extra vars từ al_bom_vars hiện có (Table field chuẩn Frappe)
        this._populate_extra_vars();
        this._setup_extra_vars_autofill();

        // Load Variable Set → render vùng biến động (KHÔNG recreate dialog)
        // Mở dialog → giữ override đã lưu trong al_bom_vars (nếu có)
        this._load_variable_set().then(vars => {
            this._current_vars = vars;
            this._render_vars_container(vars);
            this._render_bom_info(true);
            // Nạp xong lần đầu — từ giờ mọi thay đổi (kính, biến, cấu hình...)
            // sẽ tự động lên lịch tính lại giá.
            setTimeout(() => { this._dialog_ready = true; }, 50);
        });

        setTimeout(() => this._render_preview_panel(), 300);
    }

    // ── Cập nhật thông tin sản phẩm khi đổi BOM ──
    // V6 Phase 1: các field cấu hình giờ EDITABLE — populate default từ BOM,
    // user đổi → override lưu vào al_bom_vars (Phase 4 engine đọc). Header
    // sản phẩm (ảnh + mã sp) render từ Item qua representative_item.
    // Khi mở dialog (preserveExisting=true) → ưu tiên override đã lưu trong
    // al_bom_vars; khi ĐỔI BOM → reset về default của BOM mới.
    _render_bom_info(preserveExisting) {
        if (!this.dialog) return;
        const m = this._bom_meta || null;
        const existing = preserveExisting ? this._parse_existing() : {};
        const set = (fieldname, value) => {
            const ctrl = this.dialog.fields_dict[fieldname];
            if (ctrl && ctrl.set_value) ctrl.set_value(value);
        };
        if (!m || !m.bom_code) {
            set("al_bom_name", existing._bom_name || "");
            set("al_bom_set", existing._bom_set || "");
            set("al_accessory_set", existing._accessory_set || "");
            set("al_profile_system", existing._profile_system || "");
            set("al_cost_template", existing._cost_template || "");
            set("al_brand", existing._brand || "");
            this._render_product_header(null);
            return;
        }
        // Editable fields — giá trị Link = code (autoname field:code nên name==code)
        set("al_bom_name", existing._bom_name || m.bom_name || "");
        set("al_bom_set", existing._bom_set || m.bom_set_code || m.bom_set || "");
        set("al_accessory_set", existing._accessory_set || m.accessory_set_code || "");
        set("al_profile_system", existing._profile_system || m.profile_system_code || "");
        set("al_cost_template", existing._cost_template || m.cost_template_code || m.cost_template || "");
        set("al_brand", existing._brand || m.brand || "");
        this._render_product_header(m);
    }

    // ── Header sản phẩm: ảnh + mã sp (A1) ──
    _render_product_header(m) {
        if (!this.dialog) return;
        const ctrl = this.dialog.fields_dict["product_header"];
        if (!ctrl) return;
        const has = m && (m.item_code || m.item_image || m.item_name);
        if (!has) {
            ctrl.set_value(`<div style="display:flex;align-items:center;gap:12px;padding:8px 0;color:#94a3b8;font-size:12.5px;">
                <span>🪟 ${__("Chưa chọn sản phẩm — chọn BOM để xem ảnh và mã sản phẩm")}</span>
            </div>`);
            return;
        }
        const img = m.item_image ? `<div style="flex-shrink:0;width:56px;height:56px;border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;background:#f8fafc;">
                <img src="${this._esc_html(m.item_image)}" style="width:100%;height:100%;object-fit:contain;" alt=""></div>` : "";
        const itemCode = m.item_code || "";
        const itemName = m.item_name || "";
        ctrl.set_value(`<div style="display:flex;align-items:center;gap:12px;padding:8px 0;">
            ${img}
            <div style="min-width:0;">
                <div style="font-weight:600;font-size:13px;color:#1e293b;">${this._esc_html(itemName) || "—"}</div>
                <div style="font-size:12px;color:#64748b;">${__("Mã sản phẩm")}: <strong>${this._esc_html(itemCode) || "—"}</strong></div>
            </div>
        </div>`);
    }

    // ── Auto-fill var_type (và options) khi chọn var_name từ Library ──
    _setup_extra_vars_autofill() {
        if (!this.dialog) return;
        const table_field = this.dialog.fields_dict["extra_vars"];
        if (!table_field || !table_field.grid) return;
        const grid = table_field.grid;

        const self = this;
        // Event delegation — bắt cả row mới thêm sau khi refresh
        $(grid.wrapper)
            .off("change.autofill awesomplete-selectcomplete.autofill", "[data-fieldname='var_name']")
            .on("change.autofill awesomplete-selectcomplete.autofill", "[data-fieldname='var_name']", function () {
                const $row = $(this).closest(".grid-row");
                const idx = parseInt($row.attr("data-idx") || "0", 10);
                if (!idx) return;
                const row_doc = (table_field.df.data || [])[idx - 1];
                if (!row_doc || !row_doc.var_name) return;

                frappe.db.get_value("AL Variable Library", row_doc.var_name,
                    ["var_type", "select_options", "link_doctype"], (r) => {
                        if (!r) return;
                        const grid_row = (grid.grid_rows || []).find(gr => gr.idx === idx);
                        const type_ctrl = grid_row && grid_row.fields_dict && grid_row.fields_dict.var_type;
                        if (type_ctrl && type_ctrl.set_value) {
                            type_ctrl.set_value(r.var_type || "Data");
                        } else {
                            row_doc.var_type = r.var_type || "Data";
                            if (grid.refresh_row) grid.refresh_row(idx);
                        }
                        // Lưu options phụ vào row (Select/Link dùng lại khi save/preview)
                        row_doc.select_options = r.select_options || "";
                        row_doc.link_doctype = r.link_doctype || "";
                        self._schedule_auto_preview();
                    });
            });

        // Auto-preview khi sửa bất kỳ ô nào trong bảng "Biến mở rộng"
        // (tên biến, kiểu, hoặc giá trị) — event delegation để bắt cả dòng
        // thêm sau. Không cần chờ blur ra khỏi bảng như trước.
        $(grid.wrapper)
            .off("change.al_autopreview awesomplete-selectcomplete.al_autopreview", ".grid-row [data-fieldname]")
            .on("change.al_autopreview awesomplete-selectcomplete.al_autopreview", ".grid-row [data-fieldname]", function () {
                self._schedule_auto_preview();
            });
    }

    // ── Map Variable Set item → Frappe form field ─────────────────
    // Q1b/V6 P10: Pricing Dimension KHÔNG required — user để trống → engine
    // bỏ qua dimension đó khi match giá composite. KHÔNG hardcode tên biến
    // nữa — đọc cờ `is_pricing_dimension` server trả về (từ AL Variable
    // Dimension Mapping, xem api/__init__.py get_bom_meta mục 2c). Áp dụng
    // như nhau cho dimension nhôm lẫn kính, không cần sửa file này khi thêm
    // dimension mới.
    _var_to_field(v, current_val) {
        const optional = !!v.is_pricing_dimension;
        const base = {
            fieldname: "al_var_" + v.var_name,
            label: __(v.var_label || v.var_name),
            default: current_val !== undefined ? current_val : v.default_value,
            reqd: optional ? 0 : (v.is_required || 0),
        };

        switch (v.var_type) {
            case "Float":
                return { ...base, fieldtype: "Float", precision: "1" };
            case "Int":
                return { ...base, fieldtype: "Int" };
            case "Data":
                return { ...base, fieldtype: "Data" };
            case "Select":
                // Q1b: select không bắt buộc → thêm option rỗng "" (bỏ trống được)
                return {
                    ...base,
                    fieldtype: "Select",
                    options: (base.reqd ? "" : "\n") + (v.select_options || ""),
                };
            case "Link":
                return { ...base, fieldtype: "Link", options: v.link_doctype || "" };
            case "Check":
                return { ...base, fieldtype: "Check" };
            case "Currency":
                return { ...base, fieldtype: "Currency" };
            default:
                return { ...base, fieldtype: "Data" };
        }
    }

    // ── Render vùng biến động vào HTML container (3 cột thoáng) ──
    _render_vars_container(vars) {
        const $container = this._vars_container();
        if (!$container.length) return;

        // Hủy controls cũ (khi đổi BOM → re-render)
        this._var_controls = [];
        this._glass_controls = [];
        $container.empty();

        const existing = this._parse_existing();
        // Q1a: API (DEV1) trả `glass_groups` = gom AL Bom Set line kính theo
        // mã đại diện `default_glass_master` → hiện N selector kính per rep.
        // Chưa có contract (glass_groups vắng) → giữ biến global `glass_master`
        // như cũ (backward-compat).
        const glassGroups = (this._bom_meta && Array.isArray(this._bom_meta.glass_groups))
            ? this._bom_meta.glass_groups : [];
        const hasGlassGroups = glassGroups.length > 0;
        let user_vars = (vars || []).filter(v => !v.is_system);
        if (hasGlassGroups) {
            user_vars = user_vars.filter(v => v.var_name !== "glass_master");
        }
        const sys_vars = (vars || []).filter(v => v.is_system);

        // Chưa có Variable Set / chưa chọn BOM → hướng dẫn (dùng bảng Biến mở rộng)
        if (!(vars && vars.length)) {
            const hasBom = !!this.child_doc.al_bom;
            $container.html(`<div style="padding:16px;text-align:center;color:#64748b;background:#f8fafc;border:1px dashed #d1d5db;border-radius:6px;">
                <p style="margin:0 0 4px;font-size:14px;">${hasBom ? __("BOM này chưa có Variable Set.") : __("Chọn BOM ở trên để bắt đầu")}</p>
                <p style="margin:0;font-size:12px;">${hasBom ? __("Dùng bảng 'Biến mở rộng' bên dưới để thêm tham số.") : __("Hệ thống sẽ tự động sinh form tham số từ Variable Set của BOM.")}</p>
            </div>`);
            return;
        }

        // ── Kính theo vị trí (glass_groups) — N selector Link → AL Glass Master ──
        // Mỗi nhóm = 1 mã đại diện (KINH_1, KINH_2...). Default = mã đại diện;
        // ưu tiên giá trị đã lưu trong glass_master_map, rồi glass_master global cũ.
        if (hasGlassGroups) {
            $container.append(`<div style="font-weight:600;color:#1e293b;font-size:12.5px;margin:4px 0 8px;">${__("Kính theo vị trí")}</div>`);
            const $grid = $('<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-gap:0 12px;margin-bottom:8px;"></div>');
            $container.append($grid);
            const glassMap = existing.glass_master_map || {};
            glassGroups.forEach(g => {
                const rep = g.rep || "";
                if (!rep) return;
                // V6 P11: KHÔNG fallback về `rep` khi rep chỉ là khoá tổng hợp theo slug
                // (g.is_real_master === false, BOM Set không cấu hình default_glass_master)
                // — rep dạng đó KHÔNG phải mã AL Glass Master hợp lệ. Chỉ dùng giá trị
                // đã lưu (glassMap), giá trị global cũ (existing.glass_master), hoặc
                // g.default (server chỉ điền khi rep là mã thật) — nếu không có gì thì
                // để trống, bắt buộc user tự chọn.
                const current = glassMap[rep] || existing.glass_master || g.default || "";
                const df = {
                    fieldname: "al_glass_" + String(rep).replace(/[^A-Za-z0-9_]/g, "_"),
                    fieldtype: "Link",
                    options: "AL Glass Master",
                    label: __(g.label || rep),
                    default: current,
                };
                const $cell = $('<div style="min-width:0;"></div>');
                $grid.append($cell);
                const ctrl = frappe.ui.form.make_control({ df, parent: $cell[0], only_input: false });
                ctrl.make_input();
                ctrl.refresh();
                if (current !== undefined && current !== null && current !== "") {
                    ctrl.set_value(current);
                }
                this._glass_controls.push({ rep, ctrl });
            });
        }

        // ── Biến đầu vào (user) — 3 cột ──
        if (user_vars.length) {
            $container.append(`<div style="font-weight:600;color:#1e293b;font-size:12.5px;margin:4px 0 8px;">${__("Biến đầu vào")}</div>`);
            const $grid = $('<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-gap:0 12px;margin-bottom:8px;"></div>');
            $container.append($grid);
            user_vars.forEach(v => {
                const val = existing[v.var_name] !== undefined ? existing[v.var_name] : v.default_value;
                const df = this._var_to_field(v, val);
                if (df) this._make_var_control($grid, v, df);
            });
        }

        // ── Biến hệ thống (hiển thị sau, cho phép chỉnh sửa) ──
        if (sys_vars.length) {
            $container.append(`<div style="font-weight:600;color:#1e293b;font-size:12.5px;margin:10px 0 8px;">${__("Biến hệ thống (tự động)")}</div>`);
            const $grid = $('<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-gap:0 12px;margin-bottom:8px;"></div>');
            $container.append($grid);
            sys_vars.forEach(v => {
                const val = existing[v.var_name] !== undefined ? existing[v.var_name] : v.default_value;
                const df = this._var_to_field(v, val);
                if (df) this._make_var_control($grid, v, df);
            });
            // Q1c/Q2: khôi phục mặc định biến hệ thống (profile/product type) —
            // set về default_value từ Variable Library; bỏ trống → engine dùng
            // giá trị resolve (profile system child table / product type).
            const self = this;
            const $reset = $(`<button class="btn btn-xs btn-default" style="margin-top:6px;">
                ↺ ${__("Khôi phục mặc định biến hệ thống")}</button>`);
            $reset.on("click", function () {
                sys_vars.forEach(v => {
                    const item = self._var_controls.find(c => c.var_name === v.var_name);
                    if (item && item.ctrl && item.ctrl.set_value) {
                        item.ctrl.set_value(v.default_value != null ? v.default_value : "");
                    }
                });
                frappe.show_alert({ message: __("Đã khôi phục mặc định biến hệ thống"), indicator: "green" });
            });
            $container.append($reset);
        }

        // Gắn auto-preview cho MỌI control vừa tạo ở trên (kính + biến).
        this._bind_auto_preview_listeners();
    }

    // ── Tạo 1 control biến động bằng make_control (pattern eupapp) ──
    _make_var_control($grid, v, df) {
        const $cell = $('<div style="min-width:0;"></div>');
        $grid.append($cell);

        const ctrl = frappe.ui.form.make_control({
            df: df,
            parent: $cell[0],
            only_input: false,
        });
        ctrl.make_input();
        ctrl.refresh();

        // Set giá trị hiện tại sau khi render
        const val = df.default;
        if (val !== undefined && val !== null && val !== "") {
            ctrl.set_value(val);
        }

        this._var_controls.push({ var_name: v.var_name, ctrl });
    }

    // ── Nạp extra_vars từ al_bom_vars hiện có vào Table field ──────
    _populate_extra_vars() {
        if (!this.dialog) return;
        const table_field = this.dialog.fields_dict["extra_vars"];
        if (!table_field) return;

        const existing = this._parse_existing();
        const extra = existing.extra_vars && typeof existing.extra_vars === "object"
            ? existing.extra_vars : {};

        const rows = Object.entries(extra).map(([key, val]) => ({
            var_name: key,
            var_type: this._guess_var_type(val),
            var_value: typeof val === "boolean" ? (val ? "1" : "0")
                : (val === undefined || val === null ? "" : String(val)),
        }));

        table_field.df.data = rows;
        if (table_field.grid) table_field.grid.refresh();
    }

    // ── Đoán kiểu biến mở rộng khi đọc lại từ al_bom_vars ─────────
    _guess_var_type(val) {
        if (typeof val === "boolean") return "Check";
        if (typeof val === "number") {
            return Number.isInteger(val) ? "Int" : "Float";
        }
        return "Data";
    }

    // ── Đổi BOM: re-render vùng biến trong dialog CŨ (không recreate) ──
    _on_bom_change() {
        const bom = this.dialog?.get_value("al_bom");
        if (!bom) return;
        // Tự động set version mới nhất
        frappe.db.get_value("AL BOM", bom, "current_version", r => {
            if (r?.current_version) this.dialog?.set_value("al_bom_version", r.current_version);
        });
        this.child_doc.al_bom = bom;
        // Chỉ re-render vùng biến + thông tin BOM — dialog giữ nguyên vị trí/kích thước,
        // không giật, không tạo dialog mới, không reset preview.
        // Đổi BOM → reset về default của BOM mới (bỏ override cũ cho dòng này)
        this._load_variable_set().then(vars => {
            this._current_vars = vars;
            this._render_vars_container(vars);
            this._render_bom_info(false);
            this._schedule_auto_preview();
        });
    }

    // ── HTML container chứa vùng biến động ─────────────────────────
    _vars_container() {
        if (!this.dialog) return $();
        const field = this.dialog.fields_dict["vars_container"];
        return field ? field.$wrapper : $();
    }

    // ═══════════════════════════════════════════════════════════════
    // Auto-preview khi đổi tham số (fix gap: dialog KHÔNG tự tính lại
    // giá khi đổi field — trước đây chỉ tính khi bấm nút "🖥️ Preview").
    // Gắn vào: control kính per-line (_glass_controls), control biến
    // (_var_controls), bảng biến mở rộng (extra_vars), field cấu hình
    // (BOM Version/Bom Set/Accessory Set/Profile System/Cost Template/
    // Hãng nhôm — xem onchange trong _build_dialog_fields) và _on_bom_change.
    // Debounce 700ms để tránh gọi server liên tục khi đang gõ số; `_preview_seq`
    // (dùng trong _run_preview/_exec_calculate_bom) đảm bảo kết quả preview CŨ
    // trả về SAU không đè lên kết quả MỚI hơn.
    // ═══════════════════════════════════════════════════════════════
    _schedule_auto_preview() {
        if (!this._dialog_ready || !this.dialog) return;
        this._mark_preview_stale();
        if (!this._debounced_auto_preview) {
            this._debounced_auto_preview = frappe.utils.debounce(() => {
                if (this.dialog) this._run_preview();
            }, 700);
        }
        this._debounced_auto_preview();
    }

    // Báo hiệu "đang chờ tính lại" ngay lập tức (trước khi debounce chạy) mà
    // KHÔNG xoá kết quả preview cũ đang hiển thị — tránh cảm giác dialog "đứng".
    _mark_preview_stale() {
        const $container = this._preview_container();
        if (!$container.length) return;
        if ($container.find(".al-preview-stale-badge").length) return;
        $container.prepend(`<div class="al-preview-stale-badge" style="margin-bottom:6px;padding:5px 8px;
            background:#fef9c3;border:1px solid #fde68a;border-radius:4px;font-size:11.5px;color:#854d0e;">
            ⏳ ${__("Tham số vừa đổi — đang tự động tính lại giá...")}</div>`);
    }

    // Gắn listener auto-preview cho TẤT CẢ control biến + kính hiện có.
    // Gọi lại mỗi lần _render_vars_container chạy (kể cả sau khi đổi BOM) vì
    // controls cũ đã bị huỷ và tạo lại từ đầu.
    _bind_auto_preview_listeners() {
        const self = this;
        const bind = (ctrl) => {
            if (!ctrl || !ctrl.$input) return;
            ctrl.$input
                .off("change.al_autopreview awesomplete-selectcomplete.al_autopreview")
                .on("change.al_autopreview awesomplete-selectcomplete.al_autopreview",
                    () => self._schedule_auto_preview());
        };
        this._var_controls.forEach(({ ctrl }) => bind(ctrl));
        this._glass_controls.forEach(({ ctrl }) => bind(ctrl));
    }

    // ── Preview Panel ──────────────────────────────────────────────
    _render_preview_panel() {
        const $container = this._preview_container();
        if (!$container.length) return;

        // Mở lại panel → đọc trạng thái đã lưu trên item, không gọi lại API
        const status = this.child_doc.al_calc_status;

        if (status === "Success" && this.child_doc.al_bom_result) {
            this._render_display_model($container, this.child_doc.name);
            return;
        }

        if (status === "Queued" || status === "Running") {
            const job_id = this.child_doc.al_calc_job_id;
            $container.html(this._preview_progress_html(
                __("BOM đang tính trong nền — kết quả sẽ hiện tự động khi xong...")
            ));
            if (job_id) this._listen_realtime(job_id, $container);
            return;
        }

        if (status === "Failed") {
            $container.html(this._preview_error_html(this.child_doc.al_calc_error || ""));
            return;
        }

        $container.html(`<div style="padding:12px;text-align:center;color:#94a3b8;background:#f8fafc;border:1px dashed #d1d5db;border-radius:6px;">
            <span style="font-size:13px;">🖥️ ${__("Nhấn nút 'Preview tính giá' để xem kết quả")}</span>
        </div>`);
    }

    // ── Realtime cho async BOM (lọc theo job_id) ───────────────────
    _listen_realtime(job_id, $container) {
        this._cleanup_realtime();
        const self = this;
        this._realtime_handler = function (data) {
            if (!data || data.job_id !== job_id) return;
            self._cleanup_realtime();
            if (!$container || !$container.length) $container = self._preview_container();

            if (data.status === "Success") {
                const result_json = data.result ? JSON.stringify(data.result) : null;
                if (self.child_doc.name) {
                    frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                        self.child_doc.name, "al_calc_status", "Success");
                    frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                        self.child_doc.name, "al_bom_result", result_json);
                }
                self.child_doc.al_calc_status = "Success";
                self.child_doc.al_bom_result = result_json;
                // A8: async xong → rate = al_gia_ban (chưa VAT)
                self._apply_rate((data.result?.cost_template || {}).GIA_BAN);
                self._render_display_model($container, self.child_doc.name);
                frappe.show_alert({ message: __("Tính giá xong"), indicator: "green" });
            } else {
                if (self.child_doc.name) {
                    frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                        self.child_doc.name, "al_calc_status", "Failed");
                }
                self.child_doc.al_calc_status = "Failed";
                self.child_doc.al_calc_error = data.error || "";
                $container.html(self._preview_error_html(data.error || ""));
            }
        };
        frappe.realtime.on("alumglass_bom_calc_done", this._realtime_handler);
    }

    _cleanup_realtime() {
        if (this._realtime_handler) {
            frappe.realtime.off("alumglass_bom_calc_done", this._realtime_handler);
            this._realtime_handler = null;
        }
    }

    _preview_container() {
        if (!this.dialog) return $();
        const field = this.dialog.fields_dict["preview_html"];
        return field ? field.$wrapper : $();
    }

    _preview_progress_html(message) {
        return `<div style="padding:20px;text-align:center;color:#64748b;">
            <i class="fa fa-spinner fa-spin" style="font-size:18px;color:#f59e0b;"></i>
            <p style="margin-top:10px;font-size:13px;">${message || __("Đang tính BOM trong nền...")}</p>
        </div>`;
    }

    _preview_error_html(error) {
        const safe_error = error ? this._esc_html(String(error)) : "";
        return `<div style="padding:12px;color:#ef4444;text-align:center;">
            ❌ ${__("Tính giá thất bại")}
            ${safe_error ? `<pre style="margin-top:8px;font-size:11px;max-height:200px;overflow:auto;text-align:left;">${safe_error}</pre>` : ""}
        </div>`;
    }

    _run_preview() {
        // Hiển thị trạng thái loading (thay luôn badge "đang chờ" nếu có)
        const $container = this._preview_container();
        if ($container.length) {
            $container.html(this._preview_progress_html(__("Đang tính toán...")));
            $container[0].scrollIntoView({ behavior: "smooth", block: "center" });
        }

        const self = this;
        // Lưu tham số vào model TRÊN TRÌNH DUYỆT trước (vars, glass_master_map...)
        this._save();

        // Nếu chưa có BOM, báo lỗi
        const bom = this.dialog?.get_value("al_bom") || this.child_doc.al_bom;
        if (!bom) {
            if ($container.length) {
                $container.html(this._preview_error_html(__("Vui lòng chọn BOM trước khi Preview")));
            }
            return;
        }

        const cdt = this.child_doc.doctype || "Quotation Item";
        const cdn = this.child_doc.name;
        // seq tăng mỗi lần gọi preview — nếu 1 preview cũ hơn trả về SAU 1
        // preview mới hơn (VD user đổi kính liên tục), kết quả cũ bị bỏ qua.
        const seq = ++this._preview_seq;

        // FIX GỐC: server đọc al_bom_vars/al_bom/al_bom_version từ DATABASE
        // (frappe.get_doc), không phải từ bộ nhớ trình duyệt — nên PHẢI đồng
        // bộ xuống DB trước khi gọi calculate_bom, nếu không kính/tham số vừa
        // đổi sẽ không được engine nhìn thấy (giá/nẹp không đổi).
        alumglass.quotation._sync_row_to_db(this.frm, cdt, cdn)
            .then((realName) => {
                if (seq !== self._preview_seq) return; // đã có preview mới hơn
                if (realName && realName !== self.child_doc.name) {
                    // Dòng mới vừa được lưu lần đầu → tên đã đổi, cập nhật lại tham chiếu
                    const newRow = frappe.get_doc(cdt, realName);
                    if (newRow) self.child_doc = newRow;
                }
                self._exec_calculate_bom($container, seq);
            })
            .catch((err) => {
                if (seq !== self._preview_seq) return;
                if ($container.length) {
                    $container.html(self._preview_error_html(
                        __("Không lưu được dữ liệu dòng trước khi tính giá") + ": "
                        + String((err && err.message) || err || "")));
                }
            });
    }

    // Gọi API calculate_bom SAU KHI dữ liệu dòng đã đồng bộ xuống DB.
    // Tách riêng để `_run_preview` giữ ngắn gọn + tái dùng seq-guard.
    _exec_calculate_bom($container, seq) {
        const self = this;
        if (!$container || !$container.length) $container = this._preview_container();

        frappe.call({
            method: "alumglass.api.calculate_bom",
            args: { quotation_item_name: this.child_doc.name },
            callback: (r) => {
                if (seq !== self._preview_seq) return; // stale — có preview mới hơn đã chạy
                if (!$container.length) return;
                if (r.message) {
                    if (r.message.async) {
                        // BOM lớn — job đã enqueue, chờ realtime event
                        $container.html(self._preview_progress_html(
                            r.message.message || __("Đang tính BOM lớn trong nền — có thể mất vài phút...")
                        ));
                        if (self.child_doc.name) {
                            frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                                self.child_doc.name, "al_calc_status", "Queued");
                            if (r.message.job_id) {
                                frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                                    self.child_doc.name, "al_calc_job_id", r.message.job_id);
                            }
                        }
                        self.child_doc.al_calc_status = "Queued";
                        self.child_doc.al_calc_job_id = r.message.job_id;
                        self._listen_realtime(r.message.job_id, $container);
                    } else {
                        // BOM nhỏ/vừa — kết quả trả về ngay (đã persist ở server B7)
                        self.child_doc.al_calc_status = "Success";
                        if (self.child_doc.name) {
                            frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                                self.child_doc.name, "al_calc_status", "Success");
                            frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                                self.child_doc.name, "al_bom_result", JSON.stringify(r.message));
                        }
                        self.child_doc.al_bom_result = JSON.stringify(r.message);
                        // A8: sau khi tính xong → rate = al_gia_ban (chưa VAT)
                        self._apply_rate((r.message.cost_template || {}).GIA_BAN);
                        self._render_display_model($container, self.child_doc.name);
                    }
                } else {
                    $container.html(self._preview_error_html(__("Không có kết quả. Kiểm tra lại tham số đầu vào.")));
                }
            },
            error: (err) => {
                if (seq !== self._preview_seq) return;
                if ($container.length) {
                    $container.html(self._preview_error_html(String(err || "")));
                }
            },
        });
    }

    // Render preview TỐI ƯU: lấy display model (label + công thức) từ server
    // rồi render qua `alumglass.render_bom_result_display` — renderer dùng chung.
    _render_display_model($container, qi_name) {
        const self = this;
        if (!$container || !$container.length) $container = this._preview_container();
        if (!$container.length) return;
        if (!qi_name) return;

        frappe.call({
            method: "alumglass.api.get_result_display",
            args: { quotation_item_name: qi_name },
            callback: (r) => {
                if (!$container || !$container.length) return;
                if (r.message && r.message.summary && r.message.summary.calculated) {
                    $container.html(alumglass.render_bom_result_display(r.message, {
                        compact: true, show_trace: false,
                    }));
                    return;
                }
                // Server trả display trống (chưa tính / chưa lưu) — fallback raw nếu có
                let raw = null;
                try { raw = JSON.parse(self.child_doc.al_bom_result || "{}"); } catch (e) { /* ignore */ }
                if (raw && (raw.lines || raw.cost_template)) {
                    $container.html(alumglass.render_bom_result_display(
                        alumglass.raw_to_display(raw), { compact: true, show_trace: false }));
                } else {
                    $container.html(self._preview_progress_html(__("Đang tải kết quả...")));
                }
            },
            error: (err) => {
                if ($container && $container.length) {
                    $container.html(self._preview_error_html(String(err || "")));
                }
            },
        });
    }

    // Fallback đồng bộ (giữ chân cho code cũ): render raw qua renderer dùng chung.
    _build_preview_html(data) {
        return alumglass.render_bom_result_display(
            alumglass.raw_to_display(data), { compact: true, show_trace: false });
    }

    // ── Parse existing al_bom_vars JSON ────────────────────────────
    _parse_existing() {
        try { return JSON.parse(this.child_doc.al_bom_vars || "{}"); } catch (e) { return {}; }
    }

    // ── Escape helper ─────────────────────────────────────────────
    _esc_html(str) {
        return String(str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    _save() {
        const vars = {};

        // ── Thu thập biến từ controls động (Variable Set) ─────────
        this._var_controls.forEach(({ var_name, ctrl }) => {
            let val = ctrl.get_value();
            if (val !== undefined && val !== null && val !== "") {
                vars[var_name] = val;
            }
        });

        // ── Glass per-line map (glass_groups) — Q1a ─────────────────
        // Lưu `glass_master_map: {rep: actual}` vào al_bom_vars. Backward-compat:
        // không có map → engine vẫn đọc `glass_master` global (nếu user đặt).
        if (this._glass_controls && this._glass_controls.length) {
            const glassMap = {};
            let anySet = false;
            this._glass_controls.forEach(({ rep, ctrl }) => {
                const v = ctrl.get_value();
                if (v !== undefined && v !== null && String(v).trim() !== "") {
                    glassMap[rep] = v;
                    anySet = true;
                }
            });
            if (anySet) vars.glass_master_map = glassMap;
        }

        // ── Thu thập extra vars từ Table field chuẩn Frappe ────────
        vars.extra_vars = {};
        const extra_rows = this.dialog ? (this.dialog.fields_dict["extra_vars"]?.df.data || []) : [];
        (extra_rows || []).forEach(row => {
            if (row.var_name && row.var_name.trim()) {
                let val = row.var_value;
                if (row.var_type === "Float" || row.var_type === "Int") {
                    val = parseFloat(val);
                    if (isNaN(val)) val = 0;
                } else if (row.var_type === "Check") {
                    val = val === "true" || val === "1" || val === true;
                }
                vars.extra_vars[row.var_name.trim()] = val;
            }
        });

        // ── Override cấu hình (V6 Phase 1: editable fields) ─────────
        // Lưu vào al_bom_vars dạng override keys để engine đọc (Phase 4).
        // Chỉ lưu khi user đổi khác default BOM — tránh nhiễu al_bom_vars.
        const dlg = this.dialog;
        if (dlg) {
            const over = this._collect_overrides();
            Object.keys(over).forEach(k => { vars[k] = over[k]; });
        }

        // ── Lưu vào Quotation Item ─────────────────────────────────
        const cdt = this.child_doc.doctype || "Quotation Item";
        const cdn = this.child_doc.name;
        if (cdn) {
            const bom = this.dialog?.get_value("al_bom");
            const version = this.dialog?.get_value("al_bom_version");

            // A8 (Phase 3): set item_code/item_name trên dòng từ representative_item
            // của BOM (mã sản phẩm thật). Chỉ ghi khi đã có BOM và khác giá trị hiện tại
            // (không clobber item do người dùng tự nhập nếu đã đúng).
            const m = this._bom_meta || null;
            if (bom && m && m.item_code) {
                if (this.child_doc.item_code !== m.item_code) {
                    frappe.model.set_value(cdt, cdn, "item_code", m.item_code);
                    this.child_doc.item_code = m.item_code;
                }
                if (m.item_name && this.child_doc.item_name !== m.item_name) {
                    frappe.model.set_value(cdt, cdn, "item_name", m.item_name);
                    this.child_doc.item_name = m.item_name;
                }
            }

            frappe.model.set_value(cdt, cdn, "al_bom_vars", JSON.stringify(vars, null, 2));
            if (bom) frappe.model.set_value(cdt, cdn, "al_bom", bom);
            if (version) frappe.model.set_value(cdt, cdn, "al_bom_version", version);
            // Cập nhật local child_doc để dialog dùng lại nếu cần
            this.child_doc.al_bom_vars = JSON.stringify(vars, null, 2);
            if (bom) this.child_doc.al_bom = bom;
            if (version) this.child_doc.al_bom_version = version;
        }
    }

    // ── A8 (Phase 3): set rate = al_gia_ban sau khi tính xong ───────
    // Gọi từ _run_preview / _listen_realtime / nút Tính giá form-level.
    _apply_rate(giaban) {
        const cdt = this.child_doc.doctype || "Quotation Item";
        const cdn = this.child_doc.name;
        const rate = Number(giaban);
        if (cdn && !isNaN(rate) && rate > 0) {
            frappe.model.set_value(cdt, cdn, "rate", rate);
            this.child_doc.rate = rate;
        }
    }

    // ── Override keys từ các field cấu hình editable (V6 Phase 1) ──
    // Chỉ ghi khi user đổi khác default (lấy từ _bom_meta) — engine Phase 4
    // đọc `_bom_set`/`_accessory_set`/`_profile_system`/`_cost_template`.
    _collect_overrides() {
        const out = {};
        const dlg = this.dialog;
        if (!dlg) return out;
        const m = this._bom_meta || null;

        const valOf = fieldname => dlg.get_value(fieldname);
        const defOf = fieldname => (m && m[fieldname] != null) ? m[fieldname] : "";

        const overrides = [
            ["_bom_set", "al_bom_set", "bom_set_code"],
            ["_accessory_set", "al_accessory_set", "accessory_set_code"],
            ["_profile_system", "al_profile_system", "profile_system_code"],
            ["_cost_template", "al_cost_template", "cost_template_code"],
            ["_bom_name", "al_bom_name", "bom_name"],
            ["_brand", "al_brand", "brand"],
        ];
        overrides.forEach(([key, fieldname, metaKey]) => {
            const v = valOf(fieldname);
            const def = defOf(metaKey);
            if (v !== undefined && v !== null && String(v).trim() !== "" && String(v) !== String(def || "")) {
                out[key] = v;
            }
        });
        return out;
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// BOMDialog — dialog kết quả tính giá BOM (tách từ public/js/bom_dialog.js)
// ═══════════════════════════════════════════════════════════════════════════
alumglass.BOMDialog = class BOMDialog {
    constructor(quotation_item_name) {
        this.quotation_item_name = quotation_item_name;
        this.dialog = null;
        this._realtime_handler = null;
    }

    show() {
        this.dialog = new frappe.ui.Dialog({
            title: __("BOM Calculation Result"),
            fields: [
                {
                    fieldname: "result_html",
                    fieldtype: "HTML",
                }
            ],
            size: "large",
            primary_action_label: __("Close"),
            primary_action: () => this.dialog.hide(),
        });

        // Cleanup listener khi dialog đóng (tránh leak realtime handler)
        $(this.dialog.$wrapper).on("hidden.bs.modal", () => this._cleanup_realtime());

        this._load_existing_state();
    }

    // ── Mở lại: đọc trạng thái đã lưu trên Quotation Item ───────────
    _load_existing_state() {
        const self = this;
        frappe.db.get_value("Quotation Item", this.quotation_item_name, [
            "al_calc_status", "al_calc_job_id", "al_bom_result", "al_calc_error",
        ], (r) => {
            if (r) {
                if (r.al_calc_status === "Success" && r.al_bom_result) {
                    // Kết quả đã lưu — render luôn, KHÔNG gọi lại API
                    let data = null;
                    try { data = JSON.parse(r.al_bom_result); } catch (e) { /* ignore */ }
                    if (data) { this.render_results(data); return; }
                }
                if (r.al_calc_status === "Queued" || r.al_calc_status === "Running") {
                    // Đang tính trong nền — không gọi lại, chỉ chờ realtime
                    this._show_async_progress(
                        r.al_calc_job_id,
                        __("BOM đang tính trong nền — kết quả sẽ hiện tự động khi xong...")
                    );
                    this._listen_realtime(r.al_calc_job_id);
                    return;
                }
                if (r.al_calc_status === "Failed") {
                    this._render_error(r.al_calc_error || "");
                    return;
                }
            }
            // Chưa có trạng thái (chưa tính) → gọi API như bình thường
            this.calculate();
        });
    }

    calculate() {
        const self = this;
        this._show_loading(__("Đang tính giá..."));

        frappe.call({
            method: "alumglass.api.calculate_bom",
            args: {
                quotation_item_name: this.quotation_item_name,
            },
            callback: (r) => {
                if (!r.message) {
                    self._render_error(__("Không có kết quả trả về."));
                    return;
                }
                if (r.message.async) {
                    // BOM lớn — job đã enqueue, chờ realtime event
                    self._show_async_progress(r.message.job_id, r.message.message);
                    self._listen_realtime(r.message.job_id);
                } else {
                    // BOM nhỏ/vừa — kết quả trả về ngay
                    self.render_results(r.message);
                }
            },
            error: (err) => {
                self._render_error(String(err || ""));
            },
        });
    }

    // ── Realtime: lắng nghe kết quả job async (lọc theo job_id) ─────
    _listen_realtime(job_id) {
        this._cleanup_realtime();
        const self = this;
        this._realtime_handler = function (data) {
            if (!data || data.job_id !== job_id) return;  // không phải job của dialog này
            self._cleanup_realtime();  // nhận kết quả → huỷ listener

            if (data.status === "Success") {
                frappe.show_alert({
                    message: __("Tính giá xong cho {0}", [self.quotation_item_name]),
                    indicator: "green",
                });
                self.render_results(data.result);
            } else {
                self._render_error(data.error || "");
            }
        };
        frappe.realtime.on("alumglass_bom_calc_done", this._realtime_handler);
    }

    _cleanup_realtime() {
        if (this._realtime_handler) {
            frappe.realtime.off("alumglass_bom_calc_done", this._realtime_handler);
            this._realtime_handler = null;
        }
    }

    // ── Loading / Async / Error states ──────────────────────────────
    _show_loading(message) {
        this._set_html(`<div class="text-center" style="padding:30px;">
            <i class="fa fa-spinner fa-spin" style="font-size:20px;color:#f59e0b;"></i>
            <p style="margin-top:10px;color:#64748b;">${message || __("Đang tính giá...")}</p>
        </div>`);
    }

    _show_async_progress(job_id, message) {
        this._set_html(`<div class="alert alert-info" style="margin-bottom:0;"
            data-job="${frappe.utils.escape_html(job_id || "")}">
            <i class="fa fa-spinner fa-spin"></i>
            ${message || __("Đang tính BOM lớn trong nền — có thể mất vài phút...")}
        </div>`);
    }

    _render_error(error) {
        const safe_error = error ? frappe.utils.escape_html(String(error)) : "";
        this._set_html(`<div class="alert alert-danger" style="margin-bottom:0;">
            <strong>${__("Tính giá thất bại")}</strong><br>
            ${__("Xem chi tiết trong Error Log hoặc trường AL Calc Error trên Quotation Item.")}
            ${safe_error ? `<pre style="margin-top:8px;font-size:11px;max-height:200px;overflow:auto;">${safe_error}</pre>` : ""}
        </div>`);
    }

    _set_html(html) {
        if (this.dialog) {
            this.dialog.set_value("result_html", html);
            this.dialog.show();
        }
    }

    // ── Render kết quả (sync hoặc async Success) ────────────────────
    // Lấy display model (label + công thức + trace) từ server rồi render
    // qua renderer DÙNG CHUNG `alumglass.render_bom_result_display` —
    // cùng renderer với ItemParamDialog (preview), không duplicate code.
    render_results(data) {
        const self = this;
        frappe.call({
            method: "alumglass.api.get_result_display",
            args: { quotation_item_name: this.quotation_item_name },
            callback: (r) => {
                if (r.message && r.message.summary && r.message.summary.calculated) {
                    self._set_html(alumglass.render_bom_result_display(r.message, {
                        collapsible: true,
                        show_trace: true,
                        title: __("BOM Calculation Results"),
                    }));
                    return;
                }
                // Server không có display (chưa lưu DB) → fallback raw data trong tay
                self._set_html(alumglass.render_bom_result_display(
                    alumglass.raw_to_display(data), {
                        collapsible: true,
                        show_trace: true,
                        title: __("BOM Calculation Results"),
                    }));
            },
            error: () => {
                // Lỗi mạng/API → vẫn render được bằng raw data (fallback)
                self._set_html(alumglass.render_bom_result_display(
                    alumglass.raw_to_display(data), {
                        collapsible: true,
                        show_trace: true,
                        title: __("BOM Calculation Results"),
                    }));
            },
        });
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// Form handlers — nút theo TỪNG DÒNG con Quotation Item (không nút toolbar)
// ═══════════════════════════════════════════════════════════════════════════
frappe.ui.form.on("Quotation", {
    refresh(frm) {
        // Row-level buttons + double-click (mỗi dòng mở dialog cho chính dòng đó)
        _attach_row_actions(frm);
        // Grid render rows SAU refresh → retry có kiểm soát để nút xuất hiện ngay
        // khi mở form có dòng sẵn (V5 — Owner: "phải add dòng/reload mới thấy nút").
        _schedule_row_actions_retry(frm);

        alumglass.grid_placeholder.set_column({ frm, parentfield: 'items' },
            'item_code', __('Chọn Asset Category'));

        // C1/C2 (Phase 3): 2 nút form-level — Tính giá toàn bộ + Preview giá toàn bộ
        _add_form_actions(frm);
    },

    after_save(frm) {
        setTimeout(() => _attach_row_actions(frm), 600);
    },
});

frappe.ui.form.on("Quotation Item", {
    // Dòng mới thêm → gắn nút hành động
    items_add(frm) {
        setTimeout(() => _attach_row_actions(frm), 200);
    },

    // Form con mở rộng của dòng → thêm nút "Tham số BOM" + "Preview tính giá"
    form_render(innerFrm, cdt, cdn) {
        // Chỉ xử lý trong context của form Quotation
        if (!innerFrm || innerFrm.doctype !== "Quotation") return;
        const row = frappe.get_doc("Quotation Item", cdn);
        if (!row) return;

        setTimeout(() => {
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
                    new alumglass.quotation.ItemParamDialog(innerFrm, row).show();
                });
                $formBtns.find(".al-btn-preview").on("click", function () {
                    if (!row.al_bom) {
                        frappe.msgprint(__("Chưa chọn BOM. Vui lòng mở Tham số BOM trước."));
                        return;
                    }
                    // Lưu vào model trình duyệt trước...
                    frappe.model.set_value(cdt, cdn, "al_bom_vars",
                        JSON.stringify(_collect_form_vars(innerFrm, cdn) || {}));
                    // ...rồi PHẢI đồng bộ xuống DB trước khi mở BOMDialog, vì
                    // calculate_bom đọc al_bom_vars từ DB (xem _sync_row_to_db).
                    frappe.dom.freeze(__("Đang đồng bộ dữ liệu..."));
                    alumglass.quotation._sync_row_to_db(innerFrm, cdt, cdn)
                        .then((realName) => {
                            frappe.dom.unfreeze();
                            new alumglass.BOMDialog(realName).show();
                        })
                        .catch((err) => {
                            frappe.dom.unfreeze();
                            frappe.msgprint({
                                title: __("Lỗi đồng bộ dữ liệu"),
                                message: String((err && err.message) || err || ""),
                                indicator: "red",
                            });
                        });
                });
                gridBody.prepend($formBtns);
            }
        }, 400);
    },
});

// ── Retry attach row actions (grid render xong mới có .grid-row) ─────
// V5: mở form có dòng sẵn → refresh chạy trước khi grid render rows → nút chưa gắn.
// Retry ~0.5s tối đa 10 lần (~5s) rồi dừng; `_attach_row_actions` idempotent
// (guard `data("_al_btn")` + `.al-row-actions`) nên gọi lặp an toàn, không nhân đôi nút.
let _alRowActionsTimer = null;
function _schedule_row_actions_retry(frm, maxAttempts = 10) {
    if (_alRowActionsTimer) {
        clearInterval(_alRowActionsTimer);
        _alRowActionsTimer = null;
    }
    const grid = frm.fields_dict["items"]?.grid;
    if (!grid) return;

    let attempts = 0;
    const deadline = Date.now() + maxAttempts * 500;
    _alRowActionsTimer = setInterval(() => {
        attempts += 1;
        _attach_row_actions(frm);

        // Dừng sớm khi mọi row đã gắn nút (guard idempotent đã chống nhân đôi)
        const $grid = grid.wrapper ? $(grid.wrapper) : $(grid.$wrapper);
        const rows = $grid.find(".grid-row");
        const attached = rows.filter((i, el) => $(el).find(".al-row-actions").length).length;
        const allAttached = rows.length && attached === rows.length;

        if (allAttached || attempts >= maxAttempts || Date.now() >= deadline) {
            clearInterval(_alRowActionsTimer);
            _alRowActionsTimer = null;
        }
    }, 500);
}

// ── Gắn button + double-click cho từng dòng trong bảng Items ────────
function _attach_row_actions(frm) {
    const grid = frm.fields_dict["items"]?.grid;
    if (!grid) return;

    // Dùng grid.wrapper để bắt cả row render sau
    const $grid = grid.wrapper ? $(grid.wrapper) : $(grid.$wrapper);
    if (!$grid.length) return;

    $grid.find(".grid-row").each(function () {
        const $row = $(this);
        if ($row.data("_al_btn")) return;
        $row.data("_al_btn", true);

        // Nhóm 2 nút 📐 (tham số BOM) + 🖥️ (Preview tính giá) ở GÓC PHẢI cell item_code —
        // hiển thị THƯỜNG TRỰC ngoài form, user bấm ngay không cần mở rộng dòng.
        // Cell item_code thành flex → text trái, nút bên phải (giống row action buttons).
        const $itemCell = $row.find('.grid-static-col[data-fieldname="item_code"]');
        const $targetCell = $itemCell.length ? $itemCell : $row.find(".grid-static-col:first");
        if ($targetCell.length && !$targetCell.find(".al-row-actions").length) {
            const $actions = $(`<span class="al-row-actions" style="display:inline-flex;align-items:center;gap:2px;white-space:nowrap;flex-shrink:0;">
                <button class="al-row-params btn btn-xs btn-default"
                    title="${__("Mở tham số BOM")}"
                    style="padding:0 4px;font-size:11px;line-height:18px;">📐</button>
                <button class="al-row-preview btn btn-xs btn-default"
                    title="${__("Preview tính giá")}"
                    style="padding:0 4px;font-size:11px;line-height:18px;">🖥️</button>
            </span>`);
            $actions.find(".al-row-params").on("click", function (e) {
                e.stopPropagation();
                e.preventDefault();
                const rowDoc = _get_row_doc(frm, $row);
                if (rowDoc) new alumglass.quotation.ItemParamDialog(frm, rowDoc).show();
            });
            $actions.find(".al-row-preview").on("click", function (e) {
                e.stopPropagation();
                e.preventDefault();
                const rowDoc = _get_row_doc(frm, $row);
                if (!rowDoc) return;
                if (!rowDoc.al_bom) {
                    frappe.msgprint(__("Chưa chọn BOM. Vui lòng mở 📐 Tham số BOM trước."));
                    return;
                }
                // Đồng bộ trạng thái hiện tại (có thể còn thay đổi chưa lưu từ
                // dialog tham số) xuống DB trước khi mở BOMDialog — calculate_bom
                // đọc dữ liệu từ DB, không phải từ bộ nhớ trình duyệt.
                frappe.dom.freeze(__("Đang đồng bộ dữ liệu..."));
                alumglass.quotation._sync_row_to_db(frm, "Quotation Item", rowDoc.name)
                    .then((realName) => {
                        frappe.dom.unfreeze();
                        new alumglass.BOMDialog(realName).show();
                    })
                    .catch((err) => {
                        frappe.dom.unfreeze();
                        frappe.msgprint({
                            title: __("Lỗi đồng bộ dữ liệu"),
                            message: String((err && err.message) || err || ""),
                            indicator: "red",
                        });
                    });
            });
            // Text (static_area) co dãn đẩy nút về góc phải; khi row mở rộng (editable)
            // field_area cũng chiếm phần còn lại — nút luôn nằm góc phải cell item_code.
            $targetCell.css("display", "flex").css("align-items", "center").css("gap", "4px");
            $targetCell.find(".static-area, .field-area").css("flex", "1 1 0").css("min-width", "0");
            $targetCell.append($actions);
        }

        // Double-click để mở dialog
        $row.off("dblclick.alumglass").on("dblclick.alumglass", function () {
            const rowDoc = _get_row_doc(frm, $row);
            if (rowDoc) new alumglass.quotation.ItemParamDialog(frm, rowDoc).show();
        });
    });
}

// ── Lấy doc của row từ grid row element ────────────────────────────
function _get_row_doc(frm, $row) {
    const cdn = $row.attr("data-name");
    if (!cdn) return null;
    const rows = frm.doc?.items || [];
    return rows.find(r => r.name === cdn) || null;
}

// ── Thu thập giá trị form từ grid form con ──────────────────────────
function _collect_form_vars(frm, cdn) {
    const row = frappe.get_doc("Quotation Item", cdn);
    if (!row) return {};
    // Merge với al_bom_vars hiện có
    let vars = {};
    try { vars = JSON.parse(row.al_bom_vars || "{}"); } catch (e) {}
    // Giữ nguyên vars, chỉ đảm bảo BOM version đúng
    if (row.al_bom && !vars._bom) vars._bom = row.al_bom;
    return vars;
}

// ═══════════════════════════════════════════════════════════════════════════
// C1/C2 (V6 Phase 3) — nút form-level: "Tính giá" + "Preview giá" toàn bộ
// ═══════════════════════════════════════════════════════════════════════════
function _add_form_actions(frm) {
    if (!frm || frm.doctype !== "Quotation") return;
    if (!frm.fields_dict || !frm.fields_dict.items) return;
    // add_custom_button tự dedupe theo label (cả group path) → gọi lặp mỗi refresh an toàn
    frm.add_custom_button(__("Tính giá"), function () { _calc_all_items(frm); }, __("AlumGlass"));
    frm.add_custom_button(__("Preview giá"), function () { _preview_all_items(frm); }, __("AlumGlass"));
}

// ── C1 — Tính giá toàn bộ: validate + tính từng dòng + cập nhật rate ──
function _calc_all_items(frm) {
    const rows = (frm.doc.items || []).filter(r => !r.is_new);
    if (!rows.length) {
        frappe.msgprint(__("Chưa có dòng sản phẩm nào."));
        return;
    }

    // Validate từng dòng — báo rõ dòng nào thiếu gì
    const problems = [];
    rows.forEach((row, i) => {
        const missing = [];
        if (!row.al_bom) missing.push(__("chưa chọn BOM"));
        if (!row.al_bom_version) missing.push(__("chưa chọn BOM Version"));
        if (!row.al_bom_vars) missing.push(__("chưa nhập tham số (mở Tham số BOM và bấm Lưu)"));
        if (missing.length) {
            problems.push(`${__("Dòng {0}", [i + 1])} (${row.item_code || row.item_name || row.name || ""}): ${missing.join(", ")}`);
        }
    });
    if (problems.length) {
        frappe.msgprint({
            title: __("Chưa thể tính giá — thiếu thông tin"),
            message: `<ul style="padding-left:18px;margin:0;">${problems.map(p => `<li>${alumglass.esc(p)}</li>`).join("")}</ul>`,
            indicator: "orange",
        });
        return;
    }

    let done = 0, queued = 0, failed = 0;
    const total = rows.length;
    const finish = () => {
        frm.refresh_field("items");
        let msg = __("Đã tính {0}/{1} dòng", [done, total]);
        if (queued) msg += ` · ${__("{0} dòng chờ nền", [queued])}`;
        if (failed) msg += ` · ${__("{0} dòng lỗi", [failed])}`;
        frappe.show_alert({ message: msg, indicator: failed ? "red" : (queued ? "orange" : "green") });
    };
    const next = (i) => {
        if (i >= rows.length) { finish(); return; }
        const row = rows[i];
        // Đồng bộ dữ liệu dòng (al_bom_vars/al_bom/al_bom_version — có thể vừa
        // đổi trong dialog nhưng form chưa Ctrl+S) xuống DB trước khi tính,
        // vì calculate_bom đọc dữ liệu từ DB chứ không phải bộ nhớ trình duyệt.
        alumglass.quotation._sync_row_to_db(frm, "Quotation Item", row.name)
            .then((realName) => {
                frappe.call({
                    method: "alumglass.api.calculate_bom",
                    args: { quotation_item_name: realName },
                    callback: (r) => {
                        if (!r.message) { failed++; next(i + 1); return; }
                        if (r.message.async) {
                            queued++;
                            frappe.model.set_value("Quotation Item", realName, "al_calc_status", "Queued");
                            if (r.message.job_id) {
                                frappe.model.set_value("Quotation Item", realName, "al_calc_job_id", r.message.job_id);
                            }
                            next(i + 1);
                            return;
                        }
                        done++;
                        const ct = r.message.cost_template || {};
                        frappe.model.set_value("Quotation Item", realName, {
                            al_calc_status: "Success",
                            al_bom_result: JSON.stringify(r.message),
                            al_gia_ban: ct.GIA_BAN || 0,
                            al_gia_vat: ct.GIA_VAT || 0,   // response không có gia_vat top-level
                            rate: ct.GIA_BAN || 0,          // A8: rate = al_gia_ban (chưa VAT)
                        });
                        next(i + 1);
                    },
                    error: (err) => {
                        failed++;
                        frappe.model.set_value("Quotation Item", realName, {
                            al_calc_status: "Failed",
                            al_calc_error: String(err || ""),
                        });
                        next(i + 1);
                    },
                });
            })
            .catch((err) => {
                failed++;
                frappe.model.set_value("Quotation Item", row.name, {
                    al_calc_status: "Failed",
                    al_calc_error: String((err && err.message) || err || ""),
                });
                next(i + 1);
            });
    };
    frappe.show_alert({ message: __("Đang tính giá {0} dòng...", [total]), indicator: "orange" });
    next(0);
}

// ── C2 — Preview giá toàn bộ: dialog 90vw, từng sản phẩm + collapsible ──
function _preview_all_items(frm) {
    const rows = (frm.doc.items || []).filter(r => !r.is_new);
    if (!rows.length) {
        frappe.msgprint(__("Chưa có dòng sản phẩm nào."));
        return;
    }
    const dlg = new frappe.ui.Dialog({
        title: __("Preview giá toàn bộ sản phẩm"),
        fields: [{ fieldname: "pv_all_html", fieldtype: "HTML", label: "" }],
        size: "large",
        primary_action_label: __("Đóng"),
        primary_action: () => dlg.hide(),
    });
    dlg.$wrapper.find(".modal-dialog").css("max-width", "90vw");
    dlg.show();
    const $c = dlg.fields_dict["pv_all_html"].$wrapper;

    // Bảng tổng hợp: Mã sp, tên sp, số lượng, đơn giá, thành tiền
    let sum = `<table class="table table-condensed table-bordered" style="font-size:12px;margin-bottom:12px;">
        <thead style="background:#f1f5f9;"><tr>
            <th>#</th><th>${__("Mã sp")}</th><th>${__("Tên sp")}</th>
            <th class="text-right">${__("Số lượng")}</th>
            <th class="text-right">${__("Đơn giá")}</th>
            <th class="text-right">${__("Thành tiền")}</th>
        </tr></thead><tbody>`;
    rows.forEach((row, i) => {
        const rate = row.rate || 0;
        const qty = row.qty || 0;
        sum += `<tr>
            <td>${i + 1}</td>
            <td>${alumglass.esc(row.item_code)}</td>
            <td>${alumglass.esc(row.item_name)}</td>
            <td class="text-right">${format_number(qty)}</td>
            <td class="text-right">${format_currency(rate)}</td>
            <td class="text-right"><strong>${format_currency(qty * rate)}</strong></td>
        </tr>`;
    });
    sum += `</tbody></table>`;

    // Từng sản phẩm — collapsible chi tiết tính toán (renderer dùng chung)
    let details = `<div>`;
    rows.forEach((row, i) => {
        details += `<details class="al-pv-item" data-name="${row.name}" style="margin:6px 0;">
            <summary style="cursor:pointer;font-weight:600;padding:6px 8px;background:#f1f5f9;border-radius:4px;font-size:12px;color:#1e293b;">
                ${i + 1}. ${alumglass.esc(row.item_name || row.item_code || row.name)}
                ${row.item_code ? `<span style="color:#94a3b8;font-weight:400;">(${alumglass.esc(row.item_code)})</span>` : ""}
                <span class="al-pv-status" style="float:right;color:#94a3b8;font-weight:400;">${__("Đang tải...")}</span>
            </summary>
            <div class="al-pv-body" style="padding:6px 4px;">${__("Đang tải chi tiết...")}</div>
        </details>`;
    });
    details += `</div>`;
    $c.html(sum + details);

    // Nạp chi tiết từng sản phẩm (async, không chặn UI)
    rows.forEach((row) => {
        frappe.call({
            method: "alumglass.api.get_result_display",
            args: { quotation_item_name: row.name },
            callback: (r) => {
                const $det = $(`.al-pv-item[data-name="${row.name}"]`);
                if (!$det.length) return;
                if (r.message && r.message.summary && r.message.summary.calculated) {
                    $det.find(".al-pv-status").text(__("Đã tính"));
                    $det.find(".al-pv-body").html(alumglass.render_bom_result_display(r.message, {
                        collapsible: true,
                        show_trace: false,
                        compact: true,
                    }));
                } else {
                    $det.find(".al-pv-status").text(__("Chưa tính giá"));
                    $det.find(".al-pv-body").html(
                        `<p class="text-muted" style="margin:8px 0;">${__("Chưa tính giá cho sản phẩm này — bấm nút Tính giá hoặc mở Tham số BOM để tính.")}</p>`
                    );
                }
            },
            error: () => {
                const $det = $(`.al-pv-item[data-name="${row.name}"]`);
                if ($det.length) {
                    $det.find(".al-pv-status").text(__("Lỗi"));
                    $det.find(".al-pv-body").html(`<p class="text-muted" style="margin:8px 0;">${__("Không tải được chi tiết.")}</p>`);
                }
            },
        });
    });
}