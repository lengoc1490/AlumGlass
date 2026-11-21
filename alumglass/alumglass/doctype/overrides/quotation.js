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
// Hiển thị SỐ ĐO (Rộng/Cao) — thống nhất với cột Trọng lượng
// ─────────────────────────────────────────────────────────────────────────
// Rộng/Cao = 0 nghĩa là dòng vật tư KHÔNG khai số đo (nẹp, phụ kiện, keo...),
// không phải "kích thước bằng 0 mm". In "0" ra màn hình khiến người đọc báo
// giá tưởng đó là số đo thật. Vì vậy 0 bị coi như "chưa có" → "—", đúng như
// cột Trọng lượng đang làm (`weight_per_unit > 0` mới in số).
//   undefined / null / "" / "   " / 0 / "0" / "0.0" / NaN / "abc"  →  "—"
//   còn lại                                                        →  format_number()
// Hàm THUẦN (không đụng DOM) nên test được bằng Node:
//   node alumglass/tests/js/test_quotation_display.js
alumglass.fmt_dimension = function (value) {
    if (value === undefined || value === null) return "—";
    const s = String(value).trim();
    if (s === "") return "—";
    const n = Number(s);
    // NaN/Infinity hoặc 0 → coi như chưa khai số đo (⛔ không in "NaN"/"0")
    if (!isFinite(n) || n === 0) return "—";
    return format_number(n);
};

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
//   quotation_item : tên dòng Quotation Item đang xem — có giá trị thì mỗi
//                    dòng vật tư hiện nút "Vì sao ra số này?" (bấm mở dialog
//                    giải thích 6 bước); không có thì ẩn nút, không lỗi.
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
        // Q2: chỉ thêm 5 cột mới (Màu sắc/Nơi cấp vật tư/Vị trí lắp đặt/Góc
        // cắt/Ghi chú) khi có ít nhất 1 dòng thực sự dùng — giữ bảng gọn cho
        // BOM cũ/đơn giản chưa khai báo các trường này.
        const hasMeta = lines.some(function (ln) {
            return ln.color || ln.supplier_location || ln.install_position || ln.cut_angle || ln.note;
        });
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
                ${hasMeta ? `
                <th>${__("Màu sắc")}</th>
                <th>${__("Nơi cấp vật tư")}</th>
                <th>${__("Vị trí lắp đặt")}</th>
                <th class="text-center">${__("Góc cắt")}</th>
                <th>${__("Ghi chú")}</th>` : ""}
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
            // Nút "Vì sao ra số này?" — icon `?` nhỏ, không chiếm chỗ. Nội dung
            // căn cứ CHỈ sống trong dialog (một bề mặt duy nhất), ⛔ không lặp
            // khối "Căn cứ" inline trên từng dòng.
            // Dữ liệu dòng truyền qua `data-*`, không nhét JSON vào attribute.
            const explainBtn = (opts.quotation_item && ln.item_code && ln.slug)
                ? `<button type="button" class="btn btn-xs btn-default al-bom-explain-btn"
                        style="font-size:16px;line-height:1;padding:0 4px;margin-left:6px;vertical-align:middle;color:#94a3b8;border:none;background:transparent;"
                        title="${alumglass.esc(__("Vì sao ra số này?"))}"
                        aria-label="${alumglass.esc(__("Vì sao ra số này?"))}"
                        data-quotation-item="${alumglass.esc(opts.quotation_item)}"
                        data-slug="${alumglass.esc(ln.slug)}"
                        data-item-code="${alumglass.esc(ln.item_code)}"
                        data-label="${alumglass.esc(ln.label || ln.item_code)}">?</button>`
                : "";
            body += `<tr>
                <td style="color:#64748b;white-space:nowrap;">${alumglass.esc(ln.item_code || ln.slug)}</td>
                <td><strong>${alumglass.esc(ln.label || ln.item_code)}</strong>${explainBtn}${lineTrace}</td>
                <td class="text-center">${alumglass.fmt_dimension(ln.width)}</td>
                <td class="text-center">${alumglass.fmt_dimension(ln.height)}</td>
                <td class="text-center">${format_number(qty)}${ln.unit_qty ? ` <span style="color:#94a3b8;">(${format_number(ln.unit_qty)}/đv)</span>` : ""}</td>
                <td class="text-center">${weightHtml}</td>
                <td class="text-center">${format_number(totalQty)}</td>
                <td class="text-center">${unit}</td>
                <td class="text-right">${format_currency(ln.unit_price || 0)}</td>
                <td class="text-right"><strong>${format_currency(ln.line_total || 0)}</strong></td>
                <td style="font-size:10px;color:#64748b;">${alumglass.esc(ln.bucket_name || ln.cost_bucket || "")}</td>
                ${hasMeta ? `
                <td style="white-space:nowrap;">${ln.color ? alumglass.esc(ln.color) : "—"}</td>
                <td style="font-size:11px;">${ln.supplier_location ? alumglass.esc(ln.supplier_location) : "—"}</td>
                <td style="font-size:11px;">${ln.install_position ? alumglass.esc(ln.install_position) : "—"}</td>
                <td class="text-center">${ln.cut_angle ? alumglass.esc(ln.cut_angle) : "—"}</td>
                <td style="font-size:11px;color:#64748b;">${ln.note ? alumglass.esc(ln.note) : "—"}</td>` : ""}
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

// ═══════════════════════════════════════════════════════════════════════════
// "Vì sao ra số này?" — giải thích 1 dòng vật tư bằng ngôn ngữ người dùng
// ─────────────────────────────────────────────────────────────────────────
// Nút nhỏ cạnh tên vật tư (render trong bảng "Chi tiết vật tư" ở trên).
// Bấm → dialog gọi server lấy chuỗi bước: chọn mã vật tư → ... → thành tiền.
//
// Nguyên tắc hiển thị (bar User Delight):
//   - ⛔ không phơi tên hàm/API, mã lỗi, stack ra màn hình
//   - lỗi mạng/API → 1 câu đơn giản + nút "Thử lại"
//   - bước thiếu dữ liệu → nhãn xám "Chưa lưu dữ liệu cho bước này"
//   - luôn có lối thoát: nút "Đóng" + nút X chuẩn của Frappe
// ═══════════════════════════════════════════════════════════════════════════
alumglass.explain_bom_line_dialog = function (opts) {
    opts = opts || {};
    const quotation_item = opts.quotation_item || "";
    const slug = opts.slug || "";
    // Thiếu dữ liệu định danh dòng → không mở dialog (nút đã ẩn ở renderer,
    // đây là chốt chặn thứ hai).
    if (!quotation_item || !slug) return;

    // B3 — slug là khoá kỹ thuật: dùng làm tiêu đề khi thiếu nhãn sẽ phơi
    // `kinh_tren` cho người dùng. Thiếu hết thì gọi chung "dòng vật tư".
    const titleName = opts.label || opts.item_code || __("dòng vật tư");
    const dlg = new frappe.ui.Dialog({
        title: __("Vì sao ra số này? — {0}", [titleName]),
        size: "large",
        fields: [{ fieldtype: "HTML", fieldname: "explain_area" }],
        primary_action_label: __("Đóng"),
        primary_action: function () { dlg.hide(); },
    });

    const $area = () => {
        const field = dlg.fields_dict && dlg.fields_dict.explain_area;
        return field ? field.$wrapper : $();
    };
    const setArea = (html) => { $area().html(html); };

    function showLoading() {
        setArea(`<div style="padding:24px 12px;text-align:center;color:#64748b;">
            <i class="fa fa-spinner fa-spin" style="font-size:18px;color:#f59e0b;"></i>
            <p style="margin-top:10px;font-size:13px;">${__("Đang lấy căn cứ…")}</p>
        </div>`);
    }

    // Lỗi mạng/API: câu đơn giản + hành động "Thử lại" (không phơi exception).
    function showRetryableError() {
        setArea(`<div style="padding:16px 12px;text-align:center;">
            <p style="color:#b45309;font-size:13px;margin-bottom:12px;">${__("Chưa lấy được căn cứ cho dòng này. Thử lại sau.")}</p>
            <button type="button" class="btn btn-sm btn-default al-bom-explain-retry">${__("Thử lại")}</button>
        </div>`);
        $area().find(".al-bom-explain-retry").on("click", function () {
            showLoading();
            load();
        });
    }

    // B8 — lỗi quyền KHÔNG phải lỗi mạng: câu riêng, không nút "Thử lại"
    // (bấm lại cũng bị chặn), ⛔ không in `r.exc`.
    function showPermissionError() {
        setArea(`<div style="padding:16px 12px;text-align:center;">
            <p style="color:#b45309;font-size:13px;margin:0;">${__("Bạn không có quyền xem dòng này của báo giá. Liên hệ quản trị viên.")}</p>
        </div>`);
    }

    // Server trả lời nhưng dòng không còn dữ liệu → nói trạng thái, không hứa
    // "thử lại" (bấm lại cũng không khác gì).
    function showNoData(message) {
        setArea(`<div style="padding:16px 12px;text-align:center;">
            <p class="text-muted" style="margin:0;font-size:13px;">${alumglass.esc(message || __("Dòng này chưa có dữ liệu căn cứ để giải thích."))}</p>
        </div>`);
    }

    function showResult(msg) {
        const steps = Array.isArray(msg.steps) ? msg.steps : [];
        const missing = Array.isArray(msg.missing) ? msg.missing : [];
        // `missing` có thể là số bước, khoá, hoặc object {step|key} → gom hết
        // về 1 tập chuỗi để so khớp an toàn.
        const missingSet = {};
        missing.forEach(function (m) {
            if (m && typeof m === "object") {
                if (m.step !== undefined && m.step !== null) missingSet[String(m.step)] = true;
                if (m.key !== undefined && m.key !== null) missingSet[String(m.key)] = true;
            } else if (m !== undefined && m !== null) {
                missingSet[String(m)] = true;
            }
        });
        const stepMissing = function (s) {
            if (!s) return false;
            if (s.step !== undefined && s.step !== null && missingSet[String(s.step)]) return true;
            if (s.key !== undefined && s.key !== null && missingSet[String(s.key)]) return true;
            return false;
        };

        let html = `<div style="max-height:60vh;overflow:auto;padding:2px 2px 0;">`;
        // Tên vật tư đã nằm ở TIÊU ĐỀ dialog + footer "Mã vật tư" — ⛔ không
        // lặp lần thứ ba ở đầu thân.
        // Thành tiền = 0 vì THIẾU GIÁ (engine tạm tính 0 đ) — khác hẳn "0 vì
        // chưa có số lượng". Con số 0 trên màn hình trông y số thật, nên phải
        // chặn ở tầng cao nhất: banner đậm hơn `hint`, đặt TRÊN CÙNG.
        // Chỉ đọc cờ server (`warn_zero_price`), ⛔ không tự suy từ chuỗi.
        if (msg.warn_zero_price) {
            html += `<p style="margin:0 0 12px;padding:10px 12px;background:#fef2f2;border:1px solid #fca5a5;
                border-left:4px solid #b45309;border-radius:4px;color:#991b1b;font-weight:600;font-size:13px;">
                ⚠ ${alumglass.esc(__("Dòng này đang thiếu giá — đừng chốt báo giá."))}</p>`;
        }
        // B7 — báo giá tính trước bản vá: 1 dòng hướng dẫn ở đầu, không lặp
        // theo từng bước.
        if (msg.hint) {
            html += `<p style="margin:0 0 12px;padding:8px 10px;background:#fffbeb;border:1px solid #fde68a;
                border-radius:4px;color:#92400e;font-size:12px;">${alumglass.esc(msg.hint)}</p>`;
        }
        if (!steps.length) {
            html += `<p class="text-muted" style="font-size:13px;">${__("Chưa có dữ liệu căn cứ cho dòng này.")}</p>`;
        } else {
            html += `<ol style="list-style:none;margin:0;padding:0;">`;
            steps.forEach(function (s, i) {
                const num = (s && s.step !== undefined && s.step !== null) ? s.step : (i + 1);
                const title = alumglass.esc((s && s.title) || "");
                const detail = (s && s.detail) ? alumglass.esc(s.detail) : "";
                const miss = stepMissing(s);
                // `severity: "warning"` = có số liệu nhưng CHƯA ĐÚNG (vd tạm
                // tính 0 đ) — khác `missing` (chưa lưu dữ liệu, tô xám). Tô
                // hổ phách + tiền tố ⚠ để người dùng không đọc nhầm là số thật.
                const isWarn = !!(s && s.severity === "warning");
                const titleColor = isWarn ? "#b45309" : "#1e293b";
                const detailHtml = miss
                    ? `<div style="color:#94a3b8;font-size:12px;margin-top:2px;">${detail ? detail : __("Chưa lưu dữ liệu cho bước này")}</div>`
                    : (detail
                        ? (isWarn
                            ? `<div style="color:#b45309;font-size:12px;margin-top:2px;white-space:pre-wrap;word-break:break-word;background:#fffbeb;border:1px solid #fde68a;border-radius:4px;padding:4px 6px;">⚠ ${detail}</div>`
                            : `<div style="color:#475569;font-size:12px;margin-top:2px;white-space:pre-wrap;word-break:break-word;">${detail}</div>`)
                        : "");
                html += `<li style="margin-bottom:12px;padding-left:4px;">
                    <div style="font-weight:600;color:${titleColor};font-size:13px;">${alumglass.esc(num)}. ${title}</div>
                    ${detailHtml}
                </li>`;
            });
            html += `</ol>`;
        }
        html += `<div style="margin-top:14px;padding:10px 12px;background:#f8fafc;border-top:1px solid #e2e8f0;
                display:flex;gap:16px;flex-wrap:wrap;justify-content:space-between;">
            <span style="font-size:13px;"><strong>${__("Mã vật tư")}:</strong> ${alumglass.esc(msg.item_code || msg.label || "—")}</span>
            <span style="font-size:13px;"><strong>${__("Thành tiền")}:</strong>
                <strong style="color:#b45309;">${format_currency(msg.line_total || 0)}</strong></span>
        </div>`;
        html += `</div>`;
        setArea(html);
    }

    function load() {
        frappe.call({
            method: "alumglass.api.explain_bom_line",
            args: { quotation_item_name: quotation_item, slug: slug },
            callback: function (r) {
                const msg = r && r.message;
                if (msg && msg.success) {
                    showResult(msg);
                } else {
                    // Server xác nhận không có dữ liệu cho dòng → trạng thái,
                    // không phải lỗi mạng.
                    // B6 — server có thể kèm `detail` (giải thích thêm);
                    // hiện câu đó màu xám, không có thì câu chung.
                    showNoData((msg && (msg.detail || msg.message)) || "");
                }
            },
            // B8 — phân biệt LỖI QUYỀN với lỗi mạng/API. ⛔ tuyệt đối không
            // render err/stack — chỉ câu người-đọc-được (+ nút Thử lại cho
            // lỗi thật).
            error: function (r) {
                const status = r && (r.http_status_code || r.status);
                const excType = r && r.exc_type;
                if (excType === "PermissionError" || status === 403
                        || status === 401) {
                    showPermissionError();
                } else {
                    showRetryableError();
                }
            },
        });
    }

    dlg.show();
    showLoading();
    load();
};

// Gắn handler 1 LẦN cho cả trang (delegated): renderer được gọi lại nhiều lần
// (đổi tham số, preview lại, mở nhiều dialog) mà ⛔ không nhân đôi handler.
if (!alumglass._bom_explain_bound) {
    alumglass._bom_explain_bound = true;
    $(document).on("click", ".al-bom-explain-btn", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const $btn = $(this);
        const quotation_item = $btn.attr("data-quotation-item");
        const slug = $btn.attr("data-slug");
        if (!quotation_item || !slug) return;
        alumglass.explain_bom_line_dialog({
            quotation_item: quotation_item,
            slug: slug,
            item_code: $btn.attr("data-item-code") || "",
            label: $btn.attr("data-label") || "",
        });
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// F2/D2 — Lỗi & cảnh báo tính giá hiển thị cho NGƯỜI DÙNG
// ─────────────────────────────────────────────────────────────────────────
// Engine gom lỗi/cảnh báo vào `errors: {bom_items: {<khoá>: <câu>},
// cost_template: {<khoá>: <câu>}}`; server lưu kèm trong `al_bom_result` và
// `get_result_display` trả lại. Trước đây frontend KHÔNG đọc trường này ⇒
// cảnh báo "kính VƯỢT khổ tối đa" bị chôn, báo giá quá khổ vẫn ra giá bình
// thường. Ngoài ra `al_calc_error` có thể là stack trace (dữ liệu CŨ đã lưu
// trong DB) → ⛔ tuyệt đối không render thẳng ra màn hình người dùng.
// ═══════════════════════════════════════════════════════════════════════════

// Chuỗi có phải stack trace kỹ thuật? (Python traceback / JS stack)
alumglass.is_error_trace = function (s) {
    const t = String(s == null ? "" : s);
    if (!t) return false;
    if (/traceback \(most recent call last\)/i.test(t)) return true;
    if (/File ".*", line \d+/.test(t)) return true;
    if (/(^|\n)\s*at [\w$.<>]+ \(/.test(t)) return true;
    // Traceback bị cắt cụt phần đầu → nhận diện theo số dòng dấu hiệu
    const hits = t.split("\n").filter((l) => /^\s*(raise |File "|at )/.test(l)).length;
    return hits >= 2;
};

// Làm sạch 1 chuỗi lỗi (`al_calc_error` / `data.error`):
//   - câu tiếng Việt ngắn do server mới trả → dùng nguyên văn (cắt nếu quá dài)
//   - stack trace (bản cũ đã lưu trong DB) → thay bằng câu tiếng Việt ngắn;
//     trace GIỮ LẠI ở `trace` để nhét vào khối <details> ẩn + log console.
alumglass.sanitize_calc_error = function (error) {
    // `frappe.call` trả err dạng chuỗi HOẶC object (response lỗi) → rút câu
    // người-đọc-được, ⛔ không để lọt "[object Object]" ra màn hình.
    let raw = "";
    if (typeof error === "string") {
        raw = error.trim();
    } else if (error && typeof error === "object" && typeof error.message === "string") {
        raw = error.message.trim();
    } else if (error !== undefined && error !== null) {
        raw = String(error).trim();
    }
    if (!raw || raw === "[object Object]") return { message: "", trace: "" };
    if (alumglass.is_error_trace(raw)) {
        try { console.error("[AlumGlass] al_calc_error (stack trace):\n" + raw); } catch (e) { /* ignore */ }
        return {
            message: __("Tính giá thất bại. Vui lòng thử lại hoặc báo quản trị."),
            trace: raw,
        };
    }
    return { message: raw.length > 500 ? raw.slice(0, 500) + "…" : raw, trace: "" };
};

// Câu server trả về có phải câu NGƯỜI ĐỌC ĐƯỢC? (⛔ loại "KeyError: 'X'",
// "Formula 'TONG_VL' returned error (on_error=null → None)", tên hàm, mã trần)
alumglass.is_human_message = function (text) {
    const t = (text === undefined || text === null) ? "" : String(text).trim();
    if (!t) return false;
    if (alumglass.is_error_trace(t)) return false;
    // Dấu hiệu rác kỹ thuật (tên exception, giá trị null của engine)
    if (/error|exception|traceback|\bNone\b|\bnull\b/i.test(t)) return false;
    if (/^[A-Za-z0-9_.\-]+$/.test(t)) return false;      // 1 token: khoá/mã
    if (/_/.test(t) && !/\s/.test(t)) return false;       // snake_case
    // Câu tiếng Việt có dấu → chắc chắn đọc được
    if (/[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]/i.test(t)) return true;
    // Không dấu: chỉ nhận câu dài nhiều từ (VD câu tiếng Anh đơn giản)
    return t.length >= 20 && t.split(/\s+/).length >= 3;
};

// Dịch 1 khoá lỗi kỹ thuật → câu NGƯỜI ĐỌC ĐƯỢC (⛔ không bao giờ trả khoá thô).
// `group` = "bom_items" | "cost_template" — chỉ dùng cho câu chung khi không
// nhận dạng được (để user biết lỗi nằm ở vật tư hay ở khoản mục chi phí).
alumglass.calc_error_message = function (key, raw, group) {
    const k = String(key || "");
    const text = (raw === undefined || raw === null) ? "" : String(raw).trim();
    // Server trả câu tiếng Việt đọc được (VD cảnh báo vượt khổ kính kèm số đo
    // thực tế) → dùng nguyên văn; đây là trường hợp phổ biến.
    if (text && text !== k && alumglass.is_human_message(text)) {
        return text.length > 500 ? text.slice(0, 500) + "…" : text;
    }
    // Không có câu giải thích (hoặc câu là rác kỹ thuật) → dịch theo khoá đã biết.
    if (k.indexOf("__max_area_exceeded") !== -1) {
        return __("Diện tích kính '{0}' VƯỢT khổ tối đa của kính đang chọn — kiểm tra lại kích thước hoặc đổi cấu hình (chia khung / ghép kính) trước khi chốt báo giá.", [k.split("__")[0]]);
    }
    // Khoá lạ → câu chung, ⛔ KHÔNG phơi khoá kỹ thuật ra màn hình.
    return group === "cost_template"
        ? __("Một khoản mục chi phí không tính được (chi tiết đã ghi vào Error Log). Kiểm tra lại Công thức chi phí rồi tính giá lại.")
        : __("Một dòng vật tư trong BOM không tính được (chi tiết đã ghi vào Error Log). Kiểm tra lại tham số và cấu hình BOM rồi tính giá lại.");
};

// Cảnh báo (giá vẫn dùng được nhưng phải xác nhận lại) vs lỗi (không tin được).
alumglass.calc_error_severity = function (key, raw) {
    const k = String(key || "");
    const text = String(raw == null ? "" : raw);
    if (k.indexOf("__max_area_exceeded") !== -1) return "warning";
    if (/__warn/i.test(k) || /^\s*(cảnh báo|warning)/i.test(text)) return "warning";
    return "error";
};

// Chuẩn hoá `errors` → [{key, message, severity}] (đã dịch, đã làm sạch).
// Chịu được dữ liệu thiếu/bất thường (undefined, mảng, chuỗi) — không throw.
alumglass.collect_calc_errors = function (errors) {
    const out = [];
    if (!errors) return out;
    const push = (key, raw, group) => {
        out.push({
            key: String(key),
            message: alumglass.calc_error_message(key, raw, group),
            severity: alumglass.calc_error_severity(key, raw),
        });
    };
    const walk = (group, groupName) => {
        if (!group) return;
        if (Array.isArray(group)) {
            group.forEach((m, i) => push("item_" + i, m, groupName));
            return;
        }
        if (typeof group === "object") {
            Object.keys(group).forEach((k) => push(k, group[k], groupName));
            return;
        }
        push("", group, groupName);   // chuỗi trần (dữ liệu cũ / bất thường)
    };
    walk(errors.bom_items, "bom_items");
    walk(errors.cost_template, "cost_template");
    // Hình dạng khác (không có 2 nhóm con) → coi mỗi giá trị là 1 mục
    if (!out.length) {
        if (typeof errors === "string" || Array.isArray(errors)) {
            walk(errors, "");
        } else if (typeof errors === "object") {
            Object.keys(errors).forEach((k) => walk(errors[k], ""));
        }
    }
    return out;
};

// Banner lỗi/cảnh báo dán NGAY TRÊN bảng kết quả tính giá — người dùng vẫn
// thấy sau khi đã đóng popup (cảnh báo vượt khổ kính là rủi ro tiền thật).
alumglass.calc_errors_banner = function (errors) {
    const items = alumglass.collect_calc_errors(errors);
    if (!items.length) return "";
    const has_error = items.some((i) => i.severity === "error");
    const bg = has_error ? "#fef2f2" : "#fffbeb";
    const border = has_error ? "#fecaca" : "#fde68a";
    const color = has_error ? "#991b1b" : "#854d0e";
    const body = items.map((i) => `<li style="margin-bottom:3px;">${i.severity === "warning" ? "⚠️" : "⛔"} ${alumglass.esc(i.message)}</li>`).join("");
    return `<div style="margin:0 0 8px;padding:8px 10px;background:${bg};border:1px solid ${border};
        border-radius:6px;color:${color};font-size:12px;text-align:left;">
        <strong>${has_error
            ? __("Tính giá có lỗi — cần xử lý trước khi chốt báo giá")
            : __("Cảnh báo tính giá — cần xác nhận lại trước khi chốt báo giá")}</strong>
        <ul style="padding-left:18px;margin:6px 0 0;">${body}</ul>
    </div>`;
};

// Popup lỗi/cảnh báo (frappe.msgprint: cam = cảnh báo, đỏ = lỗi).
// `opts.dedupe_key`: chống popup lặp y hệt — auto-preview chạy lại sau MỖI lần
// đổi tham số, popup lặp sẽ che form; `opts.force` = user chủ động bấm tính.
alumglass.notify_calc_errors = function (errors, opts) {
    opts = opts || {};
    const items = alumglass.collect_calc_errors(errors);
    if (!items.length) return;
    const sig = items.map((i) => i.severity + ":" + i.message).join("§");
    if (opts.dedupe_key) {
        alumglass._calc_err_sig = alumglass._calc_err_sig || {};
        if (!opts.force && alumglass._calc_err_sig[opts.dedupe_key] === sig) return;
        alumglass._calc_err_sig[opts.dedupe_key] = sig;
    }
    const has_error = items.some((i) => i.severity === "error");
    const body = items.map((i) => `<li style="margin-bottom:4px;">${i.severity === "warning" ? "⚠️" : "⛔"} ${alumglass.esc(i.message)}</li>`).join("");
    frappe.msgprint({
        title: has_error
            ? __("Tính giá có lỗi — cần xử lý trước khi chốt báo giá")
            : __("Cảnh báo tính giá — cần xác nhận lại trước khi chốt báo giá"),
        message: `<ul style="padding-left:18px;margin:0;">${body}</ul>`,
        indicator: has_error ? "red" : "orange",
    });
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
            // Q2: pass-through màu sắc/nơi cấp vật tư/vị trí lắp đặt/góc cắt/ghi chú
            color: l.color, supplier_location: l.supplier_location,
            install_position: l.install_position, cut_angle: l.cut_angle, note: l.note,
            // Căn cứ chọn mã / căn cứ giá — nhánh fallback cũng phải giữ để khối
            // "Căn cứ" và nút "Vì sao ra số này?" không trống khi API display lỗi.
            rule_trace: l.rule_trace,
            price_trace: l.price_trace,
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
//     `frappe.client.set_value`. LƯU Ý: với doctype child table, API này của
//     Frappe load CẢ chứng từ cha rồi `doc.save()` → `modified` của cha trong
//     DB bị tăng nhưng form đang mở trên trình duyệt không hề được cập nhật.
//     Vì vậy sau khi ghi phải đồng bộ lại `frm.doc.modified` — nếu không lần
//     "Save" chứng từ sau đó báo TimestampMismatchError ("has been modified
//     after you have opened it"). Xem fix chi tiết trong branch bên dưới.
//   - Dòng MỚI thêm, chưa từng lưu (__islocal, tên dạng "new-quotation-item-N"):
//     Frappe chỉ cấp `name` thật cho child row SAU KHI cha được lưu → bắt
//     buộc phải `frm.save()` toàn bộ chứng từ (save sẽ refresh doc → sentinel
//     `modified` tự khớp), rồi tìm lại dòng theo idx.
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
                callback: (r) => {
                    // ── Fix TimestampMismatchError ──────────────────────────
                    // `frappe.client.set_value` với doctype child table thực chất
                    // load + save CẢ chứng từ cha (get_doc(parent).save()) → cột
                    // `modified` của cha trong DB đã tăng lên giá trị mới, nhưng
                    // `frm.doc` trên trình duyệt vẫn giữ `modified` cũ (từ lúc mở
                    // form). Khi user bấm "Save" Quotation, server so sánh
                    // modified nhận từ client với modified trong DB → lệch nhau →
                    // ném TimestampMismatchError.
                    // → Cập nhật `frm.doc.modified` về giá trị server vừa trả
                    // (chỉ tăng, không tụt — tránh 2 request đồng thời trả về
                    // theo thứ tự ngược). Response `r.message` chính là doc cha
                    // (as_dict) nên `modified`/`modified_by` lấy từ đó là khớp DB.
                    const res = (r && r.message) || {};
                    if (frm && frm.doc && res.modified
                        && (!frm.doc.modified || String(res.modified) > String(frm.doc.modified))) {
                        frm.doc.modified = res.modified;
                        if (res.modified_by) frm.doc.modified_by = res.modified_by;
                    }
                    resolve(cdn);
                },
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
// Kính theo vị trí — mã NHÌN THẤY ĐƯỢC + giá ngay cạnh ô chọn (Pha 3)
// ─────────────────────────────────────────────────────────────────────────
// Bối cảnh: mỗi vị trí kính có 1 ô Link → AL Glass Master. Engine tra giá
// theo `glass_master_map[rep]` (kính người dùng CHỌN cho báo giá này); chưa
// chọn thì tra theo mã CỐ ĐỊNH của BOM. Trước đây ô hiện TRỐNG khi rep là
// khoá tổng hợp theo slug (dòng BOM không khai `default_glass_master`) — dù
// engine vẫn đang tra giá theo một mã ⇒ người dùng không biết hệ thống dùng
// mã nào, và không đổi được mã ngay trên dialog.
//
// Server (`get_variable_set_for_bom`) trả thêm cho mỗi `glass_groups[i]`:
//   saved            mã đã lưu trong glass_master_map ("" nếu chưa chọn)
//   effective_code   mã engine SẼ dùng cho báo giá này
//   effective_source "saved" | "override" | "bom_default" | "item_code" | "none"
//   effective_name   tên kính / tên vật tư
//   price, price_list, has_price, price_approx
// Đổi mã trên dialog → API `get_glass_master_price` trả giá của mã mới.
//
// Toàn bộ hàm trong namespace này là THUẦN (không đụng DOM/frappe) để test
// bằng Node thuần:  node alumglass/tests/js/test_quotation_glass_pick.js
// ═══════════════════════════════════════════════════════════════════════════
alumglass.glass_pick = {
    PRICE_METHOD: "alumglass.api.get_glass_master_price",
    DEBOUNCE_MS: 300,
    // Câu cảnh báo khi bấm Lưu mà KHÔNG tính lại được giá kính. Phải nêu đúng
    // việc người dùng làm được: mở lại bảng tham số rồi bấm "Preview tính
    // giá" — mở lại KHÔNG tự tính (mã kính đã sync xuống DB nên trông như
    // "đã áp dụng", panel còn hiện kết quả cũ).
    RECALC_FAILED_MESSAGE: __("Chưa tính lại được giá kính — dòng đang giữ giá cũ."
        + " Mở lại bảng tham số rồi bấm \"Preview tính giá\" để tính lại."),
};

// Giá trị đầu tiên có nội dung (bỏ qua "", null, undefined, khoảng trắng).
alumglass.glass_pick._first_non_empty = function () {
    for (let i = 0; i < arguments.length; i += 1) {
        const v = arguments[i];
        if (v !== undefined && v !== null && String(v).trim() !== "") return String(v);
    }
    return "";
};

// Tham số gửi `get_variable_set_for_bom`.
// Dòng ĐÃ LƯU → gửi `quotation_item_name` để server đọc `glass_master_map`
// của báo giá này + tra giá theo cấu hình THẬT của dòng (thiếu tham số này
// thì server trả `saved=""`, `has_price=false`, `price_approx=true` → mọi ô
// kính hiện "chưa có giá" dù thực tế có).
// Dòng CHƯA lưu (`new-...`) → ⛔ không gửi: server kiểm quyền trên dòng
// không tồn tại sẽ lỗi.
alumglass.glass_pick.build_variable_set_args = function (bom_code, row_name) {
    const args = { bom_code: bom_code };
    const name = String(row_name || "");
    if (name && name.indexOf("new-") !== 0) {
        args.quotation_item_name = name;
    }
    return args;
};

// Mã khởi tạo cho ô Link + nguồn của mã đó.
// `savedFallback` = mã đã lưu do CLIENT biết (glass_master_map của báo giá
// đang mở, rồi tới biến global `glass_master` cũ) — dùng để chạy được cả khi
// server chưa kịp trả `saved`.
// Trả:
//   code            mã engine đang dùng (LUÔN hiển thị được cho người dùng)
//   source          saved | pending | override | bom_default | item_code | none
//   set_value       có được nhét vào control Link hay không
//   is_glass_master mã có thật trong AL Glass Master hay không
// `effective_is_glass_master === false` = mã giữ chỗ trên BOM (VD KINH-01)
// KHÔNG tồn tại trong danh mục → control phải để TRỐNG (nhét vào sẽ như dữ
// liệu hỏng), nhưng vẫn HIỆN mã đó ở dòng trạng thái. Thiếu cờ (server cũ)
// → giữ hành vi cũ, ⛔ không tự suy.
//
// `source:"pending"` = mã CLIENT biết KHÁC mã server đã tính (VD vừa bấm Lưu
// nhưng preview chưa chạy). Lúc đó giá server trả là giá của MÃ CŨ ⇒ ⛔ không
// được vẽ, phải lấy lại giá (xem `price_for_initial`).
alumglass.glass_pick.initial = function (group, savedFallback) {
    const g = group || {};
    const serverSaved = alumglass.glass_pick._first_non_empty(g.saved);
    // Giá trị CLIENT biết (glass_master_map đang mở) thắng giá trị server
    // đọc được — hai bên lệch nhau nghĩa là thay đổi chưa xuống DB/preview.
    const clientSaved = alumglass.glass_pick._first_non_empty(savedFallback);
    const saved = clientSaved || serverSaved;
    if (saved) {
        const hasServerState = ("saved" in g) || ("effective_code" in g);
        // Server ĐANG tính theo mã nào? (mã đã chọn, hoặc mã engine resolve
        // được — TD biến global `glass_master` cũ mà engine vẫn đọc.)
        const serverEffective = alumglass.glass_pick._first_non_empty(
            g.effective_code, g.default, serverSaved);
        const pending = hasServerState && saved !== serverEffective;
        return {
            code: saved,
            source: pending ? "pending" : "saved",
            set_value: true,
            is_glass_master: true,
        };
    }
    const code = alumglass.glass_pick._first_non_empty(g.effective_code, g.default);
    if (!code) {
        return { code: "", source: g.effective_source || "none", set_value: false, is_glass_master: true };
    }
    // Server cũ chưa trả `effective_source` → mã chỉ có thể đến từ `default`
    // khai trên BOM (mã cố định / mã đại diện giữ chỗ).
    const isMaster = g.effective_is_glass_master !== false;
    return {
        code: code,
        source: g.effective_source || "bom_default",
        set_value: isMaster,
        is_glass_master: isMaster,
    };
};

// Ghép nhãn "Tên (MÃ)" — thiếu tên thì chỉ mã, thiếu mã thì chỉ tên.
alumglass.glass_pick.code_label = function (code, name) {
    const c = code ? String(code) : "";
    const n = name ? String(name) : "";
    if (n && c) return n + " (" + c + ")";
    return c || n;
};

// Câu trạng thái người-đọc-được. `tone`: ok | warn | muted (trung tính).
// opts.code / opts.name / opts.is_glass_master:
//   - name: tên kính server trả (`effective_name`) → hiện TÊN, không chỉ mã
//   - is_glass_master === false: mã giữ chỗ KHÔNG có trong danh mục kính
// Lời khuyên được GỘP vào câu trạng thái (không còn dòng hint riêng).
alumglass.glass_pick.status = function (source, opts) {
    const o = opts || {};
    const label = alumglass.glass_pick.code_label(o.code, o.name);
    if (o.is_glass_master === false && o.code) {
        return {
            text: __("Mã đại diện trên BOM: ") + o.code + __(" (không phải kính trong danh mục)")
                + " · " + __("Chọn kính thật cho vị trí này."),
            tone: "warn",
        };
    }
    switch (source) {
        case "saved":
            return {
                text: label ? (__("Đã chọn: ") + label) : __("Đã chọn cho báo giá này"),
                tone: "ok",
            };
        case "applied":
            // Nêu TÊN kính như các trạng thái khác — người dùng đối chiếu được
            // "mã đang hiện trên ô" với "giá đang hiện trên dòng".
            return {
                text: label ? (__("Đã áp dụng: ") + label) : __("Đã áp dụng"),
                tone: "ok",
            };
        case "override":
        case "pending":
            // Hệ thống TỰ tính lại sau ~700ms — ⛔ không bắt người dùng bấm gì.
            return { text: __("Đang áp dụng kính mới — tự tính lại giá sau giây lát"), tone: "warn" };
        case "bom_default":
        case "item_code":
            return {
                text: (label ? (__("Đang dùng mã cố định trên BOM: ") + label)
                    : __("Đang dùng mã cố định trên BOM"))
                    + " · " + __("Đổi được nếu khách chọn kính khác."),
                tone: "muted",
            };
        case "none":
        default:
            return { text: __("Chưa có mã kính — chọn kính cho vị trí này"), tone: "muted" };
    }
};

// Phần thông tin giá của 1 phần tử glass_groups (để vẽ lại khi bỏ chọn mã).
alumglass.glass_pick.group_price = function (group) {
    const g = group || {};
    return {
        has_price: g.has_price,
        price: g.price,
        price_list: g.price_list,
        price_approx: g.price_approx,
    };
};

// Giá được vẽ NGAY khi mở dialog: chỉ dùng giá của nhóm khi mã hiển thị ĐÚNG
// là mã server đã tính (`effective_code`/`default`). Mã khác ⇒ trả null =
// "phải gọi API lấy giá", ⛔ tuyệt đối không vẽ giá của mã cũ cạnh mã mới.
alumglass.glass_pick.price_for_initial = function (initCode, group) {
    const g = group || {};
    const serverCode = alumglass.glass_pick._first_non_empty(g.effective_code, g.default);
    if (!initCode) return {};
    if (String(initCode) === serverCode) return alumglass.glass_pick.group_price(g);
    return null;
};

// Xoá trắng ô kính → hiện lại mã engine VẪN đang dùng: mã giữ chỗ (nếu có),
// không thì mã mặc định khai trên BOM. Không có gì ⇒ "chưa có mã".
alumglass.glass_pick.fallback_after_clear = function (group, placeholderCode) {
    const g = group || {};
    const placeholder = alumglass.glass_pick._first_non_empty(placeholderCode);
    if (placeholder) {
        return { code: placeholder, source: g.effective_source || "bom_default", is_glass_master: false };
    }
    const def = alumglass.glass_pick._first_non_empty(g.default);
    if (def) return { code: def, source: "bom_default", is_glass_master: true };
    return { code: "", source: "none", is_glass_master: true };
};

// ── CHỮ KÝ lựa chọn kính — nguồn sự thật DUY NHẤT cho "giá đã theo kính nào"
// Thay cho các cờ rời trước đây (`source === override`, `_glass_pending_recalc`,
// `_glass_changed_after_preview`): mỗi lần đổi/xoá kính đều làm chữ ký đổi,
// nên chỉ cần so chữ ký hiện tại với chữ ký của lần tính giá THÀNH CÔNG gần
// nhất là biết rate có còn khớp mã đang hiện hay không.
//
// `entries` = mảng [{ rep, code }] (dialog truyền thẳng `_glass_controls` —
// mỗi entry có `rep` và mã đang hiện ở ô là `display_code`). Trả chuỗi JSON
// ổn định của các cặp [rep, mã]:
//   - sắp theo `rep` ⇒ thứ tự phần tử đầu vào KHÔNG làm đổi chữ ký
//   - mã rỗng VẪN ghi "" ⇒ phân biệt "vị trí chưa chọn kính" ([rep, ""])
//     với "không có vị trí kính nào" ([])
alumglass.glass_pick.glass_signature = function (entries) {
    const list = Array.isArray(entries) ? entries : [];
    const pairs = [];
    list.forEach(function (e) {
        if (!e || e.rep === undefined || e.rep === null) return;
        const raw = (e.code !== undefined && e.code !== null) ? e.code : e.display_code;
        pairs.push([
            String(e.rep),
            String(raw === undefined || raw === null ? "" : raw).trim(),
        ]);
    });
    pairs.sort(function (a, b) {
        if (a[0] < b[0]) return -1;
        if (a[0] > b[0]) return 1;
        return 0;
    });
    return JSON.stringify(pairs);
};

// Chữ ký hiện tại KHÁC chữ ký của lần tính giá thành công gần nhất?
// Đây là quyết định của nút 💾 Lưu: true ⇒ phải tính lại rồi mới đóng,
// false ⇒ đóng ngay. Phủ cả 2 đường lỗi cũ: xoá trắng ô (kính quay về mã
// mặc định) và đổi kính trong lúc một lượt tính giá đang chạy.
alumglass.glass_pick.needs_recalc = function (currentSig, appliedSig) {
    const norm = (v) => String(v === undefined || v === null ? "" : v);
    return norm(currentSig) !== norm(appliedSig);
};

// Lượt tính giá vừa xong có quyền gắn "Đã áp dụng" không? Chỉ đúng khi chữ
// ký HIỆN TẠI trùng chữ ký đã CHỤP lúc lượt đó bắt đầu — đổi kính giữa lúc
// tính thì kết quả vừa về là của mã CŨ, gắn "Đã áp dụng" là nói dối và còn
// chặn nút Lưu tính lại.
alumglass.glass_pick.should_mark_applied = function (currentSig, capturedSig) {
    return !alumglass.glass_pick.needs_recalc(currentSig, capturedSig);
};

// 300000 → "300.000 đ" (dấu chấm ngăn nghìn, hậu tố đ theo cách đọc VN).
alumglass.glass_pick.format_price = function (value) {
    const n = Number(value);
    const safe = isFinite(n) ? n : 0;
    const rounded = Math.round(safe);
    const digits = String(Math.abs(rounded)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return (rounded < 0 ? "-" : "") + digits + " đ";
};

// Câu giá hiển thị dưới ô kính.
//   info = kết quả `normalize_price_response` HOẶC phần tử glass_groups
//   ({price, price_list, has_price, price_approx}) HOẶC {state:"loading"|...}
// Trả "" khi server CHƯA trả thông tin giá nào (bản API cũ) — ⛔ không bịa
// "Chưa có giá" khi thực ra chỉ là chưa có dữ liệu.
alumglass.glass_pick.price_text = function (info) {
    const d = info || {};
    const state = d.state || "";
    if (state === "loading") return __("Đang lấy giá...");
    if (state === "error") return __("Chưa lấy được giá, thử lại");
    if (state === "invalid") return d.message ? String(d.message) : __("Mã kính này không dùng được, chọn mã khác");
    if (state === "unsaved") return __("Giá hiện sau khi lưu dòng và hệ thống tính lại.");

    const hasInfo = d.has_price !== undefined || d.price !== undefined || d.price_list !== undefined;
    if (!hasInfo) return "";
    // ⛔ Không suy "có giá" từ price > 0: giá 0 có thể là giá thật.
    const hasPrice = d.has_price !== undefined ? d.has_price === true
        : (d.price !== undefined && d.price !== null);
    if (!hasPrice) {
        const list = alumglass.glass_pick._first_non_empty(d.price_list);
        return list
            ? __("Chưa có giá trong bảng giá ") + list
            : __("Chưa có giá — kiểm tra bảng giá đang áp dụng");
    }
    const amount = alumglass.glass_pick.format_price(d.price);
    const approx = d.approx === true || d.price_approx === true;
    return approx
        ? __("Giá: ") + "≈ " + amount + " " + __("(giá chốt khi tính lại xong)")
        : __("Giá: ") + amount;
};

// Chuẩn hoá phản hồi `get_glass_master_price` về 1 dạng duy nhất để UI dùng.
// `resp` có thể là object kết quả trực tiếp, hoặc `r` của frappe.call
// ({message: {...}}). Không bao giờ throw.
alumglass.glass_pick.normalize_price_response = function (resp, requestedCode) {
    let data = resp;
    if (data && typeof data === "object" && data.success === undefined
        && data.message && typeof data.message === "object") {
        data = data.message;
    }
    const code = requestedCode || "";
    if (!data || typeof data !== "object") {
        return { ok: false, state: "error", code: code, has_price: false };
    }
    if (data.success === false) {
        // Server kèm câu tiếng Việt đọc được (VD "Mã kính không tồn tại") →
        // hiện nguyên văn. Stack trace / mã kỹ thuật → câu chung, ⛔ không phơi.
        const msg = alumglass.is_human_message(data.message)
            ? String(data.message).trim() : "";
        return msg
            ? { ok: false, state: "invalid", code: data.code || code, message: msg, has_price: false }
            : { ok: false, state: "error", code: data.code || code, has_price: false };
    }
    // Không phải payload của API (VD object lỗi mạng / _server_messages của
    // frappe.call) → "Chưa lấy được giá, thử lại", ⛔ không đoán là "không có giá".
    if (data.success !== true
        && data.has_price === undefined
        && data.price === undefined
        && data.price_list === undefined) {
        return { ok: false, state: "error", code: code, has_price: false };
    }
    const hasPrice = data.has_price === true;
    return {
        ok: true,
        state: hasPrice ? "ok" : "no_price",
        code: data.code || code,
        name: data.name || "",
        price: Number(data.price) || 0,
        price_list: data.price_list || "",
        has_price: hasPrice,
        approx: data.approx === true,
        note: data.note || "",
    };
};

// Bộ hẹn giờ gọi API giá sau khi người dùng đổi mã kính (mặc định 300ms).
// `timers` inject được để test bằng đồng hồ giả; `call` inject được để test
// mà không cần frappe. Chỉ lần gõ CUỐI được gọi (debounce) và kết quả về
// MUỘN của lần trước bị bỏ (chống race).
alumglass.glass_pick.make_price_requester = function (opts) {
    opts = opts || {};
    const timers = opts.timers || {
        setTimeout: function (fn, ms) { return setTimeout(fn, ms); },
        clearTimeout: function (id) { return clearTimeout(id); },
    };
    const delay = (opts.delay === undefined || opts.delay === null)
        ? alumglass.glass_pick.DEBOUNCE_MS : opts.delay;
    const call = opts.call || function (method, args, callback, on_error) {
        frappe.call({ method: method, args: args, callback: callback, error: on_error });
    };
    let timer = null;
    let seq = 0;
    return {
        request: function (code, on_result) {
            if (timer !== null) { timers.clearTimeout(timer); timer = null; }
            timer = timers.setTimeout(function () {
                timer = null;
                const mine = ++seq;
                // Lỗi mạng / lỗi server không có payload giá → câu chung cho
                // người dùng, ⛔ không phơi exception.
                const fail = function () {
                    if (mine !== seq) return;
                    if (typeof on_result === "function") {
                        on_result({ ok: false, state: "error", code: code, has_price: false });
                    }
                };
                call(alumglass.glass_pick.PRICE_METHOD, {
                    quotation_item_name: opts.quotation_item_name || "",
                    glass_code: code,
                }, function (resp) {
                    if (mine !== seq) return;   // kết quả cũ về sau → bỏ
                    const out = alumglass.glass_pick.normalize_price_response(resp, code);
                    if (typeof on_result === "function") on_result(out);
                }, fail);
            }, delay);
        },
        cancel: function () {
            if (timer !== null) { timers.clearTimeout(timer); timer = null; }
        },
    };
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
        this._glass_controls = [];  // [{ rep, ctrl, group, source, $status, $price }]
        this._color_controls = []; // [{ rep, ctrl }] — selector màu per-line (color_groups, Q2)
        this._glass_pending_recalc = false; // có mã kính khác mã server đã tính
        this._current_vars = [];    // Variable Set đang hiển thị
        this._realtime_handler = null;
        this._preview_seq = 0;      // Chống race: preview cũ trả về SAU preview mới → bỏ qua
        this._debounced_auto_preview = null;
        this._auto_preview_timer = null;    // timer debounce (huỷ được)
        this._preview_inflight = false;      // đang có 1 lượt tính giá chạy dở
        // Chữ ký lựa chọn kính (xem alumglass.glass_pick.glass_signature):
        //   _preview_signature         chụp lúc 1 lượt tính giá BẮT ĐẦU
        //   _glass_applied_signature   chữ ký của lần tính giá THÀNH CÔNG gần nhất
        // So 2 chữ ký này thay cho cờ rời → tự phủ cả ca xoá trắng ô kính lẫn
        // ca đổi kính trong lúc lượt tính giá đang chạy.
        this._preview_signature = null;
        this._glass_applied_signature = null;
        this._preview_waiters = [];  // chờ preview xong (nút 💾 Lưu)
        // Chỉ bật auto-preview SAU KHI dialog đã nạp xong lần đầu — tránh việc
        // set giá trị mặc định lúc mở dialog (set_value lập trình cũng kích hoạt
        // onchange) tự động bắn 1 preview thừa ngay khi vừa mở dialog.
        this._dialog_ready = false;
        // Dialog đang MỞ (visible). Auto-preview chỉ được chạy khi dialog mở —
        // debounce còn treo mà dialog đã đóng KHÔNG được âm thầm ghi DB, nếu không
        // `modified` của chứng từ cha trên server bị đẩy lên (mà form không hay
        // biết) → lần "Save" chứng từ sau báo TimestampMismatchError.
        this._dialog_open = false;
    }

    show() {
        this._render_dialog();
    }

    // ── Đọc Variable Set từ BOM → Bom Set → Variable Set ──────────
    async _load_variable_set() {
        const bom = this.child_doc.al_bom;
        if (!bom) { this._bom_meta = null; return []; }

        // Gửi kèm tên dòng (nếu dòng đã lưu) — server dùng để đọc
        // `glass_master_map` + tra giá theo cấu hình THẬT của báo giá này.
        // Dòng `new-...` thì KHÔNG gửi (xem build_variable_set_args).
        const args = alumglass.glass_pick.build_variable_set_args(
            bom, (this.child_doc && this.child_doc.name) || "");

        return new Promise(resolve => {
            frappe.call({
                method: "alumglass.api.get_variable_set_for_bom",
                args: args,
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
            { fieldname: "upload_section", fieldtype: "HTML", label: "Export/Import" },
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
            primary_action: () => this._on_primary_action(),
            secondary_action_label: __("🖥️ Preview tính giá"),
            secondary_action: () => {
                this._save();  // Lưu trước khi preview
                this._run_preview(true);  // manual → cho phép cuộn tới kết quả
            },
        });
        this.dialog.show();
        this._dialog_open = true;
        this.dialog.$wrapper.find(".modal-dialog").css("max-width", "80vw");

        // Dialog đóng → đánh dấu đã đóng (chặn auto-preview treo còn chạy) +
        // cleanup realtime listener (tránh leak)
        $(this.dialog.$wrapper).on("hidden.bs.modal", () => {
            this._dialog_open = false;
            this._cleanup_realtime();
        });

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
            setTimeout(() => {
                this._dialog_ready = true;
                // Dòng đang có mã kính KHÁC mã server đã tính (vừa Lưu mà
                // preview chưa chạy) → tính lại ngay để rate khớp mã đang hiện.
                if (this._glass_pending_recalc) {
                    this._glass_pending_recalc = false;
                    this._schedule_auto_preview();
                }
            }, 50);
        });
        

        alumglass.excel_io.attach(this.dialog, {
            section: "upload_section",
            table: "extra_vars", // Sửa tên bảng con
            doctype: "Purchase Receipt",
            key: "purchase_receipt",
            // validator: "eupapp.eupapp.doctype.overrides.purchase_invoice.validate_receipt_rows",
            export: { enabled: true, filename: "purchase_receipt" },
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
        this._glass_pending_recalc = false;
        this._color_controls = [];
        // Chữ ký "kính mà SERVER đã tính" — dựng lại cùng lúc với controls,
        // ở ngay dưới (mục Kính theo vị trí).
        this._glass_applied_signature = alumglass.glass_pick.glass_signature([]);
        $container.empty();

        // Mỗi section biến bọc trong <details> để có thể thu gọn (dialog đỡ
        // dài khi BOM có nhiều biến) — mặc định mở (open) như cũ.
        const makeSection = (title) => {
            const $details = $(`<details class="al-var-section" open style="margin:4px 0 10px;">
                <summary style="cursor:pointer;font-weight:600;color:#1e293b;font-size:12.5px;
                    padding:5px 7px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:4px;
                    list-style:none;">${title}</summary>
                <div class="al-var-section-body" style="padding:8px 4px 2px;"></div>
            </details>`);
            $container.append($details);
            return $details.find(".al-var-section-body");
        };

        const existing = this._parse_existing();
        // Q1a: API (DEV1) trả `glass_groups` = gom AL Bom Set line kính theo
        // mã đại diện `default_glass_master` → hiện N selector kính per rep.
        // Chưa có contract (glass_groups vắng) → giữ biến global `glass_master`
        // như cũ (backward-compat).
        const glassGroups = (this._bom_meta && Array.isArray(this._bom_meta.glass_groups))
            ? this._bom_meta.glass_groups : [];
        const hasGlassGroups = glassGroups.length > 0;
        // Q2: color_groups — tương tự kính, nhóm theo material category (Nhôm/
        // Kính/Phụ kiện/Vật tư phụ...) để vẽ subsection riêng cho từng nhóm.
        const colorGroups = (this._bom_meta && Array.isArray(this._bom_meta.color_groups))
            ? this._bom_meta.color_groups : [];
        const hasColorGroups = colorGroups.length > 0;

        let user_vars = (vars || []).filter(v => !v.is_system);
        if (hasGlassGroups) {
            user_vars = user_vars.filter(v => v.var_name !== "glass_master");
        }
        if (hasColorGroups) {
            // "aluminum_color" giờ chọn per-vị-trí trong section "Màu sắc" —
            // ẩn khỏi Biến đầu vào để khỏi trùng lặp.
            user_vars = user_vars.filter(v => v.var_name !== "aluminum_color");
        }
        // "Bộ phụ kiện" (accessory_set/_accessory_set) đã có field riêng
        // "Phụ kiện (Accessory Set)" ở mục Cấu hình BOM khi load từ Bom/Bom
        // Set — ẩn khỏi Biến đầu vào để tránh 2 chỗ chỉnh cùng 1 thứ.
        user_vars = user_vars.filter(v => v.var_name !== "accessory_set" && v.var_name !== "_accessory_set");
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
        // Mỗi nhóm = 1 vị trí kính. Ô Link LUÔN hiện mã engine đang dùng cho
        // báo giá này (`saved || effective_code`) — ⛔ không để trống khi hệ
        // thống vẫn tra giá theo một mã (người dùng sẽ không biết đang dùng
        // mã nào, và không đổi được ngay trên dialog).
        // Dưới ô: câu TRẠNG THÁI (mã này từ đâu) + GIÁ của mã đó.
        // Đổi mã trên dialog → tự lấy lại giá (xem _on_glass_code_change).
        if (hasGlassGroups) {
            const $body = makeSection(__("Kính theo vị trí"));
            const $grid = $('<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-gap:0 12px;margin-bottom:8px;"></div>');
            $body.append($grid);
            const glassMap = existing.glass_master_map || {};
            // re-render → entry cũ (kèm bộ hẹn giờ lấy giá riêng) bị bỏ hết.
            this._glass_pending_recalc = false;
            // Mã kính SERVER đã tính cho dòng này (trước mọi thay đổi của
            // người dùng trong phiên dialog) — dựng chữ ký "đã áp dụng".
            const appliedEntries = [];
            glassGroups.forEach(g => {
                const rep = g.rep || "";
                if (!rep) return;
                // Nguồn giá trị khởi tạo (ưu tiên giảm dần):
                //   1. glass_master_map của BÁO GIÁ ĐANG MỞ — người dùng đã chọn
                //   2. `g.saved` server trả (đọc từ al_bom_vars trong DB)
                //   3. biến global `glass_master` cũ (backward-compat)
                //   4. `g.effective_code` — mã engine SẼ dùng: mã cố định khai
                //      trên BOM (`bom_default`) hoặc item_code của dòng kính
                //      (`item_code`).
                // rep dạng khoá tổng hợp theo slug KHÔNG phải mã AL Glass Master
                // hợp lệ ⇒ ⛔ không tự bịa ra mã, chỉ hiện mã server đã nói.
                const savedChoice = glassMap[rep] || g.saved || existing.glass_master || "";
                const init = alumglass.glass_pick.initial(g, savedChoice);
                // Mã khác mã server đã tính → phải tính lại giá sau khi render.
                if (init.source === "pending") this._glass_pending_recalc = true;
                const df = {
                    fieldname: "al_glass_" + String(rep).replace(/[^A-Za-z0-9_]/g, "_"),
                    fieldtype: "Link",
                    options: "AL Glass Master",
                    label: __(g.label || rep),
                    // Mã giữ chỗ trên BOM KHÔNG có trong danh mục kính → ⛔ không
                    // nhét vào Link (người dùng sẽ thấy như dữ liệu hỏng); vẫn
                    // hiện ở dòng trạng thái bên dưới.
                    default: init.set_value ? init.code : "",
                };
                const $cell = $('<div style="min-width:0;"></div>');
                $grid.append($cell);
                const ctrl = frappe.ui.form.make_control({ df, parent: $cell[0], only_input: false });
                ctrl.make_input();
                ctrl.refresh();
                if (init.set_value && init.code !== "") {
                    ctrl.set_value(init.code);
                }
                const priceForInitial = alumglass.glass_pick.price_for_initial(init.code, g);
                const entry = {
                    rep, ctrl, group: g,
                    source: init.source,
                    display_code: init.code,
                    // Tên kính chỉ dùng khi mã hiển thị ĐÚNG là mã server đã tính
                    // (tên của mã khác sẽ làm người dùng hiểu sai).
                    display_name: priceForInitial === null ? "" : (g.effective_name || ""),
                    price_info: {},
                    // Mã giữ chỗ (không phải kính thật) — giữ lại để khi người
                    // dùng bỏ chọn vẫn nói đúng mã engine đang dùng.
                    placeholder_code: init.is_glass_master === false ? init.code : "",
                    is_glass_master: init.is_glass_master,
                };
                this._glass_controls.push(entry);
                // Mã kính SERVER đang tính cho vị trí này (`effective_code` =
                // mã đã chọn trước đó / mã cố định trên BOM / item_code dòng).
                // Mã hiện trên ô khác mã này (source "pending") ⇒ chữ ký lệch
                // ⇒ nút 💾 Lưu biết phải tính lại trước khi đóng.
                appliedEntries.push({
                    rep,
                    code: alumglass.glass_pick._first_non_empty(g.effective_code, g.default),
                });
                // `rep` dạng `__slug__...` là KHOÁ NỘI BỘ (không phải tên biến
                // người dùng đặt) — ⛔ không annotate cạnh ô kính.
                if (String(rep).indexOf("__slug__") !== 0) {
                    this._annotate_var_name($cell, rep);
                }
                // 2 dòng dưới ô: trạng thái (kèm tên kính) / giá.
                entry.$status = $('<div class="al-glass-status" style="margin-top:2px;font-size:11px;line-height:1.35;"></div>');
                entry.$price = $('<div class="al-glass-price" style="margin-top:1px;font-size:11px;line-height:1.35;"></div>');
                $cell.append(entry.$status).append(entry.$price);
                if (priceForInitial === null) {
                    // Mã hiển thị KHÁC mã server đã tính (dòng vừa đổi kính mà
                    // preview chưa chạy) ⇒ giá của nhóm là giá MÃ CŨ → ⛔ không
                    // vẽ; lấy giá đúng mã đang hiện và báo "đang lấy giá".
                    this._fetch_glass_price(entry, init.code, init.source);
                } else {
                    this._render_glass_state(entry, { source: init.source, price: priceForInitial });
                }
            });
            this._glass_applied_signature = alumglass.glass_pick.glass_signature(appliedEntries);
        }

        // ── Màu sắc theo vị trí (color_groups, Q2) — nhóm theo material
        // category (Nhôm/Kính/Phụ kiện/Vật tư phụ...) thành subsection riêng,
        // mỗi vị trí 1 selector Link → AL Color Standard (chỉ hiện các bản
        // ghi đã tích "Mau dai dien"). Dòng không cấu hình default_color =
        // không có trong color_groups (luôn dùng màu cố định, không selector).
        if (hasColorGroups) {
            const $body = makeSection(__("Màu sắc"));
            const colorMap = existing.color_master_map || {};
            const byCategory = {};
            const catOrder = [];
            colorGroups.forEach(g => {
                const key = g.category_label || __("Khác");
                if (!byCategory[key]) { byCategory[key] = []; catOrder.push(key); }
                byCategory[key].push(g);
            });
            catOrder.forEach(catLabel => {
                $body.append(`<div style="font-size:11px;color:#64748b;font-weight:600;
                    margin:4px 0 4px;text-transform:uppercase;letter-spacing:.02em;">${alumglass.esc(catLabel)}</div>`);
                const $subGrid = $('<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-gap:0 12px;margin-bottom:6px;"></div>');
                $body.append($subGrid);
                byCategory[catLabel].forEach(g => {
                    const rep = g.rep || "";
                    if (!rep) return;
                    const current = colorMap[rep] || existing.aluminum_color || g.default || "";
                    const df = {
                        fieldname: "al_color_" + String(rep).replace(/[^A-Za-z0-9_]/g, "_"),
                        fieldtype: "Link",
                        options: "AL Color Standard",
                        label: __(g.label || rep),
                        get_query: () => ({ filters: { is_representative: 1 } }),
                        default: current,
                    };
                    const $cell = $('<div style="min-width:0;"></div>');
                    $subGrid.append($cell);
                    const ctrl = frappe.ui.form.make_control({ df, parent: $cell[0], only_input: false });
                    ctrl.make_input();
                    ctrl.refresh();
                    if (current !== undefined && current !== null && current !== "") {
                        ctrl.set_value(current);
                    }
                    this._color_controls.push({ rep, ctrl });
                    this._annotate_var_name($cell, rep);
                });
            });
        }

        // ── Biến đầu vào (user) — 3 cột ──
        if (user_vars.length) {
            const $body = makeSection(__("Biến đầu vào"));
            const $grid = $('<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-gap:0 12px;margin-bottom:8px;"></div>');
            $body.append($grid);
            user_vars.forEach(v => {
                const val = existing[v.var_name] !== undefined ? existing[v.var_name] : v.default_value;
                const df = this._var_to_field(v, val);
                if (df) this._make_var_control($grid, v, df);
            });
        }

        // ── Biến hệ thống (hiển thị sau, cho phép chỉnh sửa) ──
        if (sys_vars.length) {
            const $body = makeSection(__("Biến hệ thống (tự động)"));
            const $grid = $('<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-gap:0 12px;margin-bottom:8px;"></div>');
            $body.append($grid);
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
            $body.append($reset);
        }

        // Gắn auto-preview cho MỌI control vừa tạo ở trên (kính + màu + biến).
        this._bind_auto_preview_listeners();

        // Có mã kính khác mã server đã tính (VD vừa Lưu) → tự tính lại giá.
        // Lần render đầu `_dialog_ready` còn false; khi sẵn sàng, timeout nạp
        // dialog sẽ tự lên lịch (xem _render_dialog).
        if (this._glass_pending_recalc && this._dialog_ready) {
            this._glass_pending_recalc = false;
            this._schedule_auto_preview();
        }
    }

    // Hiện tên biến (var_name/rep) cạnh label + tooltip khi rê chuột vào —
    // giống hành vi xem tên field trong doctype/dialog chuẩn của Frappe.
    _annotate_var_name($cell, var_name) {
        if (!var_name) return;
        const $label = $cell.find("label.control-label").first();
        if (!$label.length) return;
        $label.attr("title", __("Tên biến") + ": " + var_name);
        if (!$label.find(".al-var-name-hint").length) {
            $label.append(` <span class="al-var-name-hint" title="${__("Tên biến")}: ${var_name}"
                style="font-weight:400;color:#94a3b8;font-size:10px;font-family:monospace;">(${var_name})</span>`);
        }
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
        this._annotate_var_name($cell, v.var_name);
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
        if (!this._dialog_ready || !this.dialog || !this._dialog_open) return;
        this._mark_preview_stale();
        if (!this._debounced_auto_preview) {
            // Debounce tự viết — `frappe.utils.debounce` không huỷ được timer
            // đang treo; nút 💾 Lưu cần huỷ để KHÔNG tính giá 2 lần.
            this._debounced_auto_preview = () => {
                if (this._auto_preview_timer) clearTimeout(this._auto_preview_timer);
                this._auto_preview_timer = setTimeout(() => {
                    this._auto_preview_timer = null;
                    if (this.dialog && this._dialog_open) this._run_preview();
                }, 700);
            };
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
        this._color_controls.forEach(({ ctrl }) => bind(ctrl));
        // Pha 3: đổi mã kính → lấy giá của mã MỚI sau 300ms (khác auto-preview
        // 700ms ở trên: cái đó tính lại cả báo giá). Bind lại sau mỗi lần
        // re-render vùng biến vì controls cũ đã bị huỷ.
        this._glass_controls.forEach(entry => this._bind_glass_price_listener(entry));
    }

    // ── Vẽ lại trạng thái + giá dưới 1 ô kính ────────────────────
    // `state` = { source, price } — price nhận cả dạng phần tử glass_groups
    // lẫn kết quả normalize_price_response. Bỏ `price` ⇒ giữ giá đang hiện.
    _render_glass_state(entry, state) {
        if (!entry) return;
        const pick = alumglass.glass_pick;
        state = state || {};
        const source = state.source || entry.source || "none";
        entry.source = source;
        if (state.price !== undefined) entry.price_info = state.price;
        // 1 dòng trạng thái (kèm TÊN kính + lời khuyên đã gộp trong câu).
        const st = pick.status(source, {
            code: entry.display_code || "",
            name: entry.display_name || "",
            is_glass_master: entry.is_glass_master !== false,
        });
        const toneColor = { ok: "#15803d", warn: "#a16207", muted: "#64748b" }[st.tone] || "#64748b";
        if (entry.$status && entry.$status.length) {
            entry.$status.css("color", toneColor).text(st.text);
        }
        if (entry.$price && entry.$price.length) {
            const info = entry.price_info || {};
            const approx = info.approx === true || info.price_approx === true;
            let color = "#334155";
            if (info.state === "error" || info.state === "invalid" || info.state === "unsaved") {
                color = "#b45309";
            } else if (info.state === "loading") {
                color = "#64748b";
            } else if (info.has_price === true) {
                color = approx ? "#a16207" : "#1e293b";
            } else if (info.has_price === false) {
                color = "#b45309";
            }
            entry.$price.text(pick.price_text(info)).css("color", color);
            // Lỗi → dòng giá BẤM ĐƯỢC để thử lại (chọn lại đúng mã cũ không
            // bắn `change`, nên không có chỗ nào khác để thử).
            entry.$price.off("click.al_glassretry");
            if (info.state === "error") {
                entry.$price
                    .css({ cursor: "pointer", "text-decoration": "underline" })
                    .attr("title", __("Bấm để thử lại"))
                    .on("click.al_glassretry", () => this._retry_glass_price(entry));
            } else {
                entry.$price.css({ cursor: "", "text-decoration": "" }).removeAttr("title");
            }
        }
    }

    // ── Lấy giá cho 1 mã kính (dùng chung mọi nhánh) ──────────────
    _fetch_glass_price(entry, code, sourceWhenDone) {
        if (!entry || !code) return;
        this._render_glass_state(entry, { source: sourceWhenDone, price: { state: "loading" } });
        const requester = this._glass_price_requester_instance(entry);
        if (!requester) {
            // Dòng chưa lưu (name dạng "new-...") → server chưa có dòng để tra.
            this._render_glass_state(entry, { source: sourceWhenDone, price: { state: "unsaved" } });
            return;
        }
        requester.request(code, (info) => {
            // Người dùng đã đổi sang mã khác trong lúc chờ → bỏ kết quả cũ.
            const current = String(entry.display_code || "").trim();
            if (current !== String(info.code || code)) return;
            if (info.ok && info.name) entry.display_name = info.name;
            this._render_glass_state(entry, { source: sourceWhenDone, price: info });
        });
    }

    _retry_glass_price(entry) {
        if (!entry) return;
        const code = String((entry.ctrl && entry.ctrl.get_value()) || entry.display_code || "").trim();
        if (!code) return;
        this._fetch_glass_price(entry, code, entry.source || "override");
    }

    // ── Đổi mã kính trên dialog → lấy giá mã mới ──────────────────
    _on_glass_code_change(entry) {
        if (!entry || !entry.ctrl) return;
        const code = String(entry.ctrl.get_value() || "").trim();
        if (!code) {
            // Xoá trắng → hiện lại mã engine VẪN đang dùng (mã giữ chỗ, rồi
            // tới mã mặc định của BOM) — "luôn thấy mã kính" của Owner.
            const fb = alumglass.glass_pick.fallback_after_clear(
                entry.group, entry.placeholder_code);
            entry.display_code = fb.code;
            // Tên kính chỉ dùng khi mã fallback ĐÚNG là mã engine đã mô tả tên
            // (server trả `effective_name` cho `effective_code`).
            const g = entry.group || {};
            const serverCode = alumglass.glass_pick._first_non_empty(g.effective_code, g.default);
            entry.display_name = (fb.code && serverCode === fb.code) ? (g.effective_name || "") : "";
            entry.is_glass_master = fb.is_glass_master;
            // Ô phải HIỆN LẠI mã đó (không chỉ dòng trạng thái) — nếu không
            // người dùng thấy ô trống trong khi giá theo mã mặc định. Chỉ nhét
            // mã THẬT của danh mục vào Link; `set_value` lập trình không bắn
            // `change` nên không lặp lại handler này.
            if (fb.code && fb.is_glass_master) entry.ctrl.set_value(fb.code);
            const price = alumglass.glass_pick.price_for_initial(fb.code, entry.group);
            if (price === null) {
                this._fetch_glass_price(entry, fb.code, fb.source);
            } else {
                this._render_glass_state(entry, { source: fb.source, price: price });
            }
            return;
        }
        // Mã chọn từ Link → luôn là kính thật trong danh mục.
        entry.display_code = code;
        entry.display_name = "";
        entry.is_glass_master = true;
        this._fetch_glass_price(entry, code, "override");
    }

    // Mỗi Ô KÍNH có bộ hẹn giờ riêng — dùng chung 1 requester thì 2 ô cùng
    // lấy giá sẽ huỷ lẫn nhau (ô trước treo ở "Đang lấy giá..." mãi mãi).
    _glass_price_requester_instance(entry) {
        if (!entry) return null;
        const name = (this.child_doc && this.child_doc.name) || "";
        if (!name || name.indexOf("new-") === 0) return null;
        if (!entry._price_requester) {
            entry._price_requester = alumglass.glass_pick.make_price_requester({
                quotation_item_name: name,
            });
        }
        return entry._price_requester;
    }

    // Bind "đổi mã kính" với namespace riêng — re-render bind lại không nhân
    // đôi handler. Chọn từ autocomplete thường bắn cả `change` lẫn
    // `awesomplete-selectcomplete`; debounce gộp thành 1 lần gọi.
    _bind_glass_price_listener(entry) {
        if (!entry || !entry.ctrl || !entry.ctrl.$input) return;
        const self = this;
        entry.ctrl.$input
            .off("change.al_glassprice awesomplete-selectcomplete.al_glassprice")
            .on("change.al_glassprice awesomplete-selectcomplete.al_glassprice",
                function () { self._on_glass_code_change(entry); });
    }

    // Huỷ lượt auto-preview đang chờ (timer 700ms).
    _cancel_auto_preview() {
        if (this._auto_preview_timer) {
            clearTimeout(this._auto_preview_timer);
            this._auto_preview_timer = null;
        }
    }

    // Chữ ký lựa chọn kính ĐANG HIỆN trên dialog (mã hiện ở từng ô Link).
    // Xem `alumglass.glass_pick.glass_signature`.
    _glass_current_signature() {
        return alumglass.glass_pick.glass_signature(this._glass_controls || []);
    }

    // "Đã áp dụng": preview tính giá xong → hết trạng thái chờ.
    // `capturedSig` = chữ ký đã CHỤP lúc lượt tính giá đó bắt đầu. Chỉ gắn
    // nhãn khi chữ ký hiện tại vẫn ĐÚNG là chữ ký đó — người dùng đổi kính
    // giữa lúc tính thì kết quả vừa về là của mã CŨ, gắn "Đã áp dụng" sẽ
    // khiến nút 💾 Lưu đóng dialog với giá cũ.
    // Không có ngoại lệ "không rõ chữ ký": mọi lượt đều phải chụp được chữ
    // ký (job nền mở lại từ phiên trước chụp lúc gắn lại listener — xem
    // `_render_preview_panel`). Thiếu tham số ⇒ ⛔ không gắn.
    // Trả true = đã gắn nhãn (rate khớp mã đang hiện), false = chưa.
    _mark_glass_applied(capturedSig) {
        const current = this._glass_current_signature();
        if (!alumglass.glass_pick.should_mark_applied(current, capturedSig)) return false;
        this._glass_applied_signature = current;
        (this._glass_controls || []).forEach(entry => {
            if (entry.source !== "override" && entry.source !== "pending") return;
            entry.source = "applied";
            // Không truyền price → giữ nguyên dòng giá đang hiện.
            this._render_glass_state(entry, {});
        });
        return true;
    }

    // Lượt tính giá vừa xong → chốt trạng thái kính rồi đánh thức chỗ đang
    // chờ (nút 💾 Lưu). Kính đã đổi giữa lượt ⇒ ⛔ không đánh thức mà tính
    // lại NGAY cho mã mới (không chờ debounce 700ms), giữ "Đang áp dụng…".
    // Trả true khi đã chốt xong (rate khớp mã đang hiện).
    _finish_preview_with_glass(capturedSig) {
        if (this._mark_glass_applied(capturedSig)) {
            this._finish_preview_waiters();
            return true;
        }
        this._cancel_auto_preview();
        if (this.dialog && this._dialog_open) {
            this._run_preview(false);
            return false;
        }
        // Dialog đã đóng → không chạy lại được; mở khoá chỗ chờ để nút Lưu thoát.
        this._finish_preview_waiters();
        return false;
    }

    // Có mã kính vừa đổi/xoá mà preview CHƯA chạy xong? (rate còn theo mã cũ)
    // So chữ ký hiện tại với chữ ký của lần tính giá THÀNH CÔNG gần nhất —
    // phủ cả xoá trắng ô kính lẫn đổi kính trong lúc preview đang chạy.
    _needs_glass_recalc() {
        if (!this._glass_controls || !this._glass_controls.length) return false;
        return alumglass.glass_pick.needs_recalc(
            this._glass_current_signature(), this._glass_applied_signature);
    }

    // Chạy preview NGAY (bỏ qua debounce) và chờ xong (tối đa `maxMs`) — dùng
    // cho nút 💾 Lưu: đóng dialog chỉ sau khi rate đã theo mã kính vừa chọn.
    // `skipRun` = đã có lượt tính giá đang chạy dở → chỉ CHỜ, không bắn thêm
    // request thứ 2 cho cùng một thay đổi.
    // `skipSync` = dòng ĐÃ được ghi xuống DB ngay trước đó → `_run_preview`
    // không ghi lại lần 2. Nút 💾 Lưu KHÔNG còn tự ghi DB (chỉ sửa dòng trên
    // form) nên nó gọi hàm này KHÔNG kèm `skipSync`.
    _preview_and_wait(maxMs, skipRun, skipSync) {
        return new Promise((resolve) => {
            let done = false;
            const finish = () => {
                if (done) return;
                done = true;
                clearTimeout(timer);
                resolve();
            };
            const timer = setTimeout(() => {
                // Quá hạn (server treo) → mở khoá để lần Lưu sau không chờ vô ích.
                this._preview_inflight = false;
                finish();
            }, maxMs || 20000);
            this._preview_waiters = this._preview_waiters || [];
            this._preview_waiters.push(finish);
            if (!skipRun) this._run_preview(false, skipSync);
        });
    }

    // Preview kết thúc (thành công HAY lỗi) → đánh thức mọi chỗ đang chờ.
    _finish_preview_waiters() {
        this._preview_inflight = false;
        const list = this._preview_waiters || [];
        this._preview_waiters = [];
        list.forEach(fn => { try { fn(); } catch (e) { /* ignore */ } });
    }

    // Báo "tính lại không xong" bằng câu người-đọc-được (⛔ không phơi lỗi
    // kỹ thuật). Câu nằm ở `glass_pick.RECALC_FAILED_MESSAGE` để test được.
    _alert_recalc_failed() {
        frappe.show_alert({
            message: alumglass.glass_pick.RECALC_FAILED_MESSAGE,
            indicator: "orange",
        }, 10);
    }

    // Nút 💾 Lưu: cập nhật dòng Quotation Item TRÊN FORM + đánh dấu phiếu
    // "có thay đổi". ⛔ KHÔNG ghi DB — DB chỉ được ghi khi người dùng bấm
    // Lưu phiếu Quotation (yêu cầu Owner 2026-11-21:
    // "lưu dialog phải ghi xuống dòng quotation item, lưu phiếu mới lưu vào db").
    // Ngoại lệ DUY NHẤT là nhánh cần tính lại giá kính: server đọc
    // `al_bom_vars` từ DB nên `_run_preview` vẫn sync dòng xuống DB trước khi
    // gọi engine (yêu cầu kỹ thuật của engine, không phải "lưu phiếu").
    _on_primary_action() {
        // `notify: true` = người dùng bấm 💾 Lưu ⇒ báo "đã cập nhật dòng" để
        // họ biết thao tác đã chạy và bước tiếp theo là Lưu phiếu. Các đường
        // gọi `_save()` khác (auto-preview, Preview tính giá) ⛔ không báo.
        this._save({ notify: true });
        // `_save()` ghi qua `frappe.model.set_value`; object trong
        // `frm.doc.items` có thể là object KHÁC ⇒ ghi lại tường minh để lưới
        // và lần Lưu phiếu sau chắc chắn mang tham số vừa sửa. `_save()` đã
        // gọi hàm này; gọi lại là idempotent (cùng nguồn giá trị từ dialog).
        this._apply_row_to_form();
        // Đánh dấu phiếu có thay đổi + vẽ lại lưới (nút Lưu của phiếu bật).
        if (this.frm) {
            if (typeof this.frm.dirty === "function") this.frm.dirty();
            if (this.frm.refresh_field) this.frm.refresh_field("items");
        }

        const current = this._glass_current_signature();
        // Lượt đang chạy đã chụp ĐÚNG lựa chọn kính HIỆN TẠI chưa? Khác chữ ký
        // nghĩa là kết quả sắp về là của mã CŨ ⇒ phải chạy lượt mới — kể cả khi
        // lựa chọn hiện tại trùng bản đã áp dụng (người dùng đổi đi rồi đổi lại
        // trong lúc lượt cũ đang chạy: rate sắp bị ghi đè bằng mã trung gian).
        const staleInflight = !!(this._glass_controls && this._glass_controls.length)
            && this._preview_inflight
            && alumglass.glass_pick.needs_recalc(current, this._preview_signature);
        // Chốt NGAY — `_needs_glass_recalc()` đọc chữ ký lựa chọn kính HIỆN TẠI.
        const mustRecalc = this._needs_glass_recalc() || staleInflight;

        const self = this;
        if (!mustRecalc) {
            // Không có gì phải tính lại ⇒ đóng NGAY, ⛔ không chờ mạng.
            if (self.dialog) self.dialog.hide();
            return Promise.resolve();
        }
        // Huỷ timer auto-preview 700ms đang treo (nếu có) — ta tính giá NGAY,
        // chạy thêm lần nữa là tính 2 lần cho cùng một thay đổi.
        self._cancel_auto_preview();
        const waitOnly = self._preview_inflight && !staleInflight;
        const $btn = (self.dialog && typeof self.dialog.get_primary_btn === "function")
            ? self.dialog.get_primary_btn() : null;
        if ($btn && $btn.length) $btn.prop("disabled", true).text(__("Đang tính giá..."));
        // ⛔ KHÔNG truyền `skipSync`: dòng CHƯA ghi DB (nút Lưu chỉ sửa form),
        // mà engine đọc `al_bom_vars` từ DB ⇒ `_run_preview` phải sync trước
        // khi gọi server. Thứ tự: dòng trên form → sync → preview → đóng.
        return self._preview_and_wait(20000, waitOnly).then(() => {
            if (self._needs_glass_recalc()) {
                // Tính lại KHÔNG xong (server lỗi / quá 20s) ⇒ đóng im lặng sẽ
                // khiến người dùng tưởng giá đã theo kính mới. Nói rõ trạng thái
                // + đúng việc cần làm (mở lại rồi bấm "Preview tính giá").
                if (self.dialog) self.dialog.hide();
                self._alert_recalc_failed();
                return;
            }
            if (self.dialog) self.dialog.hide();
        });
    }

    // ── Nguồn giá trị của dòng: DIALOG là số một ───────────────────
    // Đọc giá trị hiện tại của 1 field NGAY TRÊN DIALOG (nguồn sự thật khi
    // người dùng vừa sửa). Chịu được cả 3 tình huống thực tế:
    //   - dialog chưa/không có `get_value` (object giả, dialog đã đóng);
    //   - field KHÔNG nằm trong dialog (Frappe ném TypeError cho fieldname lạ);
    //   - `get_value` ném lỗi ⇒ đọc thẳng `fields_dict[fn].get_value()`.
    // Trả `undefined` = "không đọc được" — bên gọi phải rơi về nguồn khác,
    // ⛔ tuyệt đối không coi "không đọc được" là "rỗng" (sẽ xoá mất giá trị).
    _dialog_field_value(fieldname) {
        const dlg = this.dialog;
        if (!dlg) return undefined;
        let val;
        if (typeof dlg.get_value === "function") {
            try { val = dlg.get_value(fieldname); } catch (e) { val = undefined; }
        }
        if ((val === undefined || val === null) && dlg.fields_dict && dlg.fields_dict[fieldname]
            && typeof dlg.fields_dict[fieldname].get_value === "function") {
            try { val = dlg.fields_dict[fieldname].get_value(); } catch (e) { val = undefined; }
        }
        return val;
    }

    // Dòng tương ứng trong `frm.doc.items` — dò theo `name`, không thấy thì
    // theo `idx` (dòng mới chưa có `name` thật).
    _find_form_row() {
        const src = this.child_doc || {};
        const rows = (this.frm && this.frm.doc && this.frm.doc.items) || [];
        let row = src.name ? rows.find(r => r && r.name === src.name) : null;
        if (!row && src.idx) row = rows.find(r => r && r.idx === src.idx);
        return row || null;
    }

    // Gom 5 field then chốt của dòng. Thứ tự nguồn cho từng field:
    //   DIALOG → `extra` (mã sản phẩm đại diện của BOM) → `child_doc` →
    //   dòng đang có trên phiếu (GIỮ giá trị cũ) → "".
    // Nhờ vậy dialog đọc không ra ⛔ không xoá mất giá trị dòng đang có.
    // Ngoại lệ DUY NHẤT: `al_bom_vars` — luôn ghi theo biến vừa thu thập.
    _collect_row_values() {
        const src = this.child_doc || {};
        const existing = this._find_form_row() || {};
        const blank = (v) => v === undefined || v === null || String(v).trim() === "";
        const keep = (fieldname, extra) => {
            let v = this._dialog_field_value(fieldname);
            if (blank(v)) v = extra;
            if (blank(v)) v = src[fieldname];
            if (blank(v)) v = existing[fieldname];
            return blank(v) ? "" : v;
        };
        const bom = keep("al_bom");
        // item_code/item_name: mã sản phẩm THẬT của BOM (A8) — chỉ áp khi đã
        // có BOM, ⛔ không clobber item người dùng tự nhập.
        const meta = bom ? (this._bom_meta || null) : null;
        return {
            al_bom: bom,
            al_bom_version: keep("al_bom_version"),
            al_bom_vars: blank(src.al_bom_vars)
                ? (blank(existing.al_bom_vars) ? "{}" : existing.al_bom_vars)
                : src.al_bom_vars,
            item_code: keep("item_code", meta && meta.item_code),
            item_name: keep("item_name", meta && meta.item_name),
        };
    }

    // Ghi 1 field xuống dòng qua `frappe.model.set_value` — API chuẩn: cập nhật
    // `locals`, bắn sự kiện change, đánh dấu `__unsaved`. Bỏ qua khi giá trị
    // KHÔNG đổi để ⛔ không bắn change handler vô ích (item_code có handler
    // reset giá). Trả true nếu có ghi.
    _write_row_field(cdt, cdn, fieldname, value) {
        const prev = this.child_doc ? this.child_doc[fieldname] : undefined;
        const same = String(prev === undefined || prev === null ? "" : prev)
            === String(value === undefined || value === null ? "" : value);
        if (same) return false;
        frappe.model.set_value(cdt, cdn, fieldname, value);
        if (this.child_doc) this.child_doc[fieldname] = value;
        return true;
    }

    // Ghi các field then chốt của dialog vào dòng Quotation Item NẰM TRONG
    // `frm.doc.items` (bộ nhớ trình duyệt) — KHÔNG ghi DB.
    // Giá trị đọc từ CHÍNH DIALOG (`_collect_row_values`), ⛔ không chỉ từ
    // `this.child_doc`: dialog có thể mở trên `innerFrm` và `child_doc` là
    // object cũ/khác ⇒ dòng lưới giữ giá trị cũ (lỗi "đổi BOM Version mà
    // dòng không đổi"). Ghi vào CẢ HAI object, mỗi object đúng 1 lần.
    _apply_row_to_form() {
        const src = this.child_doc || {};
        const cdt = src.doctype || "Quotation Item";
        const cdn = src.name;
        const idx = src.idx;
        const values = this._collect_row_values();
        // Hai object có thể TRÙNG nhau → chỉ ghi 1 lần.
        const targets = [];
        const add = (row) => { if (row && targets.indexOf(row) < 0) targets.push(row); };
        if (cdn && !String(cdn).startsWith("new-") && !src.__islocal) {
            add(frappe.get_doc(cdt, cdn));
        }
        add(this._find_form_row());
        targets.forEach((target) => {
            Object.keys(values).forEach((field) => { target[field] = values[field]; });
        });
        return targets;
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
            // Trạng thái tự giải thích + LỐI XỬ LÝ: dòng còn "Queued" từ lần mở
            // form trước (worker chết/treo) → user biết phải bấm tính lại thay
            // vì ngồi chờ mãi một kết quả không bao giờ tới.
            $container.html(this._preview_progress_html(
                __("BOM đang xếp hàng tính trong nền — kết quả sẽ tự hiện khi xong. Nếu chờ lâu mà chưa thấy kết quả, bấm nút 'Preview tính giá' để tính lại.")
            ));
            // Job nền đã chạy SAU `_sync_row_to_db` ⇒ lựa chọn kính đang hiện
            // khi mở lại chính là lựa chọn của job. Chụp chữ ký NGAY ĐÂY làm
            // chữ ký của job: người dùng đổi kính sau đó thì chữ ký lệch ⇒
            // kết quả cũ về muộn không được gắn "Đã áp dụng".
            if (job_id) this._listen_realtime(job_id, $container, this._glass_current_signature());
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
    // `capturedSig` = chữ ký lựa chọn kính lúc job được gửi đi (xem
    // `_finish_preview_with_glass`): kết quả nền về muộn mà người dùng đã đổi
    // kính thì ⛔ không được gắn "Đã áp dụng".
    _listen_realtime(job_id, $container, capturedSig) {
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
                // Kết quả mới vừa về → force = true để cảnh báo (vượt khổ kính...)
                // hiện ngay, không bị dedupe chặn.
                self._render_display_model($container, self.child_doc.name, true);
                // Kính đã đổi giữa lúc job chạy ⇒ ⛔ không gắn "Đã áp dụng"
                // (kết quả là của mã cũ) mà tính lại NGAY cho mã mới.
                const applied = self._finish_preview_with_glass(capturedSig);
                if (applied) {
                    frappe.show_alert({ message: __("Tính giá xong"), indicator: "green" });
                }
            } else {
                if (self.child_doc.name) {
                    frappe.model.set_value(self.child_doc.doctype || "Quotation Item",
                        self.child_doc.name, "al_calc_status", "Failed");
                }
                self.child_doc.al_calc_status = "Failed";
                self.child_doc.al_calc_error = data.error || "";
                $container.html(self._preview_error_html(data.error || ""));
                self._finish_preview_waiters();
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

    // D2: `al_calc_error` có thể là stack trace (bản CŨ đã lưu trong DB) →
    // chỉ hiện câu tiếng Việt ngắn + lối xử lý; trace đẩy vào khối <details>
    // ẩn (còn để chẩn đoán), ⛔ không phơi ra màn hình.
    _preview_error_html(error) {
        const info = alumglass.sanitize_calc_error(error);
        const safe_error = info.message ? this._esc_html(info.message) : "";
        const trace_html = info.trace
            ? `<details style="margin-top:8px;text-align:left;"><summary style="cursor:pointer;font-size:11px;color:#94a3b8;">${__("Chi tiết kỹ thuật (gửi cho quản trị khi cần)")}</summary>
                <pre style="font-size:11px;max-height:200px;overflow:auto;">${this._esc_html(info.trace)}</pre></details>`
            : "";
        return `<div style="padding:12px;color:#ef4444;text-align:center;">
            ❌ ${__("Tính giá thất bại")}
            ${safe_error ? `<p style="margin-top:8px;">${safe_error}</p>` : ""}
            <p style="margin:6px 0 0;color:#64748b;font-size:12px;">${__("Bấm nút 'Preview tính giá' để thử lại. Nếu vẫn lỗi, báo quản trị.")}</p>
            ${trace_html}
        </div>`;
    }

    // `manual` = true khi user bấm nút "🖥️ Preview tính giá" (mong đợi dialog
    // cuộn xuống xem kết quả ngay). `manual` = false/undefined khi được gọi
    // tự động từ `_schedule_auto_preview()` (đổi kính/tham số) — KHÔNG được
    // cuộn dialog, để con trỏ/vị trí đang nhập của user đứng nguyên, cho phép
    // gõ tiếp các trường khác trong lúc kết quả tự tính lại ở nền.
    // `skipSync` = true khi dòng ĐÃ được ghi xuống DB ngay trước lượt này
    // → ⛔ không ghi lại lần 2.
    _run_preview(manual, skipSync) {
        // Đánh dấu đang tính — nút 💾 Lưu sẽ CHỜ lượt này thay vì bắn thêm.
        // Lượt này chụp tham số NGAY BÂY GIỜ (qua _save bên dưới) → chụp luôn
        // chữ ký lựa chọn kính để lúc kết quả về biết mình tính cho mã nào.
        this._preview_inflight = true;
        const capturedSig = this._glass_current_signature();
        this._preview_signature = capturedSig;
        // Hiển thị trạng thái loading (thay luôn badge "đang chờ" nếu có)
        const $container = this._preview_container();
        if ($container.length) {
            $container.html(this._preview_progress_html(__("Đang tính toán...")));
            if (manual) {
                $container[0].scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }

        const self = this;
        // Lưu tham số vào model TRÊN TRÌNH DUYỆT trước (vars, glass_master_map...)
        this._save();

        // Nếu chưa có BOM, báo lỗi. Đọc qua helper chịu lỗi: `get_value` của
        // Frappe ném TypeError nếu fieldname lạ, ⛔ không để nó làm chết Lưu.
        const bom = this._dialog_field_value("al_bom") || this.child_doc.al_bom;
        if (!bom) {
            if ($container.length) {
                $container.html(this._preview_error_html(__("Vui lòng chọn BOM trước khi Preview")));
            }
            this._finish_preview_waiters();
            return;
        }

        const cdt = this.child_doc.doctype || "Quotation Item";
        const cdn = this.child_doc.name;
        // seq tăng mỗi lần gọi preview — nếu 1 preview cũ hơn trả về SAU 1
        // preview mới hơn (VD user đổi kính liên tục), kết quả cũ bị bỏ qua.
        const seq = ++this._preview_seq;

        // Dòng đã được ghi xuống DB ngay trước lượt này → gọi thẳng engine,
        // KHÔNG ghi DB lần 2 cho cùng một thay đổi.
        if (skipSync) {
            this._exec_calculate_bom($container, seq, manual, capturedSig);
            return;
        }

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
                self._exec_calculate_bom($container, seq, manual, capturedSig);
            })
            .catch((err) => {
                if (seq !== self._preview_seq) return;
                if ($container.length) {
                    $container.html(self._preview_error_html(
                        __("Không lưu được dữ liệu dòng trước khi tính giá") + ": "
                        + String((err && err.message) || err || "")));
                }
                self._finish_preview_waiters();
            });
    }

    // Gọi API calculate_bom SAU KHI dữ liệu dòng đã đồng bộ xuống DB.
    // Tách riêng để `_run_preview` giữ ngắn gọn + tái dùng seq-guard.
    // `manual` (xem `_run_preview`) chỉ dùng để quyết định CÓ popup lỗi-cảnh báo.
    // `capturedSig` = chữ ký lựa chọn kính lúc lượt này bắt đầu — kết quả về
    // chỉ được gắn "Đã áp dụng" nếu chữ ký hiện tại vẫn đúng là nó.
    _exec_calculate_bom($container, seq, manual, capturedSig) {
        const self = this;
        if (!$container || !$container.length) $container = this._preview_container();

        frappe.call({
            method: "alumglass.api.calculate_bom",
            args: { quotation_item_name: this.child_doc.name },
            callback: (r) => {
                if (seq !== self._preview_seq) return; // stale — có preview mới hơn đã chạy
                if (!$container.length) {
                    // Dialog đã đóng/không còn panel preview → đừng treo chỗ chờ.
                    self._finish_preview_waiters();
                    return;
                }
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
                        self._listen_realtime(r.message.job_id, $container, capturedSig);
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
                        // Đọc `errors` qua get_result_display (nguồn duy nhất có
                        // errors cho cả 2 đường sync/async) — xem _render_display_model.
                        self._render_display_model($container, self.child_doc.name, manual);
                        // Tính xong → trạng thái kính "Đang áp dụng" → "Đã áp dụng"
                        // (chỉ khi kính chưa bị đổi giữa lúc tính — xem hàm).
                        self._finish_preview_with_glass(capturedSig);
                    }
                } else {
                    $container.html(self._preview_error_html(__("Không có kết quả. Kiểm tra lại tham số đầu vào.")));
                    self._finish_preview_waiters();
                }
            },
            error: (err) => {
                if (seq !== self._preview_seq) return;
                if ($container.length) {
                    // Đưa nguyên err (không String() trước) để sanitize rút câu
                    // người-đọc-được từ object response lỗi.
                    $container.html(self._preview_error_html(err));
                }
                self._finish_preview_waiters();
            },
        });
    }

    // Render preview TỐI ƯU: lấy display model (label + công thức) từ server
    // rồi render qua `alumglass.render_bom_result_display` — renderer dùng chung.
    // `force_notify` = user vừa chủ động bấm tính / vừa có kết quả mới về → luôn
    // popup lỗi-cảnh báo; mở lại panel xem kết quả CŨ thì chỉ hiện banner.
    _render_display_model($container, qi_name, force_notify) {
        const self = this;
        if (!$container || !$container.length) $container = this._preview_container();
        if (!$container.length) return;
        if (!qi_name) return;
        // Dòng Quotation Item đang mở — cần cho nút "Vì sao ra số này?" của
        // từng dòng vật tư (dialog giải thích cần biết tra ở dòng nào).
        const qi_ref = (this.child_doc && this.child_doc.name) || qi_name;

        frappe.call({
            method: "alumglass.api.get_result_display",
            args: { quotation_item_name: qi_name },
            callback: (r) => {
                if (!$container || !$container.length) return;
                if (r.message && r.message.summary && r.message.summary.calculated) {
                    // F2: `errors` (kính VƯỢT khổ tối đa, lỗi công thức...) nay
                    // được dán ngay TRÊN bảng kết quả + popup một lần — trước
                    // đây frontend bỏ qua hoàn toàn nên báo giá sai không ai biết.
                    $container.html(alumglass.calc_errors_banner(r.message.errors)
                        + alumglass.render_bom_result_display(r.message, {
                            compact: true, show_trace: false,
                            quotation_item: qi_ref,
                        }));
                    alumglass.notify_calc_errors(r.message.errors, {
                        dedupe_key: qi_name, force: !!force_notify,
                    });
                    return;
                }
                // Server trả display trống (chưa tính / chưa lưu) — fallback raw nếu có
                let raw = null;
                try { raw = JSON.parse(self.child_doc.al_bom_result || "{}"); } catch (e) { /* ignore */ }
                if (raw && (raw.lines || raw.cost_template)) {
                    // F2: al_bom_result trong tay cũng có thể mang `errors` → vẫn dán banner
                    $container.html(alumglass.calc_errors_banner(raw.errors)
                        + alumglass.render_bom_result_display(
                            alumglass.raw_to_display(raw), {
                                compact: true, show_trace: false,
                                quotation_item: qi_ref,
                            }));
                } else {
                    $container.html(self._preview_progress_html(__("Đang tải kết quả...")));
                }
            },
            error: (err) => {
                if ($container && $container.length) {
                    $container.html(self._preview_error_html(err));
                }
            },
        });
    }

    // Fallback đồng bộ (giữ chân cho code cũ): render raw qua renderer dùng chung.
    _build_preview_html(data) {
        return alumglass.render_bom_result_display(
            alumglass.raw_to_display(data), {
                compact: true, show_trace: false,
                quotation_item: (this.child_doc && this.child_doc.name) || "",
            });
    }

    // ── Parse existing al_bom_vars JSON ────────────────────────────
    _parse_existing() {
        try { return JSON.parse(this.child_doc.al_bom_vars || "{}"); } catch (e) { return {}; }
    }

    // ── Escape helper ─────────────────────────────────────────────
    _esc_html(str) {
        return String(str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    _save(opts) {
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

        // ── Color per-line map (color_groups) — Q2 ───────────────────
        // Lưu `color_master_map: {rep: actual}` vào al_bom_vars. Backward-
        // compat: không có map → engine vẫn đọc `aluminum_color` global
        // (nếu user đặt qua biến cũ).
        if (this._color_controls && this._color_controls.length) {
            const colorMap = {};
            let anyColorSet = false;
            this._color_controls.forEach(({ rep, ctrl }) => {
                const v = ctrl.get_value();
                if (v !== undefined && v !== null && String(v).trim() !== "") {
                    colorMap[rep] = v;
                    anyColorSet = true;
                }
            });
            if (anyColorSet) vars.color_master_map = colorMap;
        }

        // ── Thu thập extra vars từ Table field chuẩn Frappe ────────
        vars.extra_vars = {};
        const extra_rows = (this.dialog && this.dialog.fields_dict?.["extra_vars"]?.df.data) || [];
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
        // ⛔ KHÔNG ghi DB ở đây: chỉ cập nhật dòng TRÊN PHIẾU (bộ nhớ trình
        // duyệt) + đánh dấu phiếu "có thay đổi". DB chỉ ghi khi người dùng
        // bấm Lưu phiếu (yêu cầu Owner 2026-11-21). Ngoại lệ duy nhất là
        // nhánh cần engine tính giá — `_run_preview` tự sync trước khi gọi
        // server, không phải việc của hàm này.
        const cdt = this.child_doc.doctype || "Quotation Item";
        const cdn = this.child_doc.name;
        const vars_json = JSON.stringify(vars, null, 2);
        if (cdn) {
            // `al_bom_vars` LUÔN ghi (nguồn: biến vừa thu thập từ dialog).
            this._write_row_field(cdt, cdn, "al_bom_vars", vars_json);
            // 4 field còn lại: đọc từ CHÍNH DIALOG (`_collect_row_values`
            // rơi về `child_doc`/dòng hiện có khi dialog không trả giá trị).
            // Đây là chỗ sửa lỗi "đổi BOM Version trong dialog mà dòng vẫn
            // giữ giá trị cũ": trước đây chỉ đọc `dialog.get_value` và bỏ qua
            // khi rỗng, còn `_apply_row_to_form` lại chép `child_doc` cũ đè
            // lên dòng lưới.
            const values = this._collect_row_values();
            ["al_bom", "al_bom_version", "item_code", "item_name"].forEach((fn) => {
                this._write_row_field(cdt, cdn, fn, values[fn]);
            });
        }
        // Ghi thẳng xuống object dòng trong `frm.doc.items` (lưới + lần Lưu
        // phiếu sau đọc từ đây) — idempotent với `_write_row_field`. Gọi NGOÀI
        // khối `if (cdn)`: dòng chưa có `name` thật vẫn phải nhận giá trị
        // (dò theo `idx`).
        this._apply_row_to_form();

        // Phiếu phải mang cờ "có thay đổi" để nút Lưu phiếu bật — kể cả khi
        // chỉ có `al_bom_vars` đổi (giá trị mới giống hệt giá trị cũ).
        if (this.frm && this.frm.doc && !this.frm.doc.__unsaved) {
            this.frm.doc.__unsaved = 1;
        }

        // Phản hồi nhìn thấy được — CHỈ khi người dùng bấm 💾 Lưu (⛔ không
        // báo ở đường auto-preview). Nói rõ bước tiếp theo để người dùng
        // không tưởng đã ghi DB xong.
        if (opts && opts.notify && cdn) {
            const is_new = String(cdn).indexOf("new-") === 0
                || !!(this.child_doc && this.child_doc.__islocal);
            frappe.show_alert({
                message: is_new
                    ? __("Đã lưu dòng mới — phiếu sẽ được lưu khi bạn bấm Lưu phiếu.")
                    : __("Đã cập nhật dòng trên phiếu — bấm Lưu phiếu để ghi lại."),
                indicator: "green",
            }, 5);
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

        const valOf = fieldname => this._dialog_field_value(fieldname);
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
        // Thêm LỐI XỬ LÝ: job nền có thể đã chết (worker restart) → user biết
        // phải đóng và tính lại thay vì chờ vô hạn.
        this._set_html(`<div class="alert alert-info" style="margin-bottom:0;"
            data-job="${frappe.utils.escape_html(job_id || "")}">
            <i class="fa fa-spinner fa-spin"></i>
            ${message || __("Đang tính BOM lớn trong nền — có thể mất vài phút...")}
            <div style="margin-top:6px;font-size:12px;">${__("Nếu chờ lâu mà chưa thấy kết quả, đóng cửa sổ này rồi bấm lại nút tính giá để chạy lại.")}</div>
        </div>`);
    }

    // D2: `al_calc_error` có thể là stack trace (bản CŨ trong DB) → ⛔ không
    // render thẳng ra màn hình; trace chỉ nằm trong khối <details> ẩn.
    _render_error(error) {
        const info = alumglass.sanitize_calc_error(error);
        const safe_error = info.message ? frappe.utils.escape_html(info.message) : "";
        const trace_html = info.trace
            ? `<details style="margin-top:8px;"><summary style="cursor:pointer;font-size:11px;color:#94a3b8;">${__("Chi tiết kỹ thuật (gửi cho quản trị khi cần)")}</summary>
                <pre style="font-size:11px;max-height:200px;overflow:auto;">${frappe.utils.escape_html(info.trace)}</pre></details>`
            : "";
        this._set_html(`<div class="alert alert-danger" style="margin-bottom:0;">
            <strong>${__("Tính giá thất bại")}</strong><br>
            ${safe_error || __("Xem chi tiết trong Error Log hoặc trường AL Calc Error trên Quotation Item.")}
            <div style="margin-top:6px;font-size:12px;">${__("Đóng cửa sổ này rồi bấm lại nút tính giá để thử lại; nếu vẫn lỗi, báo quản trị.")}</div>
            ${trace_html}
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
                    // F2: lỗi/cảnh báo engine trả kèm (`errors`) → banner trên
                    // kết quả + popup (force: user vừa chủ động mở/tính).
                    self._set_html(alumglass.calc_errors_banner(r.message.errors)
                        + alumglass.render_bom_result_display(r.message, {
                            collapsible: true,
                            show_trace: true,
                            title: __("BOM Calculation Results"),
                            quotation_item: self.quotation_item_name,
                        }));
                    alumglass.notify_calc_errors(r.message.errors, {
                        dedupe_key: self.quotation_item_name, force: true,
                    });
                    return;
                }
                // Server không có display (chưa lưu DB) → fallback raw data trong tay
                // F2: raw data cũng có thể mang `errors` → vẫn phải dán banner
                self._set_html(alumglass.calc_errors_banner((data || {}).errors)
                    + alumglass.render_bom_result_display(
                        alumglass.raw_to_display(data), {
                            collapsible: true,
                            show_trace: true,
                            title: __("BOM Calculation Results"),
                            quotation_item: self.quotation_item_name,
                        }));
            },
            error: () => {
                // Lỗi mạng/API → vẫn render được bằng raw data (fallback)
                self._set_html(alumglass.render_bom_result_display(
                    alumglass.raw_to_display(data), {
                        collapsible: true,
                        show_trace: true,
                        title: __("BOM Calculation Results"),
                        quotation_item: self.quotation_item_name,
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
        // Báo giá đã Submit/huỷ → không gắn 2 nút dòng trong form con (Tham số BOM
        // / Preview tính giá): cả 2 đều dẫn tới đường GHI giá. Chốt THẬT ở SERVER;
        // docstatus ở đây chỉ đỡ mời người dùng bấm sai, KHÔNG phải lớp bảo vệ.
        if (innerFrm.doc.docstatus !== 0) return;

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

        // Báo giá đã Submit/huỷ → KHÔNG gắn nút dòng nào + KHÔNG gắn double-click:
        // cả 📐 (ItemParamDialog, auto-preview gọi calculate_bom) lẫn 🖥️
        // (BOMDialog, gọi calculate_bom) đều dẫn tới đường GHI giá. Chốt THẬT
        // nằm ở SERVER (b7_save_results + api.calculate_bom); docstatus ở đây chỉ
        // đỡ mời người dùng bấm sai, KHÔNG phải lớp bảo vệ.
        if (frm.doc.docstatus !== 0) return;

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
    // Chỉ mời bấm "Tính giá" khi báo giá còn Draft. Chốt THẬT nằm ở SERVER
    // (BomOrchestrator.b7_save_results + api.calculate_bom); docstatus ở đây chỉ
    // để đỡ mời người dùng bấm nút sẽ hỏng, KHÔNG phải lớp bảo vệ.
    if (frm.doc.docstatus === 0) {
        frm.add_custom_button(__("Tính giá"), function () { _calc_all_items(frm); }, __("AlumGlass"));
    }
    // "Preview giá" CHỈ ĐỌC (_preview_all_items → alumglass.api.get_result_display,
    // không ghi) ⇒ GIỮ NGUYÊN ở mọi trạng thái.
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
    // F2: gom cảnh báo/lỗi engine trả kèm để báo ở cuối (không popup từng dòng
    // giữa chừng — tính 20 dòng mà popup 20 lần thì không dùng được).
    const calc_issues = [];
    const total = rows.length;
    const finish = () => {
        frm.refresh_field("items");
        let msg = __("Đã tính {0}/{1} dòng", [done, total]);
        if (queued) msg += ` · ${__("{0} dòng chờ nền", [queued])}`;
        if (failed) msg += ` · ${__("{0} dòng lỗi", [failed])}`;
        frappe.show_alert({ message: msg, indicator: failed ? "red" : (queued ? "orange" : "green") });
        if (calc_issues.length) {
            const has_error = calc_issues.some((it) => it.severity === "error");
            const body = calc_issues.map((it) => `<li style="margin-bottom:4px;">${it.severity === "warning" ? "⚠️" : "⛔"} ${alumglass.esc(it.message)}</li>`).join("");
            frappe.msgprint({
                title: has_error
                    ? __("Tính giá có lỗi — cần xử lý trước khi chốt báo giá")
                    : __("Cảnh báo tính giá — cần xác nhận lại trước khi chốt báo giá"),
                message: `<ul style="padding-left:18px;margin:0;">${body}</ul>`,
                indicator: has_error ? "red" : "orange",
            });
        }
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
                        // F2: response đồng bộ hiện CHƯA có `errors` (engine
                        // _build_response chỉ trả buckets/cost_template/lines) —
                        // đọc phòng khi API bổ sung; thiếu thì bỏ qua an toàn.
                        alumglass.collect_calc_errors(r.message.errors).forEach((it) => {
                            calc_issues.push({
                                severity: it.severity,
                                message: `${row.item_code || row.item_name || realName}: ${it.message}`,
                            });
                        });
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
                            // D2: chỉ lưu câu người-đọc-được, không lưu stack trace
                            al_calc_error: alumglass.sanitize_calc_error(
                                (err && err.message) || err || "").message,
                        });
                        next(i + 1);
                    },
                });
            })
            .catch((err) => {
                failed++;
                frappe.model.set_value("Quotation Item", row.name, {
                    al_calc_status: "Failed",
                    al_calc_error: alumglass.sanitize_calc_error(
                        (err && err.message) || err || "").message,
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
                    // F2: cảnh báo/lỗi (kính vượt khổ...) hiện cả ở đây — "Preview
                    // giá toàn bộ" là đường hay dùng để soát cả báo giá.
                    const issues = alumglass.collect_calc_errors(r.message.errors);
                    const has_error = issues.some((it) => it.severity === "error");
                    $det.find(".al-pv-status")
                        .text(has_error ? __("Đã tính — có lỗi")
                            : (issues.length ? __("Đã tính — có cảnh báo") : __("Đã tính")))
                        .css("color", has_error ? "#dc2626" : (issues.length ? "#b45309" : ""));
                    $det.find(".al-pv-body").html(alumglass.calc_errors_banner(r.message.errors)
                        + alumglass.render_bom_result_display(r.message, {
                            collapsible: true,
                            show_trace: false,
                            compact: true,
                            // "Preview giá toàn bộ" cũng biết dòng → cho phép
                            // giải thích từng dòng vật tư ngay tại đây.
                            quotation_item: row.name,
                        }));
                } else {
                    $det.find(".al-pv-status").text(__("Chưa tính giá"));
                    // Nói theo trạng thái chứng từ: báo giá đã gửi/huỷ thì 2 nút
                    // "Tính giá"/"Tham số BOM" đã bị ẩn — không chỉ vào nút không còn.
                    let not_calculated_msg = __("Chưa tính giá cho sản phẩm này — bấm nút Tính giá hoặc mở Tham số BOM để tính.");
                    if (frm.doc.docstatus === 1) {
                        not_calculated_msg = __("Chưa tính giá cho sản phẩm này. Báo giá đã gửi khách nên không tính giá lại được.");
                    } else if (frm.doc.docstatus === 2) {
                        not_calculated_msg = __("Chưa tính giá cho sản phẩm này. Báo giá đã huỷ nên không tính giá được.");
                    }
                    $det.find(".al-pv-body").html(
                        `<p class="text-muted" style="margin:8px 0;">${not_calculated_msg}</p>`
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

// ── Node test hook ────────────────────────────────────────────────────────
// File này là doctype_js nạp trong trình duyệt (không có `module`). Khi nạp
// bằng `require()` trong test Node thuần thì trả namespace `alumglass` để
// kiểm các hàm thuần (glass_pick...).
if (typeof module !== "undefined" && module.exports) {
    module.exports = alumglass;
}