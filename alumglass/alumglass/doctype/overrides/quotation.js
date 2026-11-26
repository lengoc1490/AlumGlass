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

// Dấu phiên bản của tệp này — để kiểm nhanh trên site xem trình duyệt đã nạp
// bản mới chưa (gõ `alumglass.__build__` trong Console). Frappe nhúng tệp này
// vào form meta (`__js`) rồi CACHE ở Redis khi site tắt developer mode ⇒ kéo mã
// mới + `bench restart` KHÔNG đủ; `bench migrate` xoá cache qua
// `alumglass.setup.cache_bust.after_migrate`. Xem docs/ops/cap-nhat-ma-va-cache.md.
alumglass.__build__ = "2026-11-25d";
console.info("AlumGlass quotation.js build", alumglass.__build__);

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
// "Chưa tra được mã" — câu giải thích NGẮN cho `title` của cột Mã vật tư.
// Đọc `rule_missing_reason` server trả (additive: dữ liệu cũ không có ⇒ câu
// chung). ⛔ mã kỹ thuật (`row_gone`, `items.x.y`) trong câu người dùng đọc.
// ═══════════════════════════════════════════════════════════════════════════
alumglass.bom_nocode_reason = function (reason) {
    const r = String(reason || "").trim();
    if (r === "no_source_row") {
        return __("Quy tắc cần dữ liệu từ một dòng khác nhưng dòng đó chưa được chọn — mở dòng này trong BOM để chọn dòng lấy dữ liệu.");
    }
    if (r === "row_gone") {
        return __("Dòng lấy dữ liệu của quy tắc đã bị xoá — chọn lại dòng lấy dữ liệu trong BOM.");
    }
    if (r === "row_no_data") {
        return __("Dòng lấy dữ liệu chưa có số liệu quy tắc cần — nhập số liệu cho dòng đó rồi tính lại.");
    }
    if (r === "no_global_value") {
        return __("Lượt tính chưa có giá trị cho dữ liệu quy tắc đọc — kiểm tra tham số báo giá (chiều cao, số cánh…).");
    }
    return __("Quy tắc chưa ra được mã vật tư cho dòng này — bấm «?» để xem căn cứ.");
};

// ═══════════════════════════════════════════════════════════════════════════
// Nhãn người đọc cho MỘT dòng vật tư — dùng chung cho cột "Tên vật tư",
// tiêu đề dialog và aria. Thứ tự: tên dòng theo quy tắc (`line_label`) → tên
// vật tư (`item_name`) → mã → tên dòng BOM (`line_name`); ⛔ slug kỹ thuật
// (`kinh_tren`). Dữ liệu CŨ có thể đã ghi slug vào `label` ⇒ bỏ qua đúng giá
// trị trùng slug rồi mới rơi xuống "dòng vật tư" (⛔ hiện ô trống).
// ═══════════════════════════════════════════════════════════════════════════
alumglass.line_display_label = function (line) {
    const ln = line || {};
    const slug = String(ln.slug || "").trim();
    const candidates = [ln.label, ln.line_label, ln.item_name, ln.item_code, ln.line_name];
    for (let i = 0; i < candidates.length; i += 1) {
        const text = String(candidates[i] == null ? "" : candidates[i]).trim();
        if (!text) continue;
        if (slug && text === slug) continue; // slug cũ ⇒ ⛔ dùng làm nhãn
        return text;
    }
    return __("dòng vật tư");
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
    // Kết quả đang hiển thị (nếu caller truyền) → mỗi nút "Vì sao ra số này?"
    // giải thích đúng kết quả này thay vì bản (có thể CŨ) trong DB. Dòng MỚI
    // chưa có tên cũng nhờ vậy mở được nút.
    const explainKey = alumglass.register_explain_payload(
        opts.explain_result_json, opts.explain_parent);
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
            // Căn cứ CHỌN MÃ ngay dưới tên vật tư (thiết kế tra-cuu-quy-tac §3.5):
            // dòng nẹp/keo đọc được "tra độ dày kính … → quy tắc …" mà không phải
            // bấm nút "?". `rule_trace` do SERVER dựng sẵn bằng nhãn nghiệp vụ
            // (engine `_rule_trace_text`) ⇒ ⛔ không tự ghép lại từ rule_code /
            // items.<slug> ở client. Tối đa 2 dòng, hover (`title`) xem đầy đủ.
            // `qty_rule_trace` = căn cứ chọn SỐ LƯỢNG theo quy tắc (server thêm
            // sau) — ưu tiên nó, dữ liệu cũ chưa có thì rơi về `rule_trace`.
            const ruleTraceText = ln.qty_rule_trace || ln.rule_trace || "";
            const ruleTrace = ruleTraceText
                ? `<div class="al-bom-rule-trace" title="${alumglass.esc(ruleTraceText)}"
                        style="margin-top:2px;font-size:10px;color:#94a3b8;line-height:1.35;
                        display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
                        overflow:hidden;word-break:break-word;">${alumglass.esc(ruleTraceText)}</div>`
                : "";
            // Dòng CHỌN MÃ THEO QUY TẮC mà chưa ra mã ⇒ nói ĐÚNG trạng thái
            // ("Chưa tra được mã"), ⛔ phơi slug kỹ thuật (`kinh_tren`) ra cột
            // Mã. Dòng không phải Rule giữ hành vi cũ (slug nếu có).
            // `rule_input_missing` = dòng chọn mã theo quy tắc nhưng CHƯA khai
            // gì (không biểu thức, không biến) — vẫn là dòng Rule, ⛔ phơi slug.
            const isRuleLine = (ln.item_selection_mode === "Rule")
                || !!ln.rule_source_missing
                || !!ln.rule_input_missing;
            const hasCode = !!String(ln.item_code || "").trim();
            const codeCell = hasCode
                ? alumglass.esc(ln.item_code)
                : (isRuleLine
                    ? `<span class="al-bom-nocode" title="${alumglass.esc(
                        alumglass.bom_nocode_reason(ln.rule_missing_reason))}"
                        style="color:#b45309;font-weight:600;">${__("Chưa tra được mã")}</span>`
                    : alumglass.esc(ln.slug || "—"));
            // Nhãn người đọc cho mọi bề mặt (cột Tên, tiêu đề dialog, aria):
            // ⛔ slug. Dòng chưa có tên lẫn mã ⇒ "dòng vật tư".
            const lineLabel = alumglass.line_display_label(ln);
            const explainBtn = ((opts.quotation_item || explainKey) && ln.slug)
                ? `<button type="button" class="btn btn-xs btn-default al-bom-explain-btn"
                        style="font-size:16px;line-height:1;padding:0 4px;margin-left:6px;vertical-align:middle;color:#94a3b8;border:none;background:transparent;"
                        title="${alumglass.esc(__("Vì sao ra số này?"))}"
                        aria-label="${alumglass.esc(__("Vì sao ra số này?"))}"
                        data-quotation-item="${alumglass.esc(opts.quotation_item || "")}"
                        data-explain-key="${alumglass.esc(explainKey || "")}"
                        data-slug="${alumglass.esc(ln.slug)}"
                        data-item-code="${alumglass.esc(ln.item_code || "")}"
                        data-label="${alumglass.esc(lineLabel)}">?</button>`
                : "";
            body += `<tr>
                <td style="color:#64748b;white-space:nowrap;">${codeCell}</td>
                <td><strong>${alumglass.esc(lineLabel)}</strong>${explainBtn}${ruleTrace}${lineTrace}</td>
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
// ═══════════════════════════════════════════════════════════════════════════
// Nút nhỏ cạnh tên vật tư (render trong bảng "Chi tiết vật tư" ở trên).
// Bấm → dialog gọi server lấy chuỗi bước: chọn mã vật tư → ... → thành tiền.
//
// Nguyên tắc hiển thị (bar User Delight):
//   - ⛔ không phơi tên hàm/API, mã lỗi, stack ra màn hình
//   - lỗi mạng/API → 1 câu đơn giản + nút "Thử lại"
//   - bước thiếu dữ liệu → nhãn xám "Chưa lưu dữ liệu cho bước này"
//   - luôn có lối thoát: nút "Đóng" + nút X chuẩn của Frappe
// ═══════════════════════════════════════════════════════════════════════════

// Kho tạm kết quả ĐANG HIỂN THỊ theo từng lần render (`explain-key` → payload).
// Vì sao cần: preview ⛔ không ghi DB nên `al_bom_result` trong DB có thể CŨ
// hơn (hoặc chưa có) kết quả người dùng đang thấy. Nút "Vì sao ra số này?"
// phải giải thích CHÍNH kết quả đó ⇒ client gửi `result_json` của dòng.
// ⛔ Không nhét JSON vào `data-*` (attribute phình to, dễ vỡ khi có ngoặc kép).
alumglass._explain_payloads = {};
alumglass._explain_seq = 0;

// Đăng ký payload của 1 lần render → trả khoá gắn vào nút. Không có
// `result_json` ⇒ trả "" (nút dùng đường cũ: server đọc DB theo tên dòng).
alumglass.register_explain_payload = function (result_json, parent) {
    if (!result_json) return "";
    // Nhận cả chuỗi JSON (thường) lẫn object (caller lỡ truyền response thô)
    // — luôn chuẩn hoá về CHUỖI vì `explain_bom_line_args` so/ép chuỗi.
    const payload_json = (typeof result_json === "string")
        ? result_json : JSON.stringify(result_json);
    const key = "ex-" + (++alumglass._explain_seq);
    alumglass._explain_payloads[key] = {
        result_json: payload_json,
        parent: parent || "",
    };
    // Renderer chạy lại nhiều lần (mỗi lần sửa tham số) ⇒ dọn khoá cũ để
    // không giữ JSON của cả phiên trong bộ nhớ. Giữ 100 lượt gần nhất.
    const keys = Object.keys(alumglass._explain_payloads);
    if (keys.length > 100) {
        keys.slice(0, keys.length - 100).forEach(function (k) {
            delete alumglass._explain_payloads[k];
        });
    }
    return key;
};

// Tham số gửi `explain_bom_line` (THUẦN — test bằng Node).
//   - dòng ĐÃ LƯU: `quotation_item_name` để server kiểm quyền + đọc DB;
//   - dòng MỚI (`new-…`/rỗng): chỉ giải thích được khi có `result_json`
//     trong tay, và PHẢI kèm `parent` để server kiểm quyền trên báo giá cha.
// Trả null = thiếu định danh, ⛔ không gọi server.
alumglass.explain_bom_line_args = function (opts) {
    opts = opts || {};
    const slug = String(opts.slug || "");
    const name = String(opts.quotation_item || "");
    const result_json = opts.result_json ? String(opts.result_json) : "";
    const parent = String(opts.parent || "");
    if (!slug) return null;
    const is_new = !name || name.indexOf("new-") === 0;
    if (is_new && (!result_json || !parent)) return null;
    const args = { quotation_item_name: name, slug: slug };
    if (result_json) args.result_json = result_json;
    if (is_new) args.parent = parent;
    return args;
};

alumglass.explain_bom_line_dialog = function (opts) {
    opts = opts || {};
    const quotation_item = opts.quotation_item || "";
    const slug = opts.slug || "";
    // Tham số dựng 1 lần: dialog có thể mở từ DÒNG MỚI (chưa có trong DB) —
    // khi đó `result_json` + `parent` là nguồn DUY NHẤT để giải thích.
    const call_args = alumglass.explain_bom_line_args({
        quotation_item: quotation_item,
        slug: slug,
        result_json: opts.result_json || "",
        parent: opts.parent || "",
    });
    // Thiếu dữ liệu định danh dòng → không mở dialog (nút đã ẩn ở renderer,
    // đây là chốt chặn thứ hai).
    if (!call_args) return;

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
            args: call_args,
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
        if (!slug) return;
        // Kết quả ĐANG HIỂN THỊ (nếu có) — giải thích đúng cái người dùng thấy,
        // kể cả dòng MỚI chưa từng được ghi xuống DB.
        const key = $btn.attr("data-explain-key") || "";
        const payload = key ? (alumglass._explain_payloads || {})[key] : null;
        alumglass.explain_bom_line_dialog({
            quotation_item: quotation_item || "",
            parent: (payload && payload.parent) || "",
            result_json: (payload && payload.result_json) || "",
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

// Chuyển raw al_bom_result → display model tối thiểu (không trace).
// Dùng làm FALLBACK khi get_result_display không trả được label (không có API/
// lỗi mạng) — renderer chung vẫn là nơi duy nhất render HTML.
//
// ⚠ Từ 2026-11-25d: `label` lấy NHÃN NGƯỜI ĐỌC (`line_label` → `item_name` →
// `item_code`), ⛔ KHÔNG lấy `slug` — trước đây cột Tên hiện slug
// (`kinh_tren`) ở đúng đường dòng báo giá MỚI. Các cờ trạng thái quy tắc
// (`item_selection_mode`, `rule_*_missing`, `rule_missing_reason`) PHẢI đi
// qua nguyên vẹn, nếu không renderer không biết dòng là Rule để nói
// "Chưa tra được mã" thay vì phơi slug.
alumglass.raw_to_display = function (raw) {
    raw = raw || {};
    const lines = (raw.lines || []).map(function (l) {
        return {
            slug: l.slug,
            label: l.line_label || l.item_name || l.item_code || "",
            // Tên người đọc khác (dòng BOM đặt tên / tên vật tư) — pass-through
            // để `alumglass.line_display_label` có nguồn dự phòng.
            line_label: l.line_label || "",
            item_name: l.item_name || "",
            line_name: l.line_name || "",
            item_code: l.item_code,
            // Trạng thái chọn mã theo quy tắc — giữ nguyên giá trị server trả.
            item_selection_mode: l.item_selection_mode || "",
            rule_source_missing: l.rule_source_missing,
            rule_input_missing: l.rule_input_missing,
            rule_missing_reason: l.rule_missing_reason || "",
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
            qty_rule_trace: l.qty_rule_trace,
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
// LỊCH SỬ (vì sao từng có `_sync_row_to_db`): `frappe.model.set_value()` chỉ
// cập nhật doc TRÊN TRÌNH DUYỆT; server cũ đọc `al_bom_vars` bằng
// `frappe.get_doc("Quotation Item", name)` nên phải ghi DB trước mỗi lượt
// tính. Cách đó làm mỗi lần gõ phím (auto-preview 700 ms) save cả Quotation.
//
// TỪ PHASE 1 (Owner chốt 2026-11-21): `alumglass.api.preview_bom(params)` nhận
// THAM SỐ trong request, engine dựng dòng từ params ⇒ ⛔ không cần ghi DB, và
// ⛔ tuyệt đối không được ghi DB ở đường preview. Hai helper dưới đây để lại
// (deprecated) cho lời gọi bên ngoài app; ⛔ đừng thêm caller mới.
// ─────────────────────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════
// ⛔ DEPRECATED (phase 1 "Preview không ghi DB", Owner chốt 2026-11-21):
// mọi đường PREVIEW đã chuyển sang `alumglass.api.preview_bom(params)` —
// engine nhận tham số từ `params`, ⛔ không đọc `al_bom_vars` từ DB nữa.
// Hai hàm dưới đây KHÔNG còn caller trong app; giữ lại tạm để script/MCP
// bên ngoài (nếu có) không vỡ, sẽ xoá ở phase 3. ⛔ Đừng thêm caller mới.
// ─────────────────────────────────────────────────────────────────────────
// `_persist_row`: ghi các field chỉ định xuống DB cho 1 dòng Quotation Item.
// ⛔ DEPRECATED — không dùng trong luồng chạy; xoá ở phase 3.
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
// Trả về Promise<{name, doc_saved}>:
//   name      = tên THẬT của dòng sau khi đã đảm bảo tồn tại trong DB
//   doc_saved = true khi cả chứng từ Quotation đã được LƯU THẬT (dòng mới
//               buộc phải `frm.save()`) — nơi gọi dùng cờ này để ⛔ không báo
//               "bấm Lưu" khi báo giá đã lưu rồi.
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
                    resolve({ name: cdn, doc_saved: false });
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
        return { name: row ? row.name : cdn, doc_saved: true };
    });
};

// `_sync_row_to_db`: đọc trạng thái HIỆN TẠI của dòng trong bộ nhớ trình
// duyệt (đã được `frappe.model.set_value` cập nhật trước đó, ví dụ trong
// `_save()`) rồi ghi các field then chốt cho việc tính giá xuống DB.
// Trả về Promise<{name, doc_saved}> như `_persist_row` — nơi gọi chỉ cần tên
// dòng thì đọc `.name` (xem `_run_preview`, `_calc_all_items`).
// ⛔ DEPRECATED — xem khối comment ngay trên `_persist_row`.
// ⛔ DEPRECATED — không dùng trong luồng chạy; xoá ở phase 3.
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
// Ghi KẾT QUẢ tính giá xuống dòng Quotation Item — MỘT bản dùng chung
// ─────────────────────────────────────────────────────────────────────────
// Máy chủ ghi kết quả THẲNG vào DB ở `BomOrchestrator.b7_save_results`
// (`al_gia_vat`, `al_gia_ban`, `al_bom_result`, `rate`) nhưng client phải ghi
// LẠI đúng bộ đó vào dòng trong `frm.doc.items` — nếu không, lần Lưu báo giá
// gửi nguyên doc và dòng mang giá trị CŨ/rỗng GHI ĐÈ kết quả vừa tính.
//
// Trước đây dialog (`ItemParamDialog._write_result_to_row`) và đường "Tính
// giá" hàng loạt (`_calc_all_items`) mỗi bên có một bản ghi riêng: bulk còn
// đoán giá từ `cost_template` và KHÔNG ghi `al_bom_result`/trạng thái xuống
// dòng ⇒ cùng lớp lỗi trên vẫn còn. Nay cả hai đi qua `_apply_result_to_row`.
//
// Hàm này ⛔ KHÔNG gọi `frappe.db.*`, ⛔ KHÔNG `frm.save()` — DB chỉ ghi khi
// người dùng bấm Lưu báo giá.
// ═══════════════════════════════════════════════════════════════════════════

// Nhớ các OBJECT dòng đã nhận kết quả PREVIEW trong phiên này — client-only,
// ⛔ không ghi field nào xuống DB. Cần để MỞ LẠI dialog vẫn biết "kết quả này
// chưa lưu" (nếu chỉ để cờ trên dialog instance thì đóng/mở là mất). Lưu bằng
// WeakSet để ⛔ giữ object sống và tự nhả khi dòng bị thay.
alumglass.quotation._previewed_rows = new WeakSet();

// Dấu vân tay của lượt preview này: dòng đã nhận kết quả chưa lưu?
//
// So sánh NỘI DUNG chứ ⛔ chỉ tin dấu WeakSet: `frappe.model.sync` cập nhật
// TẠI CHỖ nên object dòng giữ nguyên identity sau khi Lưu báo giá ⇒ chỉ dựa
// vào WeakSet thì banner "giá vừa tính chưa được lưu" nằm mãi trên báo giá
// vừa lưu (UX1 bắt 2026-11-21). Mỗi lượt preview ghi kèm
// `row.__al_preview_json` (KHÔNG enumerable ⇒ ⛔ lọt vào payload Lưu);
// dòng bị thay `al_bom_result` (Lưu xong / nạp lại) thì dấu hết nghĩa.
alumglass.quotation._is_preview_unsaved = function (row) {
    if (!row) return false;
    const set = alumglass.quotation._previewed_rows;
    if (!set) return false;
    try {
        if (!set.has(row)) return false;
    } catch (e) {
        return false;
    }
    // Object cũ chưa gắn `__al_preview_json` ⇒ chỉ còn dấu WeakSet để dựa vào.
    if (row.__al_preview_json === undefined) return true;
    const norm = (v) => (v === undefined || v === null ? "" : String(v));
    return norm(row.al_bom_result) === norm(row.__al_preview_json);
};

// Xoá MỌI dấu "chưa lưu" — gọi khi báo giá đã LƯU xong (`after_save`).
// Phải xoá cả `__al_preview_json` trên từng dòng: đổi mỗi WeakSet là chưa đủ
// nếu dấu nội dung còn nằm trên object.
alumglass.quotation._clear_preview_marks = function (frm) {
    alumglass.quotation._previewed_rows = new WeakSet();
    const rows = (frm && frm.doc && frm.doc.items) || [];
    rows.forEach((row) => {
        if (!row) return;
        try { delete row.__al_preview_json; } catch (e) { /* bỏ qua */ }
    });
};

// ── Dấu "kết quả trên dòng KHÔNG còn khớp tham số hiện tại" ───────────────
// Người dùng đổi BOM / BOM Version / biến / cấu hình ⇒ `al_bom_result` đang
// nằm trên dòng là kết quả của bộ tham số CŨ, còn `al_calc_status` vẫn
// "Success" ⇒ mở lại dialog là thấy số CŨ (lỗi Owner 2026-11-23).
// Cờ `__al_result_stale` client-only, KHÔNG enumerable (cùng kiểu
// `__al_preview_json` — ⛔ lọt vào payload Lưu báo giá).
// ⛔ TUYỆT ĐỐI không xoá `al_bom_result` khi đánh dấu: kết quả cũ còn cần để
// so sánh sau khi tính lại xong và để ⛔ đánh rơi dữ liệu người dùng đã có.
alumglass.quotation._mark_row_result_stale = function (row) {
    if (!row) return false;
    try {
        Object.defineProperty(row, "__al_result_stale", {
            value: true,
            configurable: true,
            writable: true,
            enumerable: false,
        });
        return true;
    } catch (e) {
        return false;
    }
};

alumglass.quotation._clear_row_result_stale = function (row) {
    if (!row) return;
    try { delete row.__al_result_stale; } catch (e) { /* bỏ qua */ }
};

alumglass.quotation._is_row_result_stale = function (row) {
    return !!(row && row.__al_result_stale);
};

// Báo giá còn dòng nào mang kết quả preview CHƯA lưu? (dùng cho cảnh báo in)
alumglass.quotation._has_unsaved_preview = function (frm) {
    const rows = (frm && frm.doc && frm.doc.items) || [];
    return rows.some((row) => alumglass.quotation._is_preview_unsaved(row));
};

// Dòng CHƯA LƯU? Frappe ⛔ có property `is_new` trên dòng con (chỉ có HÀM
// `frm.is_new()`); dòng mới nhận diện bằng tên `new-…` + cờ `__islocal`.
// ⛔ dùng `row.is_new` một mình: luôn undefined ⇒ lọc "dòng mới" thành no-op.
alumglass.quotation._row_is_new = function (row) {
    if (!row) return true;
    const name = String(row.name || "");
    return !name || name.indexOf("new-") === 0 || !!row.__islocal || !!row.is_new;
};

// Dò dòng Quotation Item trong `frm.doc.items`: theo `name`, không thấy thì
// theo `idx` của object gợi ý (dòng mới chưa có `name` thật).
alumglass.quotation._find_row_in_form = function (frm, cdt, cdn, hint) {
    const rows = (frm && frm.doc && frm.doc.items) || [];
    let row = cdn ? rows.find((r) => r && r.name === cdn) : null;
    if (!row && hint && hint.idx) row = rows.find((r) => r && r.idx === hint.idx);
    return row || null;
};

// Ghi 1 field vào DANH SÁCH object đích (đã dedupe theo identity).
// Bản trong `locals` đi qua `frappe.model.set_value` (API chuẩn: bắn sự kiện
// change, đánh dấu `__unsaved`); các object khác gán thẳng. Bỏ qua object
// đang ĐÃ mang đúng giá trị. Trả true nếu có object được ghi.
alumglass.quotation._write_field_to_targets = function (cdt, cdn, targets, fieldname, value, localsDoc) {
    const norm = (v) => String(v === undefined || v === null ? "" : v);
    const desired = norm(value);
    const canSetValue = !!(frappe.model && typeof frappe.model.set_value === "function");
    let wrote = false;
    targets.forEach((target) => {
        if (!target || norm(target[fieldname]) === desired) return;
        if (target === localsDoc && canSetValue) {
            frappe.model.set_value(cdt, cdn, fieldname, value);
        } else {
            target[fieldname] = value;
        }
        wrote = true;
    });
    return wrote;
};

// Áp một kết quả tính giá (hoặc CHỈ trạng thái) xuống dòng Quotation Item.
//
//   frm, cdt, cdn : báo giá đang mở + dòng đích
//   result        : response máy chủ của lượt tính vừa xong (buckets /
//                   cost_template / lines / gia_ban / gia_vat). `null` ⇒ CHỈ
//                   ghi trạng thái/lỗi/job, ⛔ không xoá kết quả cũ, ⛔ không ghi giá.
//   opts          : { status = "Success", error = "", job_id = "",
//                     row = dòng Quotation Item trong frm.doc.items (tuỳ chọn),
//                     child_doc = object dòng của dialog (tuỳ chọn) }
//                   `row`/`child_doc` giúp ghi đúng cả khi dòng chưa có `name`.
//
// Trả true nếu có ghi kết quả, false nếu chỉ ghi trạng thái.
alumglass.quotation._apply_result_to_row = function (frm, cdt, cdn, result, opts) {
    opts = opts || {};
    const hint = opts.row || opts.child_doc || null;
    cdt = cdt || (hint && hint.doctype) || "Quotation Item";
    cdn = cdn || (hint && hint.name) || "";
    const status = opts.status || "Success";
    const job_id = opts.job_id === undefined ? "" : opts.job_id;
    const error = opts.error === undefined ? "" : opts.error;

    // Ba nơi có thể là BA OBJECT KHÁC NHAU và cả ba đều phải nhận giá trị:
    //   · bản trong `locals` — `frappe.get_doc(cdt, cdn)` (nguồn dialog mở lại),
    //   · dòng trong `frm.doc.items` — nguồn lưới + lần Lưu báo giá sau,
    //   · object dòng của dialog (`opts.child_doc`) — trạng thái nội bộ dialog.
    // Ghi vào CẢ BA + dedupe (trùng object ⛔ không ghi lặp).
    const targets = [];
    const add = (obj) => { if (obj && targets.indexOf(obj) < 0) targets.push(obj); };
    let localsDoc = null;
    if (cdn && typeof frappe.get_doc === "function") {
        try { localsDoc = frappe.get_doc(cdt, cdn) || null; } catch (e) { localsDoc = null; }
    }
    add(localsDoc);
    add(opts.row || null);
    add(alumglass.quotation._find_row_in_form(frm, cdt, cdn, hint));
    add(opts.child_doc || null);

    const write = (fieldname, value) => alumglass.quotation._write_field_to_targets(
        cdt, cdn, targets, fieldname, value, localsDoc);

    if (!result) {
        write("al_calc_status", status);
        write("al_calc_error", status === "Success" ? "" : error);
        write("al_calc_job_id", job_id);
        return false;
    }

    // `al_gia_ban` = giá TRƯỚC VAT, `al_gia_vat` = giá CÓ VAT.
    // Ưu tiên giá MÁY CHỦ đã tính (`_resolve_pre_vat_price` /
    // `_resolve_final_price` — `b7_save_results` lưu cùng khoá `gia_ban` /
    // `gia_vat` trong response), rồi mới rơi về dòng GIA_BAN / GIA_VAT của
    // cost template (response bản cũ chưa có 2 khoá trên). ⛔ KHÔNG tự bịa
    // `GIA_BAN * (1 + thuế)`: thuế suất có thể không nằm trong response.
    // ⛔ KHÔNG dùng `GIA_VAT || 0`: 0 là giá THẬT (miễn phí/hàng tặng) và `||`
    // biến 0 thành falsy ⇒ ghi đè bằng số khác hoặc mất giá.
    const blank = (v) => v === undefined || v === null || String(v).trim() === "";
    const num = (v) => {
        if (blank(v)) return null;
        const n = Number(v);
        return isFinite(n) ? n : null;
    };
    const pick = (primary, fallback) => (num(primary) !== null ? num(primary) : num(fallback));
    const ct = result.cost_template || {};
    const gia_ban = pick(result.gia_ban, ct.GIA_BAN);
    const gia_vat = pick(result.gia_vat, pick(result.GIA_VAT, ct.GIA_VAT));

    write("al_bom_result", JSON.stringify(result));
    write("al_calc_status", status);
    write("al_calc_error", status === "Failed" ? error : "");
    write("al_calc_job_id", job_id);
    // Ghi dấu "kết quả này CHƯA lưu DB" lên chính các object dòng (client-only)
    // — mở lại dialog trong phiên vẫn hiện nhắc, và ⛔ cần thêm field DB.
    // `__al_preview_json` = NỘI DUNG đã ghi: dùng để so sánh khi đọc lại dấu
    // (xem `_is_preview_unsaved`). Định nghĩa ⛔ enumerable để `JSON.stringify`
    // của payload Lưu báo giá ⛔ mang theo bản sao JSON này.
    if (status === "Success") {
        const result_json = JSON.stringify(result);
        targets.forEach((target) => {
            try {
                alumglass.quotation._previewed_rows.add(target);
                Object.defineProperty(target, "__al_preview_json", {
                    value: result_json,
                    configurable: true,
                    writable: true,
                    enumerable: false,
                });
                // Kết quả MỚI đã ghi ⇒ dấu "cũ" (`__al_result_stale`) hết hiệu
                // lực. Xoá Ở ĐÂY (không phải ở chỗ gọi) để mọi đường ghi kết
                // quả — dialog, realtime, "Tính giá" hàng loạt, "Áp dụng vào
                // dòng" — đều tự xoá cờ.
                alumglass.quotation._clear_row_result_stale(target);
            } catch (e) { /* bỏ qua */ }
        });
    }
    if (gia_ban !== null) write("al_gia_ban", gia_ban);
    if (gia_vat !== null) write("al_gia_vat", gia_vat);
    // `rate` = giá trước VAT — CÙNG giá trị máy chủ ghi trong `b7_save_results`.
    // Chỉ ghi khi > 0 (0 thường là "chưa có giá" — ⛔ không xoá đơn giá người
    // dùng đã nhập tay).
    if (gia_ban !== null && gia_ban > 0) write("rate", gia_ban);
    return true;
};

// Tính LẠI TỔNG TIỀN báo giá trên client sau khi `rate` của dòng đổi.
//
// Vì sao cần: trước đây server (B7) ghi cả tổng tiền cha xuống DB nên màn
// hình ít nhất mở lại là thấy đúng. Nay preview ⛔ không ghi DB, mà
// `frappe.model.set_value("rate")` KHÔNG kéo theo `calculate_taxes_and_totals`
// (ERPNext không có handler `rate`) ⇒ không gọi hàm này thì tổng trên màn
// hình giữ số CŨ trong khi giá dòng đã mới.
//
// Gọi MỘT lần mỗi lô (dialog: sau khi có kết quả; bulk: ở `finish()`), ⛔ không
// gọi trong vòng lặp từng dòng. Thiếu controller (môi trường test / form chưa
// có cscript) ⇒ bỏ qua im lặng: lần Lưu báo giá server vẫn tính lại tổng.
alumglass.quotation._refresh_totals = function (frm) {
    if (!frm) return;
    try {
        const cscript = frm.cscript;
        if (cscript && typeof cscript.calculate_taxes_and_totals === "function") {
            cscript.calculate_taxes_and_totals();
        } else if (typeof frm.calculate_taxes_and_totals === "function") {
            frm.calculate_taxes_and_totals();
        }
    } catch (e) {
        // Không có controller tính thuế ⇒ để lần Lưu báo giá tính lại.
    }
    ["items", "total", "grand_total"].forEach((f) => {
        try {
            if (typeof frm.refresh_field === "function") frm.refresh_field(f);
        } catch (e) { /* field không có trên form ⇒ bỏ qua */ }
    });
};

// Toast báo KẾT QUẢ PREVIEW — LUÔN xanh dương, ⛔ xanh lá (UX1 2026-11-21).
// Vì sao: trong sản phẩm này xanh lá = đã GHI DB thật; preview ⛔ ghi gì nên
// xanh lá khiến người dùng tưởng báo giá đã mang giá mới. Câu phải nói rõ
// "chưa lưu" + việc cần làm; câu dài ⇒ để 7 giây cho đọc kịp.
alumglass.quotation._show_preview_toast = function (message) {
    frappe.show_alert({ message: message, indicator: "blue" }, 7);
};

// Tham số `preview_bom` cho 1 dòng ĐANG NẰM TRÊN FORM (không đọc DB).
// Dùng cho nút 🖥️ ngoài lưới / trong form con của dòng. ⛔ Không gửi tiền
// tệ/bảng giá/khách hàng — server luôn lấy từ Quotation cha trong DB.
alumglass.quotation._row_preview_params = function (frm, row) {
    row = row || {};
    const params = {
        al_bom: row.al_bom || "",
        al_bom_version: row.al_bom_version || "",
        al_bom_vars: row.al_bom_vars || "{}",
        item_code: row.item_code || "",
        item_name: row.item_name || "",
        parent: (frm && frm.doc && frm.doc.name) || "",
        parenttype: "Quotation",
    };
    ["qty", "uom"].forEach((fieldname) => {
        if (row[fieldname] !== undefined && row[fieldname] !== null) {
            params[fieldname] = row[fieldname];
        }
    });
    return params;
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
// Dòng ĐÃ LƯU → gửi `quotation_item_name` để server kiểm quyền trên báo giá.
// Dòng CHƯA lưu (`new-...`) → ⛔ không gửi: server kiểm quyền trên dòng
// không tồn tại sẽ lỗi.
// `params` (TUỲ CHỌN — phase 1.5) = tham số dòng ĐANG NẰM TRÊN DIALOG
// (al_bom, al_bom_version, al_bom_vars, item_code, item_name, parent).
// Preview ⛔ không ghi DB nữa nên thiếu params thì server đọc `al_bom_vars`
// CŨ/rỗng trong DB ⇒ biến & mã kính hiện sai trạng thái. ⛔ Không truyền ⇒
// args y như trước (không có key `params`).
alumglass.glass_pick.build_variable_set_args = function (bom_code, row_name, params) {
    const args = { bom_code: bom_code };
    const name = String(row_name || "");
    if (name && name.indexOf("new-") !== 0) {
        args.quotation_item_name = name;
    }
    if (params) {
        args.params = typeof params === "string" ? params : JSON.stringify(params);
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
// `params` (TUỲ CHỌN — phase 1.5): object hoặc HÀM trả object tham số dòng
// đang nằm trên dialog. Truyền hàm để mỗi lượt gọi lấy trạng thái MỚI NHẤT
// (requester sống suốt dialog, tham số đổi sau mỗi lần sửa). Server dùng nó
// tra giá theo biến người dùng đang sửa thay vì `al_bom_vars` cũ trong DB.
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
                const args = {
                    quotation_item_name: opts.quotation_item_name || "",
                    glass_code: code,
                };
                const extra = (typeof opts.params === "function")
                    ? opts.params() : (opts.params || null);
                if (extra) {
                    args.params = typeof extra === "string" ? extra : JSON.stringify(extra);
                }
                call(alumglass.glass_pick.PRICE_METHOD, args,
                    function (resp) {
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
        // Response máy chủ của lượt tính giá THÀNH CÔNG gần nhất trong phiên
        // dialog này — nút 💾 Lưu dùng lại để ghi đủ bộ kết quả xuống dòng mà
        // ⛔ không phải tính lại.
        this._last_result = null;
        // ⚠ `al_calc_status`/`al_calc_job_id` của preview chỉ sống trong BỘ NHỚ
        // client (`child_doc`/dòng trên form) — phase 1 ⛔ ghi DB, đóng form là
        // mất. Mở lại dialog trong cùng phiên vẫn thấy đúng trạng thái.
        this._preview_unsaved = false;
        // ── BOM Version: chống ghi đè muộn (lỗi Owner 2026-11-23) ──
        // `default` của field `al_bom_version` dựng từ `child_doc` lúc `show()`,
        // nhưng dialog còn chờ `_load_variable_set()` (gọi server) mới dựng
        // xong. Trong lúc chờ, dòng trên form có thể đã nhận version mới hơn
        // (Lưu trước, realtime, form con…). `_seed_version_from_row()` đọc lại
        // dòng SAU khi nạp xong và chốt giá trị — chỉ 1 lần mỗi lần mở dialog.
        this._version_seeded = false;
        // Người dùng đã TỰ sửa ô BOM Version trong phiên này chưa. ⛔ Không
        // được đè lên lựa chọn tay của người dùng.
        this._version_user_edited = false;
        // Giá trị hệ thống (default lúc dựng field / lần seed) đã đặt — dùng để
        // phân biệt `set_value` lập trình với thao tác thật của người dùng,
        // vì Frappe bắn `onchange` cho CẢ HAI (xem `_on_version_change`).
        this._version_default = (child_doc && child_doc.al_bom_version) || "";
        this._version_programmatic_value = undefined;
        // Người dùng đã ĐỔI BOM trong phiên dialog này chưa. Bật ⇒
        // `_seed_version_from_row()` ⛔ được chốt version theo dòng (dòng còn
        // mang version của BOM CŨ, ghi đè lựa chọn BOM MỚI của người dùng).
        // CHỈ bật khi BOM trên dialog khác BOM đang giữ của dòng — xem
        // `_on_bom_change`.
        this._bom_changed_in_session = false;
        // Đang ĐIỀN LẬP TRÌNH các field cấu hình (`_render_bom_info`) — bật để
        // `_on_param_edited()` ⛔ đánh dấu "kết quả CŨ" cho lượt `set_value`
        // không phải do người dùng.
        this._programmatic_param_set = false;
        // Chống race của `_load_variable_set`: mỗi lượt nạp tăng seq; lượt CŨ
        // trả về sau (chọn BOM1 rồi BOM2) bị bỏ, ⛔ ghi đè trạng thái BOM2.
        this._variable_set_seq = 0;
        // Timer dựng panel preview lúc mở dialog (300ms) — huỷ khi dialog đóng
        // để ⛔ gắn listener realtime SAU khi listener đã bị dọn (rò + toast lạ).
        this._preview_panel_timer = null;
    }

    show() {
        // NGUỒN SỰ THẬT = dòng THẬT trên báo giá. Dòng trên phiếu có thể được
        // mở dialog bằng một bản sao KHÁC: nút trong form con của dòng truyền
        // `frappe.get_doc("Quotation Item", cdn)` (bản trong `locals`), trong
        // khi lần Lưu trước chỉ ghi vào dòng của `frm.doc.items` ⇒ bản sao kia
        // vẫn mang giá trị CŨ và dialog dựng field theo nó (lỗi Owner gặp
        // 2026-11-23: dòng đã đổi BOM Version mà mở lại dialog vẫn thấy bản
        // cũ). Đồng bộ TRƯỚC khi dựng fields (`default` của BOM/BOM Version,
        // `_parse_existing` – biến, kính, màu, extra_vars… đều đọc
        // `this.child_doc`).
        // `_resolve_row_object()` dò theo 3 lớp — xem comment ở hàm đó. Không
        // tìm thấy dòng tương ứng (mở ngoài ngữ cảnh báo giá) → giữ `child_doc`,
        // ⛔ không ném.
        const gridRow = this._resolve_row_object();
        if (gridRow) {
            // Dòng mới vừa được lưu: Frappe đổi tên `new-…` → tên thật trong
            // `frm.doc.items`, object dialog còn giữ tên cũ ⇒ lần mở SAU dò
            // theo tên sẽ trượt. Đồng bộ tên trước khi thay object.
            this._sync_child_doc_name(gridRow);
            this.child_doc = gridRow;
        }
        this._render_dialog();
        // Chốt version NGAY sau khi dựng xong (lượt ĐỒNG BỘ): dialog phải hiện
        // đúng version của dòng, ⛔ phụ thuộc `default` của field và ⛔ phụ
        // thuộc lượt nạp Variable Set (mạng). Lượt này ⛔ đặt `_version_seeded`
        // nên lượt async trong `_render_dialog` vẫn chạy — bảo vệ ca "dòng đổi
        // version trong lúc chờ server".
        this._seed_version_from_row({ sync: true });
        // Ép LỚP HIỂN THỊ khớp dòng: `set_value` của control có thể bị nuốt
        // (`inside_change_event` / `is_value_same` — base_control.js:216-231)
        // ⇒ giá trị model đúng mà ô vẫn hiện version CŨ. Chỉ sửa hiển thị
        // (`set_input` + `ctrl.value`), ⛔ ghi model, ⛔ ghi dòng.
        this._force_display_row_version();
    }

    // ── Đọc Variable Set từ BOM → Bom Set → Variable Set ──────────
    async _load_variable_set() {
        // Mỗi lượt nạp một seq riêng. Người dùng chọn BOM2 trong lúc lượt nạp
        // BOM1 còn chờ ⇒ lượt BOM1 trả về SAU bị coi là cũ (resolve `null`),
        // ⛔ ghi đè biến/kính/version của BOM2 (lỗi Owner 2026-11-23).
        const seq = ++this._variable_set_seq;
        const bom = this.child_doc.al_bom;
        if (!bom) { this._bom_meta = null; return []; }

        // Gửi kèm tên dòng (nếu dòng đã lưu) — server kiểm quyền + đọc trạng
        // thái kính của báo giá. Dòng `new-...` thì KHÔNG gửi tên (xem
        // build_variable_set_args).
        // Phase 1.5: gửi THÊM `params` = trạng thái dòng ĐANG MỞ (biến, kính,
        // BOM/Version trên form). Preview ⛔ không ghi DB nữa ⇒ thiếu params
        // thì server đọc `al_bom_vars` cũ/rỗng và dialog hiện biến & mã kính
        // ĐÃ LƯU thay vì trạng thái người dùng đang thấy.
        const args = alumglass.glass_pick.build_variable_set_args(
            bom, (this.child_doc && this.child_doc.name) || "",
            this._dialog_state_params());

        return new Promise(resolve => {
            frappe.call({
                method: "alumglass.api.get_variable_set_for_bom",
                args: args,
                callback: r => {
                    // Lượt nạp cũ (BOM đã bị đổi) ⇒ bỏ, ⛔ đụng `_bom_meta`.
                    if (seq !== this._variable_set_seq) { resolve(null); return; }
                    this._bom_meta = r.message || null;
                    if (r.message?.variables) {
                        resolve(r.message.variables);
                    } else {
                        resolve([]);
                    }
                },
                error: () => {
                    if (seq !== this._variable_set_seq) { resolve(null); return; }
                    this._bom_meta = null; resolve([]);
                },
            });
        });
    }

    // `default` cho field BOM Version lúc DỰNG dialog.
    // Nguồn chính là `child_doc` (đã được `show()` đồng bộ với dòng thật).
    // Nếu dòng THẬT lúc này vẫn mang version KHÁC `child_doc` (bản sao trong
    // `locals` cũ, dòng vừa được ghi ở đường khác…) thì in cảnh báo ra
    // Console để lần sau khỏi phải đoán — ⛔ KHÔNG hiện cho người dùng; việc
    // CHỐT giá trị nằm ở `_seed_version_from_row()` sau khi nạp xong.
    _version_default_for_field() {
        const dialogVersion = (this.child_doc && this.child_doc.al_bom_version) || "";
        try {
            const row = this._resolve_row_object();
            const rowVersion = (row && row.al_bom_version) || "";
            if (row && String(rowVersion) !== String(dialogVersion)) {
                console.warn("[alumglass] version lệch khi mở dialog",
                    { dialog: dialogVersion, row: rowVersion });
            }
        } catch (e) { /* chỉ là chẩn đoán — ⛔ được làm hỏng dialog */ }
        this._version_default = dialogVersion;
        return dialogVersion;
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
                default: this._version_default_for_field(),
                get_query: () => {
                    const bom = this.dialog?.get_value("al_bom");
                    if (bom) return { filters: { bom: bom } };
                    return {};
                },
                onchange: () => this._on_version_change(),
            },
            {
                fieldname: "al_brand", fieldtype: "Link", label: __("Hãng nhôm"),
                options: "Brand",
                // A2: editable — lưu override _brand
                onchange: () => this._on_param_edited(),
            },

            // Cấu hình BOM — editable (A2/A3), override lưu vào al_bom_vars
            { fieldtype: "Section Break", label: __("Cấu hình BOM") },
            {
                fieldname: "al_bom_set", fieldtype: "Link", label: __("Bom Set"),
                options: "AL Bom Set",
                onchange: () => this._on_param_edited(),
            },
            {
                fieldname: "al_accessory_set", fieldtype: "Link", label: __("Phụ kiện (Accessory Set)"),
                options: "AL Accessory Set",
                onchange: () => this._on_param_edited(),
            },
            { fieldname: "col_cfg_1", fieldtype: "Column Break" },
            {
                fieldname: "al_profile_system", fieldtype: "Link", label: __("Hệ profile"),
                options: "AL Profile System",
                onchange: () => this._on_param_edited(),
            },
            {
                fieldname: "al_cost_template", fieldtype: "Link", label: __("Cost Template"),
                options: "AL Cost Template",
                onchange: () => this._on_param_edited(),
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
            primary_action_label: __("Áp dụng vào dòng"),
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
        // huỷ timer dựng panel (nếu chưa chạy) + cleanup realtime listener
        // (tránh leak và tránh gắn listener mới sau khi đã dọn).
        $(this.dialog.$wrapper).on("hidden.bs.modal", () => {
            this._dialog_open = false;
            if (this._preview_panel_timer) {
                clearTimeout(this._preview_panel_timer);
                this._preview_panel_timer = null;
            }
            this._cleanup_realtime();
        });

        // Nạp extra vars từ al_bom_vars hiện có (Table field chuẩn Frappe)
        this._populate_extra_vars();
        this._setup_extra_vars_autofill();

        // Load Variable Set → render vùng biến động (KHÔNG recreate dialog)
        // Mở dialog → giữ override đã lưu trong al_bom_vars (nếu có)
        this._load_variable_set().then(vars => {
            // Lượt nạp đã bị thay (người dùng đổi BOM trong lúc chờ) ⇒ bỏ
            // nguyên lượt, ⛔ ghi đè biến/kính/version của BOM mới.
            if (vars === null) return;
            this._current_vars = vars;
            this._render_vars_container(vars);
            this._render_bom_info(true);
            // Nạp xong biến/kính → chốt lại BOM Version theo dòng THẬT (dòng
            // có thể đã nhận version mới hơn trong lúc chờ server trả về).
            // Chỉ chạy 1 lần/lần mở; ⛔ đè lên lựa chọn tay của người dùng.
            this._seed_version_from_row();
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
                // Dòng còn mang kết quả CŨ (tham số đã đổi mà lượt tính lại
                // chưa chạy — VD người dùng đóng cửa sổ trong 700ms) ⇒ tự
                // tính lại; người dùng ⛔ phải bấm gì thêm.
                if (this._has_stale_result()) {
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

        this._preview_panel_timer = setTimeout(() => {
            this._preview_panel_timer = null;
            this._render_preview_panel();
        }, 300);
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
            if (!ctrl || !ctrl.set_value) return;
            // Đây là ĐIỀN GIÁ TRỊ LẬP TRÌNH khi dựng/nạp lại vùng cấu hình,
            // KHÔNG phải người dùng sửa. Frappe bắn `df.onchange` cho cả
            // `set_value` ⇒ phải chặn `_on_param_edited()` đánh dấu "kết quả
            // CŨ" oan (mở dialog sạch lại tự tính lại giá).
            this._programmatic_param_set = true;
            try {
                ctrl.set_value(value);
            } finally {
                this._programmatic_param_set = false;
            }
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
                        self._on_param_edited();
                    });
            });

        // Auto-preview khi sửa bất kỳ ô nào trong bảng "Biến mở rộng"
        // (tên biến, kiểu, hoặc giá trị) — event delegation để bắt cả dòng
        // thêm sau. Không cần chờ blur ra khỏi bảng như trước.
        $(grid.wrapper)
            .off("change.al_autopreview awesomplete-selectcomplete.al_autopreview", ".grid-row [data-fieldname]")
            .on("change.al_autopreview awesomplete-selectcomplete.al_autopreview", ".grid-row [data-fieldname]", function () {
                self._on_param_edited();
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

    // ── Chuẩn hoá giá trị Link BOM để so sánh ──────────────────────
    // `undefined`/`null` → "" (rỗng), còn lại `String()`. Giữ nguyên hoa/
    // thường vì name của Link `AL BOM` phân biệt hoa/thường như dữ liệu.
    _norm_bom(value) {
        return value === undefined || value === null ? "" : String(value);
    }

    // ── Đổi BOM: re-render vùng biến trong dialog CŨ (không recreate) ──
    _on_bom_change() {
        const bom = this.dialog?.get_value("al_bom");
        if (!bom) return;
        // BOM trên dialog TRÙNG BOM đang giữ của dòng ⇒ ⛔ phải là thao tác
        // đổi BOM: không đánh dấu "đã đổi", không lấy `current_version` đè
        // version của dòng, không nạp lại biến. (Frappe ⛔ bắn `onchange` khi
        // áp `default` — `FieldGroup.make` dùng `set_input`, xem
        // `field_group.js:24-33` + `data.js:244` — nhưng `set_value` lập trình
        // và vài đường khác thì CÓ bắn, nên vẫn phải chặn tại đây.)
        const bomNorm = this._norm_bom(bom);
        if (bomNorm === this._norm_bom(this.child_doc && this.child_doc.al_bom)) return;
        // Đánh dấu người dùng ĐÃ đổi BOM: từ đây `_seed_version_from_row()`
        // ⛔ được chốt version theo dòng (dòng còn mang version BOM CŨ).
        this._bom_changed_in_session = true;
        // Kết quả đang nằm trên dòng là của BOM CŨ ⇒ đánh dấu CŨ (⛔ xoá
        // `al_bom_result`). Đặt TRƯỚC lượt nạp mạng: người dùng đóng cửa sổ
        // ngay sau khi đổi BOM vẫn ⛔ thấy số của BOM cũ ở lần mở sau.
        this._mark_result_stale();
        // Tự động set version mới nhất
        frappe.db.get_value("AL BOM", bom, "current_version", r => {
            // Callback của BOM CŨ về SAU (chọn nhanh A→B→A) ⇒ ⛔ được đè lên
            // version của BOM đang chọn: ô `al_bom` trên dialog đã khác `bom`
            // của lượt gọi này. Cùng kiểu chống race như `_load_variable_set`
            // (`_variable_set_seq`). Không có guard: version của B hiện trên
            // dialog trong khi ô BOM hiện A — sai thầm lặng (UX1 2026-11-23).
            if (this._norm_bom(this.dialog?.get_value("al_bom"))
                !== this._norm_bom(bom)) return;
            if (r?.current_version) this.dialog?.set_value("al_bom_version", r.current_version);
        });
        this.child_doc.al_bom = bom;
        // Chỉ re-render vùng biến + thông tin BOM — dialog giữ nguyên vị trí/kích thước,
        // không giật, không tạo dialog mới, không reset preview.
        // Đổi BOM → reset về default của BOM mới (bỏ override cũ cho dòng này)
        this._load_variable_set().then(vars => {
            // Lượt nạp đã cũ (người dùng đổi BOM lần nữa) ⇒ bỏ.
            if (vars === null) return;
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

    // ── Người dùng sửa 1 THAM SỐ tính giá (kính/biến/cấu hình/extra vars) ──
    // Một cửa duy nhất cho mọi onchange tham số: đánh dấu kết quả đã lưu trên
    // dòng là CŨ rồi mới lên lịch tính lại. Tách khỏi
    // `_schedule_auto_preview()` vì hàm đó còn được gọi ở các đường KHÔNG
    // phải sửa tham số (mở dialog, chờ kính) — đánh dấu ở đó sẽ báo "cũ" sai.
    _on_param_edited() {
        // `set_value` LẬP TRÌNH (dựng lại vùng cấu hình ở `_render_bom_info`)
        // cũng bắn `onchange` — ⛔ phải thao tác người dùng, ⛔ đánh dấu "cũ".
        if (this._programmatic_param_set) return;
        this._mark_result_stale();
        this._schedule_auto_preview();
    }

    // Đánh dấu kết quả trên DÒNG là cũ. Ghi lên MỌI object của cùng dòng
    // (bản trong `locals` / dòng lưới `frm.doc.items` / `child_doc` của
    // dialog) để mở lại dialog bằng đường nào cũng thấy cờ — mở lại bằng nút
    // form con truyền bản trong `locals`, mở bằng nút trên lưới đọc
    // `frm.doc.items`.
    // ⛔ KHÔNG xoá `al_bom_result`, ⛔ KHÔNG ghi DB.
    _mark_result_stale() {
        const src = this.child_doc || {};
        const cdt = src.doctype || "Quotation Item";
        const cdn = src.name;
        const targets = [];
        const add = (obj) => { if (obj && targets.indexOf(obj) < 0) targets.push(obj); };
        if (cdt && cdn && typeof frappe.get_doc === "function") {
            try { add(frappe.get_doc(cdt, cdn)); } catch (e) { /* bỏ qua */ }
        }
        add(this._find_form_row());
        add(src);
        let any = false;
        targets.forEach((target) => {
            if (alumglass.quotation._mark_row_result_stale(target)) any = true;
        });
        return any;
    }

    // Dòng của dialog còn mang kết quả CŨ (tham số đã đổi, chưa tính lại)?
    // Hỏi cả `child_doc` lẫn dòng THẬT trên form — hai object có thể khác nhau
    // (form con truyền bản trong `locals`).
    _is_result_stale() {
        if (alumglass.quotation._is_row_result_stale(this.child_doc)) return true;
        return alumglass.quotation._is_row_result_stale(this._find_form_row());
    }

    // Có kết quả CŨ đang nằm trên dòng ở trạng thái "Success" — tức là mở
    // panel ra sẽ thấy SỐ CŨ trông y như số thật. Chỉ ca này mới cần tự tính
    // lại khi dialog mở xong; dòng chưa từng có kết quả thì cờ "cũ" vô nghĩa
    // (panel đang hiện lời mời bấm Preview) — ⛔ tự bắn lượt tính giá thừa.
    _has_stale_result() {
        if (!this._is_result_stale()) return false;
        const row = this.child_doc || {};
        return row.al_calc_status === "Success" && !!row.al_bom_result;
    }

    // Báo hiệu "đang chờ tính lại" ngay lập tức (trước khi debounce chạy) mà
    // KHÔNG xoá kết quả preview cũ đang hiển thị — tránh cảm giác dialog "đứng".
    _mark_preview_stale() {
        const $container = this._preview_container();
        if (!$container.length) return;
        // Panel đã hiện ô xám "đang tính lại" (`.al-preview-pending` do
        // `_preview_stale_html` dựng) ⇒ trạng thái đã được nói đúng, đã kèm
        // lối xử lý. Chèn thêm badge vàng ở đây thành HAI dòng ⏳ chồng nhau,
        // hai màu, hai câu khác nhau (UX1 2026-11-23).
        if ($container.find(".al-preview-pending").length) return;
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
                    () => self._on_param_edited());
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
                // Phase 1.5: trạng thái dialog tại THỜI ĐIỂM hỏi giá (hàm —
                // requester sống suốt dialog, biến/tham số đổi liên tục).
                // Server tra giá theo biến người dùng đang sửa thay vì bản
                // `al_bom_vars` cũ trong DB (preview ⛔ không ghi DB).
                params: () => this._dialog_state_params(),
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
    // ⛔ KHÔNG còn `skipSync`: nút 💾 Lưu chỉ sửa dòng trên FORM, và preview
    // cũng ⛔ không ghi DB ⇒ không có gì phải đồng bộ trước.
    _preview_and_wait(maxMs, skipRun) {
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
            if (!skipRun) this._run_preview(false);
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

    // Nút 💾 Lưu: cập nhật dòng Quotation Item TRÊN FORM + đánh dấu báo giá
    // "có thay đổi". ⛔ KHÔNG ghi DB — DB chỉ được ghi khi người dùng bấm
    // Lưu Quotation (yêu cầu Owner 2026-11-21:
    // "lưu dialog phải ghi xuống dòng quotation item, lưu phiếu mới lưu vào db").
    // Ngoại lệ DUY NHẤT là nhánh cần tính lại giá kính: server đọc
    // `al_bom_vars` từ DB nên `_run_preview` vẫn sync dòng xuống DB trước khi
    // gọi engine (yêu cầu kỹ thuật của engine, không phải "lưu báo giá").
    _on_primary_action() {
        // `_save()` CHỈ ghi (form, không DB) và trả thông tin dòng vừa ghi.
        // Thông báo do CHÍNH HÀM NÀY bắn SAU `dialog.hide()` ở cả hai nhánh:
        // bắn trong lúc modal còn mở thì toast bị che, và nhánh phải chờ
        // preview (tới 20s) thì toast 7s hết hạn trước khi người dùng thấy.
        // Các đường gọi `_save()` khác (auto-preview, Preview tính giá)
        // ⛔ không báo — chúng không gọi hàm này.
        // Đọc dấu "kết quả trên dòng đang CŨ" TRƯỚC `_save()`: `_save()` ghi
        // tham số mới xuống dòng, và đường ghi kết quả xoá dấu — đọc sau sẽ
        // mất dấu đúng lúc cần nhất.
        const wasStale = this._is_result_stale();
        const saved = this._save({ notify: true }) || {};
        // `_save()` ghi qua `frappe.model.set_value`; object trong
        // `frm.doc.items` có thể là object KHÁC ⇒ ghi lại tường minh để lưới
        // và lần Lưu báo giá sau chắc chắn mang tham số vừa sửa. `_save()` đã
        // gọi hàm này; gọi lại là idempotent (cùng nguồn giá trị từ dialog).
        // Kết quả tính giá đang có trong phiên này (nếu đã có lượt tính xong)
        // cũng phải được ghi ĐỦ bộ CÙNG LƯỢT (idempotent — giá trị đã đúng thì
        // `_write_row_field` bỏ qua): thiếu bước này, Lưu báo giá sẽ gửi doc
        // lên với kết quả cũ/rỗng và ghi đè kết quả vừa tính.
        // ⛔ GHI LẠI `_last_result` KHI DÒNG ĐANG ĐÁNH DẤU CŨ: `_last_result`
        // là kết quả của bộ tham số CŨ, còn dòng vừa nhận tham số MỚI. Ghi nó
        // xuống sẽ (a) xoá dấu cũ (mọi đường ghi kết quả đều xoá) và (b) làm
        // số cũ trông y như số thật ở lần mở lại dialog — đúng lỗi Owner
        // 2026-11-23 đi qua cửa "Áp dụng vào dòng". Dòng cũ sẽ được tính lại
        // ngay bên dưới (`mustRecalc`).
        if (this._last_result && !wasStale) this._write_result_to_row(this._last_result, {});
        this._apply_row_to_form();
        // Kiểm hậu điều kiện SAU khi đã ghi xuống dòng (chỉ Console): bấm
        // "Áp dụng" xong mà version trên dialog vẫn khác version đã ghi ⇒ có
        // đường khác đang đè. ⛔ ném, ⛔ chặn thao tác.
        this._warn_version_mismatch();
        // Đánh dấu báo giá có thay đổi + vẽ lại lưới (nút Lưu của form bật).
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
        // Dòng đang mang kết quả CŨ (tham số vừa đổi) cũng phải tính lại TRƯỚC
        // khi đóng dialog, kể cả khi lựa chọn kính không đổi (ca đổi BOM
        // Version / biến): đóng luôn sẽ để số cũ nằm trên dòng.
        const mustRecalc = wasStale || this._needs_glass_recalc() || staleInflight;

        const self = this;
        if (!mustRecalc) {
            // Không có gì phải tính lại ⇒ đóng NGAY, ⛔ không chờ mạng.
            if (self.dialog) self.dialog.hide();
            // Preview ⛔ KHÔNG ghi DB (phase 1) ⇒ lúc nào cũng còn "chưa lưu
            // vào báo giá", kể cả dòng mới (dòng mới cũng chỉ nằm trên form).
            self._notify_params_applied(saved);
            return Promise.resolve();
        }
        // Huỷ timer auto-preview 700ms đang treo (nếu có) — ta tính giá NGAY,
        // chạy thêm lần nữa là tính 2 lần cho cùng một thay đổi.
        self._cancel_auto_preview();
        const waitOnly = self._preview_inflight && !staleInflight;
        const $btn = (self.dialog && typeof self.dialog.get_primary_btn === "function")
            ? self.dialog.get_primary_btn() : null;
        if ($btn && $btn.length) $btn.prop("disabled", true).text(__("Đang tính giá..."));
        // Thứ tự: dòng trên form → preview (params đi kèm request) → đóng.
        // ⛔ Không đồng bộ DB trước: engine nhận tham số từ params.
        return self._preview_and_wait(20000, waitOnly).then(() => {
            // Preview tính lại THẤT BẠI ⇒ chỉ toast cam bên dưới, ⛔ không báo
            // thêm "đã áp dụng" (người dùng sẽ tưởng giá đã đúng tham số mới).
            // Dòng vẫn mang dấu CŨ sau lượt chờ = tính lại không xong (server
            // lỗi / quá 20s / kết quả không về) ⇒ cùng cách xử lý như kính.
            if ((wasStale && self._is_result_stale()) || self._needs_glass_recalc()) {
                // Tính lại KHÔNG xong (server lỗi / quá 20s) ⇒ đóng im lặng sẽ
                // khiến người dùng tưởng giá đã theo tham số mới. Nói rõ trạng
                // thái + đúng việc cần làm (mở lại rồi bấm "Preview tính giá").
                // Dấu cũ GIỮ NGUYÊN trên dòng — lần mở lại vẫn thấy panel ⏳,
                // ⛔ hiện số cũ như số thật.
                if (self.dialog) self.dialog.hide();
                self._alert_recalc_failed();
                return;
            }
            if (self.dialog) self.dialog.hide();
            // Báo SAU khi đóng — nhánh này có thể đã chờ preview tới 20s nên
            // toast bắn sớm sẽ hết hạn trước khi người dùng thấy.
            // Preview ⛔ không ghi DB ⇒ luôn nhắc "bấm Lưu báo giá".
            self._notify_params_applied(saved);
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

    // Cập nhật TÊN THẬT vào object dòng đang giữ (`this.child_doc`).
    //
    // Dòng mới thêm có tên `new-…`; sau khi Lưu báo giá, Frappe đổi tên trong
    // `frm.doc.items` sang tên thật nhưng object dialog (nhất là bản trong
    // `locals` do form con truyền vào) vẫn mang tên cũ. Giữ nguyên ⇒ lần mở
    // sau `_resolve_row_object()` dò theo tên TRƯỢT, chỉ còn khớp `idx` (dễ
    // trúng nhầm dòng khi lưới đổi thứ tự). Đồng bộ ngay khi đã tìm ra dòng thật.
    _sync_child_doc_name(row) {
        if (!row || !row.name || !this.child_doc) return row;
        if (this.child_doc.name !== row.name) this.child_doc.name = row.name;
        return row;
    }

    // Dòng THẬT tương ứng với dialog — theo ĐÚNG thứ tự các lớp:
    //   1. `this.frm.doc.items` — đường chuẩn: dialog mở từ form báo giá.
    //      Dò theo `name`, không thấy thì theo `idx` (dòng mới chưa có tên).
    //      ĐÂY LÀ LỚP DUY NHẤT được khớp `idx`, và chỉ khi chính form đó là
    //      BÁO GIÁ (hoặc form con của dòng báo giá) + cùng phiếu cha (xem
    //      `find_in`/`from_frm`).
    //   2. `cur_frm.doc.items` — form báo giá ĐANG MỞ trên Desk. Cần khi `frm`
    //      truyền vào không mang `items` (vd form con), vẫn phải lấy dòng mới
    //      nhất thay vì bản sao trong `locals`.
    //   2b. `frappe.container.page.frm` — form đang mở trong container. Một số
    //      đường mở form (điều hướng qua container, mở lại tab) KHÔNG gán
    //      `cur_frm`, nhưng form vẫn nằm ở đây.
    //   2c. `frappe.views.formview["Quotation"|"Sales Order"].frm` — form đang
    //      giữ trong bộ nhớ view (tab nền, form vừa mở lại).
    //   2d. Quét MỌI `frappe.views.formview` đang mở — lớp cuối trước khi chịu
    //      thua, phòng khi view giữ dưới khoá doctype khác (bản dịch tên, tên
    //      khác hoa/thường).
    //   3. `this.frm.doc` CHÍNH LÀ dòng (`doctype === "Quotation Item"`) —
    //      đường `frappe.get_doc("Quotation Item", cdn)` của form con. CHỈ
    //      nhận khi TÊN KHỚP `child_doc.name`; đây ⛔ không phải bản sao mà là
    //      chính dòng cần hiển thị.
    // ⚠ Thứ tự các lớp giữ NGUYÊN. Các lớp (2) → (2d) chỉ nhận form BÁO GIÁ
    // và ⛔ bao giờ khớp theo `idx`: `idx` là số thứ tự TRONG BẢNG của từng
    // chứng từ, nên một Sales Order / báo giá KHÁC đang mở cũng có dòng `idx`
    // trùng — khớp `idx` ở đó là trả về dòng của CHỨNG TỪ KHÁC, rồi
    // `_write_row_field` / `_apply_row_to_form` / `_sync_child_doc_name` ghi
    // chéo sang chứng từ đó (lỗi 2026-11-23).
    // Không lớp nào khớp (mở ngoài ngữ cảnh báo giá) → null; nơi gọi giữ
    // `child_doc` như cũ và ⛔ không ném.
    // Mọi lớp đều phòng thủ (`try/catch` + kiểm `items` là MẢNG): object giả
    // trong test, form đã đóng, `doc` chưa nạp, `views` chưa tồn tại… đều chỉ
    // trả null, ⛔ được làm hỏng việc mở dialog.
    _resolve_row_object() {
        const src = this.child_doc || {};
        // Dòng hợp lệ phải là `Quotation Item`. Object giả trong test/harness
        // có thể KHÔNG khai `doctype` ⇒ vẫn chấp nhận; khai mà khác ⇒ dòng
        // của chứng từ khác, ⛔ nhận.
        const is_row = (r) => !!r && (!r.doctype || r.doctype === "Quotation Item");
        // Tên THẬT mới dùng để khớp: dòng mới `new-…` chưa được Frappe đặt tên
        // (sau khi Lưu mới thành tên thật — xem `_sync_child_doc_name`).
        const real_name = (src.name && !String(src.name).startsWith("new-"))
            ? src.name : null;
        // Khớp dòng trong bảng: theo TÊN THẬT trước; theo `idx` CHỈ khi bên
        // gọi cho phép (`allow_idx === true`) — xem cảnh báo ở đầu hàm.
        const find_in = (rows, allow_idx) => {
            if (!Array.isArray(rows) || !rows.length) return null;
            let row = real_name
                ? rows.find(r => is_row(r) && r.name === real_name)
                : null;
            if (!row && allow_idx === true && src.idx) {
                row = rows.find(r => is_row(r) && r.idx === src.idx);
            }
            return row || null;
        };
        // Đọc bảng dòng của 1 form bất kỳ — sai kiểu/thiếu `doc` ⇒ null.
        //   · `quotation_only`: form phải là BÁO GIÁ (`doc.doctype`) — form
        //     Đơn bán hàng hay chứng từ khác ⛔ bao giờ chứa dòng `Quotation
        //     Item`, đọc vào chỉ để trả nhầm.
        //   · `allow_idx`: xem `find_in`; kèm điều kiện CÙNG PHIẾU CHA — dòng
        //     khai `parent` thì `doc.name` phải đúng phiếu đó (chống ghi chéo
        //     chứng từ).
        const from_frm = (frm, opts) => {
            opts = opts || {};
            try {
                const doc = frm && frm.doc;
                if (!doc) return null;
                if (opts.quotation_only && doc.doctype !== "Quotation") return null;
                let allowIdx = opts.allow_idx === true;
                if (allowIdx && src.parent && doc.name !== src.parent) allowIdx = false;
                return find_in(doc.items, allowIdx);
            } catch (e) {
                return null;
            }
        };

        // (1) form đang mở dialog — lớp DUY NHẤT được khớp theo `idx` (dòng mới
        // chưa có tên thật), và chỉ khi chính form đó là báo giá / form con của
        // dòng báo giá.
        let own = null;
        try {
            const ownDoc = this.frm && this.frm.doc;
            const ownDt = ownDoc && ownDoc.doctype;
            own = from_frm(this.frm, {
                allow_idx: ownDt === "Quotation" || ownDt === "Quotation Item",
            });
        } catch (e) { own = null; }
        if (own) return own;

        // (2) form báo giá đang mở trên Desk
        let live = null;
        try {
            if (typeof cur_frm !== "undefined") {
                live = from_frm(cur_frm, { quotation_only: true });
            }
        } catch (e) { live = null; }
        if (live) return live;

        // (2b) form đang mở trong container
        let containerRow = null;
        try {
            containerRow = from_frm(frappe.container && frappe.container.page
                && frappe.container.page.frm, { quotation_only: true });
        } catch (e) { containerRow = null; }
        if (containerRow) return containerRow;

        // (2c) form view theo doctype — danh sách giữ nguyên nhưng CHỈ nhận
        // form báo giá: dòng `Quotation Item` ⛔ thuộc Đơn bán hàng.
        let viewRow = null;
        try {
            const views = frappe.views && frappe.views.formview;
            const dts = ["Quotation", "Sales Order"];
            for (let i = 0; i < dts.length && !viewRow; i += 1) {
                const fv = views && views[dts[i]];
                viewRow = from_frm(fv && fv.frm, { quotation_only: true });
            }
        } catch (e) { viewRow = null; }
        if (viewRow) return viewRow;

        // (2d) quét MỌI form view đang mở — vẫn chỉ nhận form báo giá (khoá
        // của view có thể khác chuỗi "Quotation", nhưng `doc.doctype` thì không)
        let scanned = null;
        try {
            const views = frappe.views && frappe.views.formview;
            if (views && typeof views === "object") {
                const keys = Object.keys(views);
                for (let i = 0; i < keys.length && !scanned; i += 1) {
                    const fv = views[keys[i]];
                    scanned = from_frm(fv && fv.frm, { quotation_only: true });
                }
            }
        } catch (e) { scanned = null; }
        if (scanned) return scanned;

        // (3) `this.frm.doc` chính là dòng cần hiển thị
        try {
            const doc = this.frm && this.frm.doc;
            if (doc && doc.doctype === "Quotation Item" && src.name
                && doc.name === src.name) {
                return doc;
            }
        } catch (e) { /* form giả/đã đóng — coi như không có */ }

        return null;
    }

    // Dòng tương ứng trong báo giá — giữ tên cũ cho nơi gọi hiện có
    // (`_collect_row_values`, `_write_row_field`, `_apply_row_to_form`).
    // Dùng CHUNG `_resolve_row_object()` để `show()` và các đường ghi
    // ⛔ không lệch nhau.
    _find_form_row() {
        return this._resolve_row_object();
    }

    // ── Chốt BOM Version SAU khi nạp xong biến/kính ─────────────────
    // Dialog dựng field với `default` = `child_doc.al_bom_version` NGAY lúc
    // `show()`, nhưng phần biến/kính còn chờ `_load_variable_set()` (gọi
    // server). Trong khoảng chờ đó dòng THẬT có thể đã mang version mới hơn
    // (`_write_row_field` của lượt Lưu trước, realtime, form khác ghi…) ⇒
    // người dùng mở lại thấy version CŨ (lỗi Owner 2026-11-23). Hàm này đọc
    // lại dòng một lần nữa NGAY TRƯỚC khi dialog coi như nạp xong và chốt
    // giá trị.
    // Quy ước:
    //   · mỗi lần mở dialog chốt HAI lượt: 1 lượt ĐỒNG BỘ ngay sau
    //     `_render_dialog()` (`{ sync: true }`) và 1 lượt async sau khi nạp
    //     xong Variable Set. Lượt sync ⛔ đặt `_version_seeded` để lượt async
    //     vẫn chạy — bảo vệ ca "dòng đổi version trong lúc chờ server";
    //   · người dùng ĐÃ tự sửa ô này ⇒ ⛔ không đè, chỉ cảnh báo Console;
    //   · người dùng ĐÃ đổi BOM THẬT ⇒ ⛔ chốt version của dòng (version đang
    //     hiện là của BOM mới);
    //   · không tìm thấy dòng / giá trị đã khớp ⇒ không làm gì;
    //   · cuối lượt chốt THẬT ⇒ `_warn_version_mismatch()` (chỉ Console).
    // Trả true nếu có ghi giá trị.
    _seed_version_from_row(opts) {
        const sync = !!(opts && opts.sync);
        const seededBefore = this._version_seeded;
        const wrote = this._seed_row_version_values(sync);
        // Kiểm hậu điều kiện ở ĐÚNG một chỗ cho mọi nhánh return phía trên.
        // Bỏ qua khi lượt gọi bị `_version_seeded` chặn (đã chốt rồi — không
        // phải lỗi mới) trừ lượt sync lúc mở dialog.
        if (sync || this._version_seeded !== seededBefore) this._warn_version_mismatch();
        return wrote;
    }

    // Phần lõi của `_seed_version_from_row` — tách ra để mọi nhánh return đều
    // đi qua phần kiểm hậu điều kiện của wrapper.
    _seed_row_version_values(sync) {
        const markSeeded = () => { if (!sync) this._version_seeded = true; };
        if (!sync && this._version_seeded) return false;
        // Chưa có dialog thì ⛔ đánh dấu "đã seed" — lượt gọi sau (khi dialog
        // đã dựng) vẫn phải chạy được.
        if (!this.dialog) return false;
        // Người dùng đã ĐỔI BOM trong phiên này ⇒ version đang hiện là của BOM
        // MỚI, còn dòng vẫn mang version BOM CŨ ⇒ ⛔ được chốt theo dòng.
        // Cờ này CHỈ bật khi BOM trên dialog KHÁC BOM của dòng (xem
        // `_on_bom_change`), nên ca "mở lại dialog" ⛔ bao giờ rơi vào đây.
        if (this._bom_changed_in_session) {
            markSeeded();
            return false;
        }
        // Ô BOM trên dialog khác BOM của object dòng (người dùng vừa đổi, dòng
        // chưa đồng bộ) ⇒ cũng ⛔ được chốt version theo dòng.
        if (this._norm_bom(this._dialog_field_value("al_bom"))
            !== this._norm_bom(this.child_doc && this.child_doc.al_bom)) {
            markSeeded();
            return false;
        }
        markSeeded();
        const row = this._resolve_row_object();
        if (!row) return false;
        const rowVersion = row.al_bom_version || "";
        const norm = (v) => (v === undefined || v === null ? "" : String(v));
        const current = this._dialog_field_value("al_bom_version");
        // Không đọc được giá trị dialog (object giả, field chưa dựng) coi như
        // rỗng — vẫn so được với dòng.
        if (norm(current) === norm(rowVersion)) return false;
        if (this._version_user_edited) {
            console.warn("[alumglass] dialog version khác dòng — giữ lựa chọn người dùng");
            return false;
        }
        // Ghi nhận đây là giá trị HỆ THỐNG đặt để `onchange` của field không
        // hiểu nhầm thành thao tác người dùng (Frappe bắn onchange cho cả
        // `set_value` lập trình).
        this._version_default = rowVersion;
        this._version_programmatic_value = rowVersion;
        this.dialog.set_value("al_bom_version", rowVersion);
        return true;
    }

    // Ép Ô HIỂN THỊ `al_bom_version` khớp version của DÒNG.
    //
    // Vì sao cần dù đã có `_seed_version_from_row`: `dialog.set_value()` đi
    // qua `BaseControl.set_value` — gặp `inside_change_event` (control đang
    // trong 1 lượt change khác) hoặc `is_value_same` thì THOÁT SỚM, không ghi
    // vào input (base_control.js:216-231). Khi đó model/`this.value` đã đúng
    // nhưng người dùng vẫn thấy version CŨ trên ô.
    // Chỉ sửa LỚP HIỂN THỊ: `ctrl.set_input()` (ghi phần hiển thị) + gán
    // `ctrl.value` (giá trị control đọc ra) — ⛔ ghi model, ⛔ ghi dòng, ⛔ ghi DB.
    // Bỏ qua khi người dùng đang có lựa chọn RIÊNG (đã đổi BOM / tự sửa
    // version): lúc đó version trên dialog KHÁC dòng là ĐÚNG ý người dùng.
    // Trả true nếu có ép.
    _force_display_row_version() {
        try {
            if (!this.dialog) return false;
            if (this._bom_changed_in_session || this._version_user_edited) return false;
            const row = this._resolve_row_object();
            if (!row) return false;
            const rowVersion = (row.al_bom_version === undefined || row.al_bom_version === null)
                ? "" : String(row.al_bom_version);
            const shown = this._dialog_field_value("al_bom_version");
            // Không đọc được ô (dialog giả, field chưa dựng) ⇒ ⛔ kết luận
            // lệch — ép mù sẽ đè lên giá trị đúng.
            if (shown === undefined) return false;
            const norm = (v) => (v === undefined || v === null ? "" : String(v));
            if (norm(shown) === norm(rowVersion)) return false;
            const ctrl = this.dialog.fields_dict && this.dialog.fields_dict["al_bom_version"];
            if (!ctrl) return false;
            if (typeof ctrl.set_input === "function") ctrl.set_input(rowVersion);
            ctrl.value = rowVersion;
            console.warn("[alumglass] phải ép hiển thị version",
                { dialog: shown, row: rowVersion });
            return true;
        } catch (e) {
            // Chỉ là lớp hiển thị — ⛔ được làm hỏng việc mở dialog.
            return false;
        }
    }

    // Chẩn đoán SAU khi chốt version (chỉ Console, ⛔ hiện cho người dùng):
    // nếu ô BOM Version trên dialog vẫn khác version của dòng thì có đường
    // khác đang ghi đè (realtime, form con, server trả version khác…) — ghi
    // lại để lần sau khỏi phải đoán. Không ném, không sửa gì.
    _warn_version_mismatch() {
        try {
            if (!this.dialog) return;
            const row = this._resolve_row_object();
            if (!row) return;
            // Lệch CÓ CHỦ ĐÍCH: người dùng đã đổi BOM / tự sửa version — đã
            // có cảnh báo riêng ở `_seed_row_version_values`/`_on_version_change`,
            // ⛔ báo trùng.
            if (this._bom_changed_in_session || this._version_user_edited) return;
            const dialogVersion = this._dialog_field_value("al_bom_version");
            // Không đọc được (object giả) hoặc đang trống ⇒ ⛔ kết luận lệch:
            // ô trống có thể là dialog chưa dựng xong field.
            if (!dialogVersion) return;
            const rowVersion = row.al_bom_version;
            const norm = (v) => (v === undefined || v === null ? "" : String(v));
            if (norm(dialogVersion) !== norm(rowVersion)) {
                console.warn("[alumglass] version vẫn lệch sau khi chốt",
                    { dialog: dialogVersion, row: rowVersion });
            }
        } catch (e) { /* chỉ là chẩn đoán — ⛔ được làm hỏng dialog */ }
    }

    // ── onchange của field BOM Version ─────────────────────────────
    // `set_value` lập trình (default lúc mở dialog, seed, đổi BOM) CŨNG bắn
    // onchange — nên chỉ đánh dấu "người dùng đã sửa" khi giá trị hiện tại
    // KHÁC giá trị hệ thống vừa đặt (`_version_default` / lần seed gần nhất).
    // Nhờ vậy `_seed_version_from_row()` không đè lựa chọn tay của người dùng,
    // mà cũng không tự khoá mình vì lượt set mặc định lúc dựng field.
    // Người dùng chọn version THẬT ⇒ ghi NGAY xuống dòng (xem
    // `_write_version_down`): trước đây version chỉ xuống dòng khi bấm
    // **Áp dụng vào dòng** hoặc khi auto-preview (700ms) tình cờ chạy — đóng
    // cửa sổ trong 700ms là mất thay đổi, im lặng (UX1 2026-11-23).
    _on_version_change() {
        const norm = (v) => (v === undefined || v === null ? "" : String(v));
        const systemValues = [norm(this._version_default)];
        if (this._version_programmatic_value !== undefined) {
            systemValues.push(norm(this._version_programmatic_value));
        }
        const current = this._dialog_field_value("al_bom_version");
        if (systemValues.indexOf(norm(current)) < 0) {
            this._version_user_edited = true;
            this._write_version_down(current);
            // Version vừa đổi ⇒ kết quả trên dòng là của version CŨ. Đánh dấu
            // ngay (⛔ chờ auto-preview 700ms): đóng cửa sổ rồi mở lại trong
            // khoảng đó vẫn ⛔ được thấy giá của version cũ.
            this._mark_result_stale();
        }
        this._schedule_auto_preview();
    }

    // Ghi BOM Version người dùng vừa chọn xuống DÒNG trên phiếu (form, ⛔ DB) —
    // cùng cơ chế "dialog ghi xuống dòng, DB chỉ ghi khi bấm Lưu báo giá".
    // Bỏ qua khi không đọc được giá trị (field chưa dựng) hoặc dòng chưa có
    // tên. Trả true nếu có ghi.
    _write_version_down(value) {
        if (value === undefined) return false;
        const src = this.child_doc || {};
        const cdt = src.doctype || "Quotation Item";
        const cdn = src.name;
        if (!cdn) return false;
        const wrote = this._write_row_field(cdt, cdn, "al_bom_version", value);
        // `_apply_row_to_form` ghi nốt các object còn lại (lưới/locals) và các
        // field then chốt từ CÙNG nguồn dialog — idempotent.
        this._apply_row_to_form();
        // Đánh dấu phiếu có thay đổi: nếu chỉ sửa object dòng mà không bật cờ,
        // người dùng đóng cửa sổ rồi rời trang sẽ mất thay đổi mà ⛔ được cảnh
        // báo (nút Lưu không bật).
        if (this.frm) {
            if (this.frm.doc) this.frm.doc.__unsaved = 1;
            if (typeof this.frm.dirty === "function") this.frm.dirty();
            if (this.frm.refresh_field) this.frm.refresh_field("items");
        }
        return wrote;
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

    // Ghi 1 field xuống dòng. Ba nơi có thể là BA OBJECT KHÁC NHAU và cả ba
    // đều phải nhận giá trị:
    //   · bản trong `locals` — `frappe.get_doc(cdt, cdn)` (nguồn dialog mở
    //     lại bằng nút form con của dòng),
    //   · dòng trong `frm.doc.items` — nguồn lưới + lần Lưu báo giá sau,
    //   · `this.child_doc` — trạng thái nội bộ của dialog.
    // Ghi qua `frappe.model.set_value` cho bản trong `locals` (API chuẩn: bắn
    // sự kiện change, đánh dấu `__unsaved`), các object khác gán thẳng —
    // dedupe theo identity để TRÙNG object thì ⛔ không ghi lặp. Object nào
    // ĐÃ mang đúng giá trị thì bỏ qua (⛔ không bắn change handler vô ích —
    // item_code có handler reset giá). Trả true nếu có ghi.
    // Logic ghi nằm ở `_write_field_to_targets` (dùng chung với "Tính giá"
    // hàng loạt) — ở đây chỉ gom đủ 3 object đích của dialog.
    _write_row_field(cdt, cdn, fieldname, value) {
        const targets = [];
        const add = (obj) => { if (obj && targets.indexOf(obj) < 0) targets.push(obj); };
        // `frappe.get_doc` trả bản trong `locals` — kể cả dòng `new-…` (dòng
        // mới cũng có mặt trong `locals`, `set_value` vẫn chạy đúng).
        const localsDoc = (cdt && cdn) ? (frappe.get_doc(cdt, cdn) || null) : null;
        add(localsDoc);
        add(this._find_form_row());
        add(this.child_doc);
        // Ghi qua hàm dùng chung với đường "Tính giá" hàng loạt — ⛔ không có
        // bản sao thứ hai của logic ghi field.
        return alumglass.quotation._write_field_to_targets(
            cdt, cdn, targets, fieldname, value, localsDoc);
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

    // ── Ghi KẾT QUẢ tính giá xuống dòng Quotation Item ─────────────
    // Máy chủ ghi kết quả THẲNG vào DB ở `BomOrchestrator.b7_save_results`
    // (`al_gia_vat`, `al_gia_ban`, `al_bom_result`, `rate`) nhưng trước đây
    // client chỉ cập nhật `child_doc` + bản trong `locals`, ⛔ KHÔNG cập nhật
    // dòng trong `frm.doc.items`. Người dùng bấm Lưu báo giá → Frappe gửi
    // nguyên doc → dòng mang giá trị CŨ/rỗng GHI ĐÈ kết quả vừa tính (mở lại
    // dialog thấy số cũ / mất kết quả). Hàm này ghi ĐỦ bộ field xuống cả 3
    // nơi qua `_apply_result_to_row` (hàm dùng chung ở mức module, cũng là
    // đường "Tính giá" hàng loạt dùng), ⛔ không gọi `frappe.db.*`,
    // ⛔ không `frm.save()` — DB chỉ ghi khi Lưu báo giá.
    //
    // `result` = response máy chủ của lượt tính vừa xong (buckets /
    // cost_template / lines). `result` rỗng (null) + `extra.status` ⇒ CHỈ ghi
    // trạng thái/lỗi/job — ⛔ không xoá kết quả cũ, ⛔ không ghi giá.
    // `extra`: { status = "Success", error = "", job_id = "" }.
    // Trả true nếu có ghi kết quả, false nếu chỉ ghi trạng thái.
    _write_result_to_row(result, extra) {
        const src = this.child_doc || {};
        const cdt = src.doctype || "Quotation Item";
        const cdn = src.name;
        extra = extra || {};
        // MỘT nguồn ghi duy nhất cho cả dialog và "Tính giá" hàng loạt —
        // xem `alumglass.quotation._apply_result_to_row`.
        const applied = alumglass.quotation._apply_result_to_row(
            this.frm, cdt, cdn, result, {
                status: extra.status,
                error: extra.error,
                job_id: extra.job_id,
                child_doc: this.child_doc,
            });
        // Giữ lại để nút 💾 Lưu ghi lại đủ bộ (idempotent) mà ⛔ không tính lại.
        if (result) this._last_result = result;
        return applied;
    }

    // ── Preview Panel ──────────────────────────────────────────────
    _render_preview_panel() {
        // Dialog đã đóng (X/Esc/click nền) ⇒ ⛔ dựng panel/gắn listener nữa:
        // handler đóng đã dọn listener, gắn lại sau đó là rò + toast lạ.
        if (this._dialog_open === false) return;
        const $container = this._preview_container();
        if (!$container.length) return;

        // Mở lại panel → đọc trạng thái đã lưu trên item, không gọi lại API
        const status = this.child_doc.al_calc_status;
        // Kết quả preview còn trên dòng nhưng CHƯA lưu DB ⇒ mở lại dialog vẫn
        // phải nhắc (cờ bám object dòng, xem `_previewed_rows`).
        this._preview_unsaved = alumglass.quotation._is_preview_unsaved(this.child_doc);

        if (status === "Success" && this.child_doc.al_bom_result) {
            // Dòng còn dấu CŨ (`__al_result_stale` — tham số vừa đổi, chưa
            // tính lại) ⇒ TUYỆT ĐỐI ⛔ dựng bảng từ `al_bom_result` cũ: số cũ
            // trông y như số thật của tham số mới (lỗi Owner 2026-11-23).
            // Nói đúng trạng thái + lối xử lý, màu TRUNG TÍNH (⛔ đỏ — ⛔
            // phải lỗi).
            if (this._is_result_stale()) {
                $container.html(this._preview_stale_html());
                return;
            }
            // Mở lại dialog ⇒ dựng display từ KẾT QUẢ TRÊN DÒNG (nguồn sự thật
            // là dòng Quotation Item), ⛔ không đọc lại DB: dòng có thể đang
            // mang kết quả MỚI hơn bản trong DB (vừa tính xong, chưa Lưu báo
            // giá). Dòng rỗng ⇒ `_render_display_model` tự rơi về đường đọc DB.
            // Field JSON có thể là object (tuỳ bản Frappe/nguồn dựng doc) ⇒
            // chuẩn hoá về chuỗi; chuỗi rỗng thì ⛔ không gửi tham số.
            const rowResult = this.child_doc.al_bom_result;
            const rowResultJson = typeof rowResult === "string"
                ? rowResult : JSON.stringify(rowResult);
            this._render_display_model(
                $container, this.child_doc.name, false, rowResultJson);
            return;
        }

        if (status === "Queued" || status === "Running") {
            const job_id = this.child_doc.al_calc_job_id;
            // Trạng thái tự giải thích + LỐI XỬ LÝ: dòng còn "Queued" từ lần mở
            // form trước (worker chết/treo) → user biết phải bấm tính lại thay
            // vì ngồi chờ mãi một kết quả không bao giờ tới.
            $container.html(this._preview_progress_html(
                __("BOM đang xếp hàng tính trong nền. Kết quả chỉ nhận được khi cửa sổ này còn mở — nếu không thấy, bấm 'Preview tính giá' để tính lại.")
            ));
            // Job nền nhận THAM SỐ trong payload (⛔ không đọc DB) ⇒ lựa chọn
            // kính đang hiện khi mở lại chính là lựa chọn của job. Chụp chữ ký
            // NGAY ĐÂY làm chữ ký của job: người dùng đổi kính sau đó thì chữ
            // ký lệch ⇒ kết quả cũ về muộn không được gắn "Đã áp dụng".
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
        // Dialog đã đóng ⇒ ⛔ gắn listener (handler đóng đã dọn; gắn lại là rò).
        if (this._dialog_open === false) return;
        this._cleanup_realtime();
        const self = this;
        this._realtime_handler = function (data) {
            if (!data || data.job_id !== job_id) return;
            self._cleanup_realtime();
            // Instance đã đóng giữa lúc job chạy ⇒ ⛔ ghi kết quả (dialog mới
            // trên cùng dòng có thể đang sở hữu giá trị đúng), chỉ mở khoá chỗ chờ.
            if (self._dialog_open === false) {
                self._finish_preview_waiters();
                return;
            }
            if (!$container || !$container.length) $container = self._preview_container();

            if (data.status === "Success") {
                // Kết quả job nền về → ghi ĐỦ bộ xuống dòng TRÊN FORM
                // (al_bom_result, al_gia_ban, al_gia_vat, rate, trạng thái).
                // Server ⛔ không ghi DB cho preview nên đây là nguồn duy nhất;
                // lần Lưu báo giá sau đọc từ dòng này.
                self._write_result_to_row(data.result || null, {
                    status: "Success", job_id: job_id,
                });
                self._preview_unsaved = true;
                alumglass.quotation._refresh_totals(self.frm);
                // Kết quả mới vừa về → force = true để cảnh báo (vượt khổ kính...)
                // hiện ngay, không bị dedupe chặn.
                // Truyền chính kết quả vừa nhận: dòng mới (`new-…`) chưa có
                // trong DB nên ⛔ được để client gọi API đọc DB.
                self._render_display_model(
                    $container, self.child_doc.name, true,
                    data.result ? JSON.stringify(data.result) : null);
                // Kính đã đổi giữa lúc job chạy ⇒ ⛔ không gắn "Đã áp dụng"
                // (kết quả là của mã cũ) mà tính lại NGAY cho mã mới.
                const applied = self._finish_preview_with_glass(capturedSig);
                if (applied) {
                    // Preview ⛔ ghi DB ⇒ XANH DƯƠNG + nói rõ chưa lưu
                    // (xanh lá = đã ghi thật trong sản phẩm này).
                    alumglass.quotation._show_preview_toast(
                        __("Tính giá xong — chưa lưu vào báo giá."));
                }
            } else {
                // Trạng thái hỏng phải nằm TRÊN DÒNG (⛔ không chỉ `child_doc`):
                // mở lại dialog / Lưu báo giá sau đọc từ dòng.
                self._write_result_to_row(null, {
                    status: "Failed", error: data.error || "", job_id: job_id,
                });
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

    // Trạng thái "kết quả trên dòng đã CŨ" — thay cho bảng số ở
    // `_render_preview_panel` khi tham số vừa đổi mà chưa tính lại.
    // Màu TRUNG TÍNH (xám/xanh nhạt): đây ⛔ phải lỗi, chỉ là "đang chờ số
    // mới"; dùng đỏ sẽ làm người dùng tưởng hỏng. Luôn kèm LỐI XỬ LÝ.
    _preview_stale_html() {
        return `<div class="al-preview-pending" style="padding:14px;text-align:center;color:#334155;
            background:#f8fafc;border:1px solid #cbd5e1;border-radius:6px;">
            <span style="font-size:13px;">⏳ ${__("Tham số vừa đổi — đang tính lại giá. Chờ vài giây, hoặc bấm")}
            <b>${__("🖥️ Preview tính giá")}</b>.</span>
        </div>`;
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
        // Câu lỗi (VD "Kết quả tính giá lưu trên dòng này bị hỏng… Bấm 'Preview
        // tính giá' để tính lại.") đã có lối xử lý ⇒ ⛔ in thêm câu hướng dẫn
        // y hệt ngay bên dưới (lặp 2 lần liền nhau).
        const already_hints = /preview\s*tính\s*giá/i.test(info.message || "");
        const hint_html = already_hints
            ? `<p style="margin:6px 0 0;color:#64748b;font-size:12px;">${__("Nếu vẫn lỗi, báo quản trị.")}</p>`
            : `<p style="margin:6px 0 0;color:#64748b;font-size:12px;">${__("Bấm nút 'Preview tính giá' để thử lại. Nếu vẫn lỗi, báo quản trị.")}</p>`;
        return `<div style="padding:12px;color:#ef4444;text-align:center;">
            ❌ ${__("Tính giá thất bại")}
            ${safe_error ? `<p style="margin-top:8px;">${safe_error}</p>` : ""}
            ${hint_html}
            ${trace_html}
        </div>`;
    }

    // `manual` = true khi user bấm nút "🖥️ Preview tính giá" (mong đợi dialog
    // cuộn xuống xem kết quả ngay). `manual` = false/undefined khi được gọi
    // tự động từ `_schedule_auto_preview()` (đổi kính/tham số) — KHÔNG được
    // cuộn dialog, để con trỏ/vị trí đang nhập của user đứng nguyên, cho phép
    // gõ tiếp các trường khác trong lúc kết quả tự tính lại ở nền.
    //
    // ⛔ KHÔNG ghi DB (phase 1 "Preview không ghi DB"): tham số đi lên server
    // trong `params` của `preview_bom`; engine dựng dòng từ params thay vì đọc
    // DB. Vì vậy đường này ⛔ KHÔNG còn `_sync_row_to_db`/`frm.save()` — trước
    // đây mỗi lần gõ phím (auto-preview 700 ms) là một lượt save cả Quotation.
    _run_preview(manual) {
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
            if (manual && $container[0]
                && typeof $container[0].scrollIntoView === "function") {
                $container[0].scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }

        // Lưu tham số vào model TRÊN TRÌNH DUYỆT trước (vars, glass_master_map...)
        const saved = this._save() || {};

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

        // seq tăng mỗi lần gọi preview — nếu 1 preview cũ hơn trả về SAU 1
        // preview mới hơn (VD user đổi kính liên tục), kết quả cũ bị bỏ qua.
        const seq = ++this._preview_seq;
        this._exec_calculate_bom($container, seq, manual, capturedSig,
            this._preview_params(saved));
    }

    // Tham số gửi `preview_bom` — CHỈ những gì dialog đang thấy.
    // `saved.vars_json` là `al_bom_vars` vừa thu thập trong `_save()` (nguồn
    // DUY NHẤT đúng: biến gõ trong dialog, chưa cần ghi DB).
    // `parent` để server kiểm quyền + tra tiền tệ/bảng giá từ Quotation CHA
    // trong DB — ⛔ KHÔNG gửi tiền tệ/bảng giá/khách hàng từ client.
    _preview_params(saved) {
        saved = saved || {};
        const values = this._collect_row_values();
        const row = this._find_form_row() || this.child_doc || {};
        const params = {
            al_bom: values.al_bom || "",
            al_bom_version: values.al_bom_version || "",
            al_bom_vars: saved.vars_json || values.al_bom_vars || "{}",
            item_code: values.item_code || "",
            item_name: values.item_name || "",
            parent: (this.frm && this.frm.doc && this.frm.doc.name) || "",
            parenttype: "Quotation",
        };
        ["qty", "uom"].forEach((fieldname) => {
            if (row[fieldname] !== undefined && row[fieldname] !== null) {
                params[fieldname] = row[fieldname];
            }
        });
        return params;
    }

    // Gọi API PREVIEW (`preview_bom`) — ⛔ KHÔNG ghi DB, ⛔ không cần đồng bộ
    // dòng xuống DB trước (tham số đi trong `params`).
    // Tách riêng để `_run_preview` giữ ngắn gọn + tái dùng seq-guard.
    // `manual` (xem `_run_preview`) chỉ dùng để quyết định CÓ popup lỗi-cảnh báo.
    // `capturedSig` = chữ ký lựa chọn kính lúc lượt này bắt đầu — kết quả về
    // chỉ được gắn "Đã áp dụng" nếu chữ ký hiện tại vẫn đúng là nó.
    // `params` = tham số của lượt này (mặc định dựng từ trạng thái dialog).
    _exec_calculate_bom($container, seq, manual, capturedSig, params) {
        const self = this;
        if (!$container || !$container.length) $container = this._preview_container();
        params = params || this._preview_params({});
        const cdn = (this.child_doc && this.child_doc.name) || "";
        // Dòng MỚI chưa có trong DB ⇒ ⛔ gửi tên (server sẽ tra DB và ném lỗi).
        const is_local = !cdn || String(cdn).indexOf("new-") === 0;

        frappe.call({
            method: "alumglass.api.preview_bom",
            args: {
                quotation_item_name: is_local ? "" : cdn,
                params: JSON.stringify(params),
            },
            callback: (r) => {
                if (seq !== self._preview_seq) return; // stale — có preview mới hơn đã chạy
                // Instance đã đóng (người dùng đóng dialog khi preview đang chạy)
                // ⇒ ⛔ ghi kết quả: dialog MỚI trên cùng dòng có thể đã tính ra
                // số đúng, kết quả cũ về muộn sẽ ghi đè (giá sai được Lưu).
                if (self._dialog_open === false) {
                    self._finish_preview_waiters();
                    return;
                }
                if (!$container.length) {
                    // Dialog đã đóng/không còn panel preview → đừng treo chỗ chờ.
                    self._finish_preview_waiters();
                    return;
                }
                if (r.message) {
                    if (r.message.async) {
                        // BOM lớn — job đã enqueue (⛔ server không ghi status/job
                        // id xuống DB; trạng thái chỉ nằm trên dòng TRONG PHIÊN
                        // này, đóng tab là mất — Owner chốt 2026-11-21).
                        $container.html(self._preview_progress_html(
                            r.message.message || __("Đang tính BOM lớn trong nền — có thể mất vài phút...")
                        ));
                        self._write_result_to_row(null, {
                            status: "Queued", job_id: r.message.job_id || "",
                        });
                        self._listen_realtime(r.message.job_id, $container, capturedSig);
                    } else {
                        // Kết quả đồng bộ — ghi ĐỦ bộ xuống dòng TRÊN FORM
                        // (al_bom_result + al_gia_ban + al_gia_vat + rate + trạng
                        // thái); DB chỉ đổi khi người dùng bấm Lưu báo giá.
                        self._write_result_to_row(r.message, { status: "Success" });
                        self._preview_unsaved = true;
                        // `rate` vừa đổi ⇒ tổng tiền trên màn hình phải tính lại
                        // (server không còn ghi tổng giúp).
                        alumglass.quotation._refresh_totals(self.frm);
                        self._render_display_model(
                            $container, is_local ? "" : cdn, manual,
                            JSON.stringify(r.message));
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
                // Instance đã đóng ⇒ ⛔ vẽ lỗi lên dialog đã đóng; chỉ mở khoá.
                if (self._dialog_open === false) {
                    self._finish_preview_waiters();
                    return;
                }
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
    // `result_json` (tuỳ chọn) = chuỗi `al_bom_result` ĐANG NẰM TRÊN DÒNG — khi
    // có, server dựng display từ chính chuỗi đó thay vì đọc DB (mở lại dialog
    // phải thấy đúng kết quả của dòng, kể cả khi dòng mới hơn bản trong DB).
    // Rỗng ⇒ giữ nguyên đường đọc DB cũ.
    _render_display_model($container, qi_name, force_notify, result_json) {
        const self = this;
        if (!$container || !$container.length) $container = this._preview_container();
        if (!$container.length) return;

        // Dòng MỚI (`new-…`) chưa có trong DB ⇒ server không có gì để tra
        // quyền / cost template, và API đọc DB sẽ ném "không tìm thấy dòng".
        // Dựng bảng NGAY từ kết quả trong tay, cùng renderer dùng chung.
        const is_local = !qi_name || String(qi_name).indexOf("new-") === 0;
        if (is_local) {
            this._render_result_json($container, result_json, force_notify);
            return;
        }

        // Dòng Quotation Item đang mở — cần cho nút "Vì sao ra số này?" của
        // từng dòng vật tư (dialog giải thích cần biết tra ở dòng nào).
        const qi_ref = (this.child_doc && this.child_doc.name) || qi_name;

        const args = { quotation_item_name: qi_name };
        if (result_json) args.result_json = result_json;

        frappe.call({
            method: "alumglass.api.get_result_display",
            args: args,
            callback: (r) => {
                if (!$container || !$container.length) return;
                if (r.message && r.message.summary && r.message.summary.calculated) {
                    // F2: `errors` (kính VƯỢT khổ tối đa, lỗi công thức...) nay
                    // được dán ngay TRÊN bảng kết quả + popup một lần — trước
                    // đây frontend bỏ qua hoàn toàn nên báo giá sai không ai biết.
                    $container.html(self._unsaved_banner()
                        + alumglass.calc_errors_banner(r.message.errors)
                        + alumglass.render_bom_result_display(r.message, {
                            compact: true, show_trace: false,
                            quotation_item: qi_ref,
                            // Kết quả vừa tính (chưa/không lưu DB) ⇒ nút
                            // "Vì sao ra số này?" giải thích CHÍNH kết quả này.
                            explain_result_json: result_json || "",
                            explain_parent: (self.frm && self.frm.doc && self.frm.doc.name) || "",
                        }));
                    alumglass.notify_calc_errors(r.message.errors, {
                        dedupe_key: qi_name, force: !!force_notify,
                    });
                    return;
                }
                // Server trả display trống (chưa tính / chưa lưu) — fallback raw nếu có
                self._render_result_json($container, result_json, force_notify);
            },
            error: (err) => {
                if ($container && $container.length) {
                    $container.html(self._preview_error_html(err));
                }
            },
        });
    }

    // Render kết quả THÔ (response engine) bằng renderer dùng chung.
    // Dùng cho: dòng MỚI (chưa có tên trong DB) và khi server không dựng
    // được display model. `result_json` = chuỗi JSON client vừa nhận.
    _render_result_json($container, result_json, force_notify) {
        if (!$container || !$container.length) return;
        let raw = null;
        try { raw = JSON.parse(result_json || "{}"); } catch (e) { raw = null; }
        if (!raw || (!raw.lines && !raw.cost_template)) {
            $container.html(this._preview_progress_html(__("Đang tải kết quả...")));
            return;
        }
        const is_local = !this.child_doc || !this.child_doc.name
            || String(this.child_doc.name).indexOf("new-") === 0;
        const qi_ref = is_local ? "" : (this.child_doc && this.child_doc.name) || "";
        $container.html(this._unsaved_banner()
            + alumglass.calc_errors_banner(raw.errors)
            + alumglass.render_bom_result_display(
                alumglass.raw_to_display(raw), {
                    compact: true, show_trace: false,
                    quotation_item: qi_ref,
                    // Dòng MỚI: không có dòng trong DB ⇒ nguồn DUY NHẤT để
                    // giải thích là kết quả đang hiển thị (`result_json`).
                    explain_result_json: result_json || "",
                    explain_parent: (this.frm && this.frm.doc && this.frm.doc.name) || "",
                }));
        alumglass.notify_calc_errors(raw.errors, {
            dedupe_key: (this.child_doc && this.child_doc.name) || "preview-local",
            force: !!force_notify,
        });
    }

    // Chỉ báo "kết quả CHƯA lưu" — bắt buộc phải có cùng phase 1 (design §5.3):
    // preview ⛔ không ghi DB, người dùng có thể tưởng giá đã lưu và gửi khách
    // bản in mang giá CŨ. Câu chữ: người-đọc-được, nêu đúng việc cần làm VÀ
    // hậu quả nếu bỏ qua (UX1 2026-11-21 — câu cũ thiếu vế hậu quả).
    _unsaved_banner() {
        if (!this._preview_unsaved) return "";
        return `<div class="al-preview-unsaved" style="margin-bottom:6px;padding:6px 8px;
            background:#eef2ff;border:1px solid #c7d2fe;border-radius:4px;font-size:12px;color:#3730a3;">
            💾 ${__("Giá vừa tính chưa được lưu vào báo giá. Bấm nút Lưu ở thanh trên để ghi lại — đóng trang hoặc tải lại là mất kết quả này.")}</div>`;
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

    // ── Thu thập `al_bom_vars` từ TRẠNG THÁI HIỆN TẠI của dialog ────
    // THUẦN ĐỌC: ⛔ không ghi dòng/DB. Tách khỏi `_save()` để đường hỏi giá
    // kính (phase 1.5) gửi server đúng biến người dùng đang sửa — preview
    // không còn ghi DB trước khi hỏi giá.
    _collect_vars() {
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
        return vars;
    }

    // ── Tham số dòng ĐANG NẰM TRÊN DIALOG (phase 1.5) ──────────────
    // Cùng whitelist với `preview_bom`. Dùng cho các API CHỈ ĐỌC cần biết
    // trạng thái người dùng đang thấy (`get_variable_set_for_bom`,
    // `get_glass_master_price`) — preview ⛔ không ghi DB nên server đọc DB
    // sẽ ra bản CŨ/rỗng.
    // Nguồn `al_bom_vars`:
    //   · dialog đã dựng vùng biến/kính (_var_controls/_glass_controls) ⇒
    //     `_collect_vars()` — biến người dùng ĐANG sửa;
    //   · còn lại (vd vừa mở dialog, chưa dựng) ⇒ chuỗi trên DÒNG đang mở.
    // ⛔ Không gửi tiền tệ/bảng giá/khách hàng — server luôn đọc từ cha trong DB.
    _dialog_state_params() {
        const values = this._collect_row_values();
        let vars_json = values.al_bom_vars || "{}";
        const collected = (this._var_controls && this._var_controls.length)
            || (this._glass_controls && this._glass_controls.length);
        if (collected) {
            try {
                vars_json = JSON.stringify(this._collect_vars());
            } catch (e) {
                vars_json = values.al_bom_vars || "{}";
            }
        }
        return {
            al_bom: values.al_bom || "",
            al_bom_version: values.al_bom_version || "",
            al_bom_vars: vars_json,
            item_code: values.item_code || "",
            item_name: values.item_name || "",
            parent: (this.frm && this.frm.doc && this.frm.doc.name) || "",
            parenttype: "Quotation",
        };
    }

    _save(opts) {
        const vars = this._collect_vars();

        // ── Lưu vào Quotation Item ─────────────────────────────────
        // ⛔ KHÔNG ghi DB ở đây: chỉ cập nhật dòng TRÊN PHIẾU (bộ nhớ trình
        // duyệt) + đánh dấu phiếu "có thay đổi". DB chỉ ghi khi người dùng
        // bấm Lưu báo giá (yêu cầu Owner 2026-11-21). Ngoại lệ duy nhất là
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

        // Chẩn đoán (chỉ Console, ⛔ ném): ghi xong mà version TRÊN DIALOG vẫn
        // khác version của dòng trên lưới ⇒ có đường khác đang đè giá trị vừa
        // ghi. Bỏ qua ô trống/không đọc được (ô trống ≠ bằng chứng lệch).
        try {
            const dialogVersion = this._dialog_field_value("al_bom_version");
            const row = this._find_form_row();
            if (dialogVersion && row) {
                const norm = (v) => (v === undefined || v === null ? "" : String(v));
                if (norm(dialogVersion) !== norm(row.al_bom_version)) {
                    console.warn("[alumglass] ghi version xong vẫn lệch",
                        { dialog: dialogVersion, row: row.al_bom_version });
                }
            }
        } catch (e) { /* chỉ là chẩn đoán — ⛔ được làm hỏng việc lưu */ }

        // Phiếu phải mang cờ "có thay đổi" để nút Lưu của form bật — kể cả khi
        // chỉ có `al_bom_vars` đổi (giá trị mới giống hệt giá trị cũ).
        if (this.frm && this.frm.doc && !this.frm.doc.__unsaved) {
            this.frm.doc.__unsaved = 1;
        }

        // ⛔ KHÔNG tự bắn thông báo: toast bắn khi dialog còn mở sẽ bị modal
        // che, và nhánh chờ preview (tới 20s) làm toast 7s hết hạn trước khi
        // người dùng đọc. Trả thông tin để `_on_primary_action` báo SAU
        // `dialog.hide()`. `opts.notify` giữ lại cho tương thích lời gọi cũ
        // nhưng không còn tác dụng — mọi đường gọi `_save()` đều im lặng.
        return {
            row_name: cdn || "",
            // `al_bom_vars` vừa thu thập — `_run_preview` gửi nguyên chuỗi này
            // trong `params` của `preview_bom` (engine ⛔ không đọc DB nữa).
            vars_json: vars_json,
            is_new: !!(
                String(cdn || "").indexOf("new-") === 0
                || (this.child_doc && this.child_doc.__islocal)
            ),
        };
    }

    // Thông báo trạng thái của nút 💾 Lưu — gọi SAU khi dialog đóng.
    // Màu XANH DƯƠNG, ⛔ không xanh lá: trong app này xanh lá nghĩa là đã xong
    // thật (đã ghi DB), còn ở đây mới chỉ sửa dòng trên form.
    // Từ phase 1 "Preview không ghi DB" (Owner chốt 2026-11-21) MỌI đường lưu
    // của dialog đều chỉ ghi dòng trên form — kể cả dòng mới (⛔ không còn
    // `frm.save()` ngầm) ⇒ chỉ còn 2 câu, theo dòng cũ/mới.
    // Câu dài hơn 100 ký tự ⇒ để 7 giây cho người dùng đọc kịp.
    _notify_params_applied(info) {
        info = info || {};
        const message = info.is_new
            ? __("Đã thêm dòng vào phiếu — chưa lưu vào báo giá. Bấm nút Lưu trên báo giá để lưu.")
            : __("Đã áp dụng tham số vào dòng này — chưa lưu vào báo giá. Bấm nút Lưu trên báo giá để lưu.");
        frappe.show_alert({ message: message, indicator: "blue" }, 7);
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
    // `params` (tuỳ chọn) = tham số dòng ĐANG NẰM TRÊN FORM (al_bom,
    // al_bom_version, al_bom_vars…). Có params ⇒ cửa sổ này chạy
    // `preview_bom` (⛔ không ghi DB) ngay, không đọc trạng thái cũ trong DB —
    // dòng có thể mới hơn bản đã lưu. Không params (lời gọi bên ngoài) ⇒ vẫn
    // hiện trạng cũ đọc `al_calc_status` trong DB.
    //
    // `frm` (tuỳ chọn) = form Quotation đang mở — cần để nút "Áp dụng vào dòng"
    // ghi kết quả xuống dòng TRÊN FORM (⛔ vẫn không ghi DB). Không truyền ⇒
    // rơi về `cur_frm`.
    constructor(quotation_item_name, params, frm) {
        this.quotation_item_name = quotation_item_name;
        this.params = params || null;
        this.frm = frm || null;
        this.dialog = null;
        this._realtime_handler = null;
        // Cửa sổ còn mở? Kết quả job nền về MUỘN (sau khi người dùng đã đóng
        // bằng X/Esc) ⛔ được tự bật lại cửa sổ — người dùng đã chủ động đóng.
        this._dialog_open = false;
        // Kết quả đang HIỂN THỊ — nút "Áp dụng vào dòng" dùng đúng số này.
        this._result = null;
        // Kết quả đọc từ DB (mở cửa sổ ⛔ kèm tham số) ⇒ dòng đã mang số đó:
        // ⛔ ghi lại, ⛔ hiện câu "chưa ghi vào báo giá" (nói sai sự thật).
        this._result_from_db = false;
    }

    show() {
        this.dialog = new frappe.ui.Dialog({
            title: __("Kết quả tính giá"),
            fields: [
                {
                    fieldname: "result_html",
                    fieldtype: "HTML",
                }
            ],
            size: "large",
            // Preview ⛔ ghi DB (phase 1) ⇒ cửa sổ này CHỈ để xem; dòng báo giá
            // chỉ đổi khi người dùng bấm nút chính (UX1 2026-11-21).
            primary_action_label: __("Áp dụng vào dòng"),
            primary_action: () => this._apply_to_form_row(),
            secondary_action_label: __("Đóng"),
            secondary_action: () => this.dialog.hide(),
            // Đóng bằng X/Esc/click nền cũng phải nhả trạng thái (Frappe phát
            // `onhide` cho MỌI đường đóng). `_on_hidden` idempotent.
            onhide: () => this._on_hidden(),
        });
        this._dialog_open = true;
        // Chưa có kết quả ⇒ ⛔ cho bấm "Áp dụng vào dòng" (bấm mà ⛔ có gì để
        // ghi thì chỉ đóng cửa sổ im lặng). Bật lại khi kết quả về.
        this._update_apply_button();

        // Cleanup listener khi dialog đóng (tránh leak realtime handler)
        $(this.dialog.$wrapper).on("hidden.bs.modal", () => this._on_hidden());

        this._load_existing_state();
    }

    // Người dùng đóng cửa sổ (nút Đóng, X, Esc, click ra ngoài) — `onhide`
    // của Frappe ⛔ phát cho MỌI đường đóng nên phải gắn cả 2 chỗ dưới đây;
    // `_on_hidden` idempotent.
    _on_hidden() {
        this._dialog_open = false;
        this._cleanup_realtime();
    }

    // Bật/tắt nút "Áp dụng vào dòng" theo việc CÓ kết quả để áp hay ⛔.
    _update_apply_button() {
        const dlg = this.dialog;
        if (!dlg) return;
        // Có kết quả VÀ có ĐÍCH để ghi (form + tên dòng). Thiếu đích thì ⛔ cho
        // bấm: bấm rồi `_apply_to_form_row` thoát im lặng khiến người dùng
        // tưởng đã áp dụng xong (đóng cửa sổ mà ⛔ ghi gì).
        const cdn = this.quotation_item_name || "";
        const frm = this._resolve_frm();
        const can_apply = !!(this._result && !this._result_from_db && frm && cdn);
        const method = can_apply ? "enable_primary_action" : "disable_primary_action";
        if (typeof dlg[method] === "function") dlg[method]();
    }

    // ── Mở lại: đọc trạng thái đã lưu trên Quotation Item ───────────
    _load_existing_state() {
        const self = this;
        // Có params ⇒ tham số trên form MỚI HƠN bản trong DB (có thể chưa Lưu)
        // ⇒ tính thử ngay, ⛔ không hiện kết quả cũ đã lưu.
        if (this.params) {
            this.calculate();
            return;
        }
        frappe.db.get_value("Quotation Item", this.quotation_item_name, [
            "al_calc_status", "al_calc_job_id", "al_bom_result", "al_calc_error",
        ], (r) => {
            if (r) {
                if (r.al_calc_status === "Success" && r.al_bom_result) {
                    // Kết quả đã lưu — render luôn, KHÔNG gọi lại API
                    let data = null;
                    try { data = JSON.parse(r.al_bom_result); } catch (e) { /* ignore */ }
                    if (data) {
                        this._result_from_db = true;
                        this.render_results(data);
                        return;
                    }
                }
                if (r.al_calc_status === "Queued" || r.al_calc_status === "Running") {
                    // Đang tính trong nền — không gọi lại, chỉ chờ realtime
                    this._show_async_progress(
                        r.al_calc_job_id,
                        __("BOM đang xếp hàng tính trong nền. Kết quả chỉ nhận được khi cửa sổ này còn mở — nếu không thấy, đóng cửa sổ rồi bấm lại 🖥️ Preview tính giá.")
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
        const name = this.quotation_item_name || "";
        const is_local = !name || String(name).indexOf("new-") === 0;

        // `preview_bom` — ⛔ KHÔNG ghi DB. Có params ⇒ engine tính từ đúng
        // tham số đang hiện trên form; không params ⇒ engine đọc dòng DB
        // (tương thích lời gọi cũ) nhưng kết quả vẫn CHỈ hiển thị.
        frappe.call({
            method: "alumglass.api.preview_bom",
            args: {
                quotation_item_name: is_local ? "" : name,
                params: JSON.stringify(this.params || {}),
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
                // Preview ⛔ ghi DB ⇒ XANH DƯƠNG + nói rõ chưa lưu.
                // ⛔ chèn `quotation_item_name` vào câu: đó là docname dòng con
                // (Frappe sinh hash `7f3a91c0d2…`) — người dùng ⛔ đọc được.
                alumglass.quotation._show_preview_toast(
                    __("Tính giá xong — chưa lưu vào báo giá."));
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
            // Có kết quả trong tay ⇒ bật "Áp dụng vào dòng"; chưa có ⇒ tắt.
            this._update_apply_button();
            // Người dùng đã đóng cửa sổ (X/Esc/backdrop) ⇒ ⛔ bật lại; kết quả
            // job nền về muộn chỉ cập nhật nội dung cho lần mở sau.
            if (this._dialog_open !== false) this.dialog.show();
        }
    }

    // ── Render kết quả (sync hoặc async Success) ────────────────────
    // Lấy display model (label + công thức + trace) từ server rồi render
    // qua renderer DÙNG CHUNG `alumglass.render_bom_result_display` —
    // cùng renderer với ItemParamDialog (preview), không duplicate code.
    render_results(data) {
        const self = this;
        const name = this.quotation_item_name || "";
        const is_local = !name || String(name).indexOf("new-") === 0;
        // Kết quả đang HIỂN THỊ = thứ nút "Áp dụng vào dòng" sẽ ghi xuống dòng.
        this._result = data || null;

        // Dòng MỚI chưa có trong DB ⇒ ⛔ gọi API đọc DB (sẽ ném "không tìm
        // thấy dòng"). Render ngay từ kết quả vừa nhận.
        if (is_local) {
            this._render_raw(data);
            return;
        }

        frappe.call({
            method: "alumglass.api.get_result_display",
            args: {
                quotation_item_name: name,
                // Truyền chính kết quả vừa tính: dòng trên form có thể MỚI
                // hơn bản đã lưu (preview ⛔ không ghi DB).
                result_json: data ? JSON.stringify(data) : undefined,
            },
            callback: (r) => {
                if (r.message && r.message.summary && r.message.summary.calculated) {
                    // F2: lỗi/cảnh báo engine trả kèm (`errors`) → banner trên
                    // kết quả + popup (force: user vừa chủ động mở/tính).
                    self._set_html(self._preview_note_html()
                        + alumglass.calc_errors_banner(r.message.errors)
                        + alumglass.render_bom_result_display(r.message, {
                            collapsible: true,
                            show_trace: true,
                            title: __("Kết quả tính giá"),
                            quotation_item: name,
                            // Kết quả vừa tính (⛔ chưa ghi DB) ⇒ giải thích
                            // đúng kết quả này, không đọc bản cũ trong DB.
                            explain_result_json: data ? JSON.stringify(data) : "",
                            explain_parent: self._explain_parent(),
                        }));
                    alumglass.notify_calc_errors(r.message.errors, {
                        dedupe_key: name, force: true,
                    });
                    return;
                }
                self._render_raw(data);
            },
            error: () => {
                // Lỗi mạng/API → vẫn render được bằng raw data (fallback)
                self._render_raw(data);
            },
        });
    }

    // Render kết quả THÔ bằng renderer dùng chung (fallback / dòng mới).
    _render_raw(data) {
        if (data) this._result = data;
        // F2: raw data cũng có thể mang `errors` → vẫn phải dán banner
        this._set_html(this._preview_note_html()
            + alumglass.calc_errors_banner((data || {}).errors)
            + alumglass.render_bom_result_display(
                alumglass.raw_to_display(data || {}), {
                    collapsible: true,
                    show_trace: true,
                    title: __("Kết quả tính giá"),
                    // Dòng chưa có trong DB ⇒ không có tên thật để server tra;
                    // vẫn gắn nút khi có kết quả trong tay (phase 1.5).
                    quotation_item: String(this.quotation_item_name || "").indexOf("new-") === 0
                        ? "" : (this.quotation_item_name || ""),
                    explain_result_json: data ? JSON.stringify(data) : "",
                    explain_parent: this._explain_parent(),
                }));
    }

    // Dòng nhắc BẮT BUỘC của cửa sổ kết quả (UX1 2026-11-21): cửa sổ này chỉ
    // để XEM — ⛔ ghi gì xuống báo giá cho tới khi bấm "Áp dụng vào dòng".
    // Kết quả đọc từ DB thì số đã nằm trên báo giá ⇒ ⛔ hiện câu này.
    _preview_note_html() {
        if (this._result_from_db) return "";
        return `<div class="al-preview-readonly" style="margin-bottom:6px;padding:6px 8px;
            background:#f1f5f9;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;color:#334155;">
            👁️ ${__("Kết quả chỉ để xem — chưa ghi vào báo giá. Bấm \"Áp dụng vào dòng\" nếu muốn dùng kết quả này.")}</div>`;
    }

    // Form Quotation đang mở — ưu tiên tham số truyền vào, rồi `cur_frm`.
    _resolve_frm() {
        if (this.frm) return this.frm;
        try {
            if (typeof cur_frm !== "undefined" && cur_frm && cur_frm.doc) return cur_frm;
        } catch (e) { /* không có form → bỏ qua */ }
        return null;
    }

    // Nút "Áp dụng vào dòng": ghi KẾT QUẢ ĐANG HIỂN THỊ xuống dòng trên form
    // qua đúng hàm dùng chung (`_apply_result_to_row`) + tính lại tổng + đánh
    // dấu phiếu có thay đổi. ⛔ KHÔNG ghi DB — chỉ nút Lưu báo giá mới ghi.
    _apply_to_form_row() {
        const result = this._result;
        const frm = this._resolve_frm();
        const cdn = this.quotation_item_name || "";
        // Kết quả đọc từ DB (mở cửa sổ ⛔ kèm tham số) ⇒ dòng đã mang đúng số
        // đó: ⛔ ghi lại, ⛔ báo "chưa lưu" (nói sai sự thật). Đóng cửa sổ.
        if (this._result_from_db) {
            if (this.dialog) this.dialog.hide();
            return;
        }
        // CHƯA có kết quả / thiếu đích ⇒ ⛔ làm gì (nút đã bị disable; đóng cửa
        // sổ im lặng ở đây từng khiến người dùng tưởng đã áp dụng xong).
        if (!result || !frm || !cdn) return;
        const rows = (frm.doc && frm.doc.items) || [];
        const row = rows.find((r) => r && r.name === cdn) || null;
        alumglass.quotation._apply_result_to_row(
            frm, "Quotation Item", cdn, result, { row: row });
        alumglass.quotation._refresh_totals(frm);
        if (typeof frm.dirty === "function") frm.dirty();
        if (typeof frm.refresh_field === "function") frm.refresh_field("items");
        if (this.dialog) this.dialog.hide();
        // Đóng cửa sổ RỒI mới báo (toast bị modal che). XANH DƯƠNG + nói rõ
        // chưa lưu: xanh lá trong sản phẩm này = đã ghi DB thật.
        frappe.show_alert({
            message: __("Đã áp dụng kết quả vào dòng này — chưa lưu vào báo giá. Bấm nút Lưu trên báo giá để lưu."),
            indicator: "blue",
        }, 7);
    }

    // Quotation cha — chỉ dùng cho dòng MỚI (server kiểm quyền `read`).
    // Ưu tiên tham số dòng đang mở (đường từ form), rồi form hiện tại.
    _explain_parent() {
        if (this.params && this.params.parent) return this.params.parent;
        try {
            if (typeof cur_frm !== "undefined" && cur_frm && cur_frm.doc) {
                return cur_frm.doc.name || "";
            }
        } catch (e) { /* không có form → bỏ qua */ }
        return "";
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

        // Phase 2 (Owner chốt 2026-11-21): in khi còn kết quả preview CHƯA lưu
        // ⇒ hộp thoại "Lưu rồi in" (⛔ in bản cũ). Frappe ⛔ bắn sự kiện client
        // `before_print` ⇒ phải bọc `frm.print_doc` (xem `_attach_print_guard`).
        _attach_print_guard(frm);
    },

    after_save(frm) {
        // 🔴2 (UX1 2026-11-21): preview ⛔ ghi DB thì dấu "chưa lưu" phải TẮT
        // ngay sau khi báo giá LƯU XONG. Dấu bám OBJECT dòng (WeakSet) mà
        // `frappe.model.sync` cập nhật TẠI CHỖ ⇒ object giữ identity, ⛔ tự
        // mất. Không xoá thì banner "giá vừa tính chưa được lưu" nằm mãi.
        alumglass.quotation._clear_preview_marks(frm);
        setTimeout(() => _attach_row_actions(frm), 600);
    },
});

// Bọc `frm.print_doc` MỘT lần cho mỗi form — Frappe ⛔ có sự kiện client
// `before_print`, không bọc thì phần chặn in là code chết.
//
// Phase 2 (Owner chốt 2026-11-21 — "bắt Lưu trước"): in khi báo giá còn dòng
// mang kết quả preview CHƯA lưu ⇒ **hộp thoại chặn mềm** "Lưu rồi in" / "Huỷ".
// ⛔ Có nút "vẫn in bản cũ": bản in có thể rơi về bản đã lưu (in từ danh sách,
// in lại, PDF cũ…) nên in ngay ⛔ chắc khớp số đang hiện trên màn hình.
// ⛔ Không chặn ở tầng server (server không biết client còn kết quả chưa lưu).
function _attach_print_guard(frm) {
    if (!frm || frm.__al_print_guard) return;
    if (typeof frm.print_doc !== "function") return;
    const orig = frm.print_doc;
    frm.print_doc = function () {
        const args = arguments;
        const self = this;
        const do_print = () => orig.apply(self, args);
        // Lượt in do CHÍNH hộp thoại phát lại ⇒ in thẳng, ⛔ hỏi vòng.
        if (frm.__al_print_bypass) return do_print();
        // Đang lưu cho một lượt in trước ⇒ ⛔ in chồng (chống đệ quy/đua).
        if (frm.__al_print_busy) return undefined;
        if (!alumglass.quotation._has_unsaved_preview(frm)) return do_print();
        return _al_offer_save_then_print(frm, do_print);
    };
    // ⛔ enumerable: cờ client-only, ⛔ được lẫn vào payload nào.
    _al_define_hidden(frm, "__al_print_guard", true);
}

// Đặt property client-only KHÔNG enumerable để ⛔ lọt vào payload gửi server.
function _al_define_hidden(obj, key, value) {
    try {
        Object.defineProperty(obj, key, {
            value: value, configurable: true, writable: true, enumerable: false,
        });
    } catch (e) {
        obj[key] = value;
    }
}

// Báo giá CHƯA từng lưu lần nào? Dùng cho câu lỗi lưu-thất-bại: phiếu mới thì
// tải lại trang mất TOÀN BỘ nội dung vừa nhập (⛔ phải "kết quả vừa tính").
// Form không có `is_new` (form giả/khác phiên bản) ⇒ coi như ĐÃ lưu để câu lỗi
// là bản nhẹ hơn, ⛔ hù người dùng bằng cảnh báo mất dữ liệu sai.
function _al_form_is_new(frm) {
    if (!frm || typeof frm.is_new !== "function") return false;
    try {
        return !!frm.is_new();
    } catch (e) {
        return false;
    }
}

// Hộp thoại "Lưu rồi in". Chỉ có 2 lối: Lưu rồi in, hoặc Huỷ — ⛔ lối in bản
// cũ. `print_fn` = ĐÚNG lệnh in người dùng vừa bấm (đã chụp tham số) ⇒ lưu
// xong phát lại y nguyên.
function _al_offer_save_then_print(frm, print_fn) {
    if (frm.__al_print_dialog_open) return undefined;  // ⛔ mở 2 hộp
    frm.__al_print_dialog_open = true;
    let dlg = null;

    const close = () => {
        frm.__al_print_dialog_open = false;
        if (dlg) dlg.hide();
    };

    const start_save = () => {
        if (frm.__al_print_busy) return;   // đang lưu ⇒ ⛔ chạy lượt nữa
        frm.__al_print_busy = true;
        close();
        let settled = false;
        // Timer chốt hạn: `frm.save()` của Frappe có nhánh KHÔNG gọi callback và
        // KHÔNG resolve (thiếu trường bắt buộc / "No changes in document") ⇒
        // thiếu backstop thì cờ `__al_print_busy` kẹt vĩnh viễn, mọi lần In sau
        // `return` im lặng phải tải lại trang.
        let backstop = null;
        const finish = (ok, opts) => {
            if (settled) return;
            settled = true;
            if (backstop) { clearTimeout(backstop); backstop = null; }
            frm.__al_print_busy = false;
            if (!ok) {
                // Hết hạn chờ lưu: câu riêng, chỉ đúng việc cần làm (lỗi thật
                // Frappe đã hiện trên màn hình; người dùng kiểm rồi thử lại).
                if (opts && opts.timeout) {
                    frappe.msgprint({
                        message: __("Chưa lưu xong báo giá nên chưa in. Kiểm tra thông báo lỗi trên màn hình rồi thử lại."),
                        indicator: "red",
                    });
                    return;
                }
                // Câu người-đọc-được, ⛔ traceback, ⛔ in. Nêu LỐI THOÁT cho
                // người chỉ muốn cầm bản in (⛔ thêm nút thứ 3 vào hộp thoại).
                //
                // Câu phải rẽ theo báo giá CHƯA từng lưu: với phiếu mới, tải
                // lại trang là mất TOÀN BỘ nội dung vừa nhập — ⛔ phải "chỉ mất
                // kết quả vừa tính" như câu của phiếu đã lưu.
                frappe.msgprint({
                    message: _al_form_is_new(frm)
                        ? __("Chưa lưu được báo giá nên chưa in. Sửa lỗi vừa hiện rồi bấm Lưu lại — báo giá chưa được lưu lần nào, tải lại trang sẽ mất toàn bộ nội dung vừa nhập.")
                        : __("Chưa lưu được báo giá nên chưa in. Sửa lỗi vừa hiện rồi bấm Lưu lại. Nếu chỉ cần in bản đã lưu thì tải lại trang (kết quả vừa tính sẽ mất)."),
                    indicator: "red",
                });
                return;
            }
            // Lưu xong (`after_save` đã xoá dấu "chưa lưu") ⇒ phát lại đúng
            // lệnh in ban đầu (cùng tham số), ⛔ đi qua hộp thoại lần nữa.
            frm.__al_print_bypass = true;
            try { print_fn(); } finally { frm.__al_print_bypass = false; }
        };
        backstop = setTimeout(() => finish(false, { timeout: true }), 30000);

        try {
            let ret = null;
            if (typeof frm.save === "function") {
                // `frm.save` của Frappe NUỐT lỗi trong promise (chỉ log) ⇒ phải
                // dựa vào `callback`/`on_error` để biết lưu THẬT SỰ xong.
                ret = frm.save(undefined, (r) => {
                    if (r && r.exc) finish(false); else finish(true);
                }, undefined, () => finish(false));
            } else if (typeof frm.save_or_update === "function") {
                ret = frm.save_or_update();
            } else {
                throw new Error("form không có hàm lưu");
            }
            // Backstop cho form không gọi callback (vd tài liệu không bẩn).
            // ⚠️ `frm.save()` resolve KỂ CẢ khi validate ném (Frappe `.catch`
            // chỉ log) ⇒ ⛔ được coi là xong: chỉ xong khi phiếu HẾT BẨN.
            // `finish` chạy MỘT lần nên ⛔ in 2 lần.
            if (ret && typeof ret.then === "function") {
                ret.then(() => {
                    if (typeof frm.is_dirty === "function" && frm.is_dirty()) {
                        return finish(false);
                    }
                    finish(true);
                }, () => finish(false));
            }
        } catch (e) {
            finish(false);
        }
    };

    // Tiêu đề phải đúng với CẢ HAI trường hợp: báo giá chưa từng lưu thì ⛔ có
    // "giá đã lưu" nào để nói tới. Nội dung cũng ⛔ khẳng định "bản in là bản
    // cũ": `frappe/www/printview.py` nhận chính document từ trình duyệt khi
    // `form_dict.doc` có (⛔ luôn đọc DB).
    const is_new = (typeof frm.is_new === "function")
        ? !!frm.is_new()
        : !!(frm.doc && (frm.doc.__islocal || frm.doc.__unsaved && !frm.doc.name));
    const dlg_title = is_new
        ? __("Báo giá chưa được lưu")
        : __("Báo giá có giá vừa tính chưa lưu");

    try {
        dlg = new frappe.ui.Dialog({
            title: dlg_title,
            fields: [{ fieldname: "al_print_msg", fieldtype: "HTML" }],
            primary_action_label: __("Lưu rồi in"),
            primary_action: () => start_save(),
            secondary_action_label: __("Huỷ"),
            secondary_action: () => close(),
            // Đóng bằng X/Esc/click nền ⇒ Frappe gọi `onhide`, ⛔ gọi
            // `secondary_action` ⇒ thiếu dòng này cờ kẹt `true` và MỌI lần in
            // sau bị chặn im lặng cả phiên.
            onhide: () => { frm.__al_print_dialog_open = false; },
        });
        const field = dlg.fields_dict && dlg.fields_dict["al_print_msg"];
        if (field && field.$wrapper && typeof field.$wrapper.html === "function") {
            field.$wrapper.html(`<p style="margin:0;font-size:13px;line-height:1.5;">
                ${__("Bạn vừa tính lại giá nhưng chưa lưu báo giá. Lưu báo giá rồi in để bản in chắc chắn khớp số trên màn hình.")}</p>`);
        }
        dlg.show();
    } catch (e) {
        // Không dựng được hộp thoại ⇒ cờ phải về false, nếu không mọi lần in
        // sau đều bị chặn im lặng (guard tưởng đang mở hộp).
        frm.__al_print_dialog_open = false;
        return null;
    }
    return dlg;
}

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
        // / Preview tính giá): số liệu đã chốt phải giữ nguyên. Chốt THẬT ở SERVER
        // (`assert_parent_editable` của preview_bom); docstatus ở đây chỉ đỡ mời
        // người dùng bấm sai, KHÔNG phải lớp bảo vệ.
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
                    // Lưu vars vào model TRÊN TRÌNH DUYỆT (⛔ không ghi DB)...
                    frappe.model.set_value(cdt, cdn, "al_bom_vars",
                        JSON.stringify(_collect_form_vars(innerFrm, cdn) || {}));
                    // ...rồi mở cửa sổ preview với params — engine tính từ
                    // tham số gửi kèm, ⛔ không đọc DB (phase 1). Truyền form để
                    // nút "Áp dụng vào dòng" ghi được xuống dòng (⛔ vẫn ⛔ DB).
                    new alumglass.BOMDialog(
                        cdn, alumglass.quotation._row_preview_params(innerFrm, row),
                        innerFrm).show();
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
    // Cùng lý do với `_attach_row_actions`: `fields_dict` có thể chưa có.
    if (!frm || !frm.fields_dict || !frm.fields_dict["items"]) return;
    const grid = frm.fields_dict["items"].grid;
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
// Chặn `frm` THIẾU `fields_dict` (form chưa render xong / form giả trong test /
// timer `after_save` bắn sau khi form đã đóng): trước đây đọc
// `frm.fields_dict["items"]` là ném TypeError **trong timer** ⇒ lỗi rò ra
// ngoài luồng, test xanh mà tiến trình vẫn chết (exit 1).
function _attach_row_actions(frm) {
    if (!frm || !frm.fields_dict || !frm.fields_dict["items"]) return;
    const grid = frm.fields_dict["items"].grid;
    if (!grid) return;

    // Dùng grid.wrapper để bắt cả row render sau
    const $grid = grid.wrapper ? $(grid.wrapper) : $(grid.$wrapper);
    if (!$grid.length) return;

    $grid.find(".grid-row").each(function () {
        const $row = $(this);
        if ($row.data("_al_btn")) return;
        $row.data("_al_btn", true);

        // Báo giá đã Submit/huỷ → KHÔNG gắn nút dòng nào + KHÔNG gắn double-click:
        // cả 📐 (ItemParamDialog → preview_bom) lẫn 🖥️ (BOMDialog → preview_bom)
        // đều tính lại giá, mà số liệu đã chốt phải giữ nguyên. Chốt THẬT nằm ở
        // SERVER (`assert_parent_editable` trong preview_bom); docstatus ở đây chỉ
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
                // Mở cửa sổ preview với tham số ĐANG CÓ trên form — engine tính
                // từ params, ⛔ không cần đồng bộ DB trước (phase 1). Truyền
                // form để nút "Áp dụng vào dòng" ghi được xuống dòng.
                new alumglass.BOMDialog(
                    rowDoc.name,
                    alumglass.quotation._row_preview_params(frm, rowDoc), frm).show();
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
    // (`assert_parent_editable` trong api.preview_bom); docstatus ở đây chỉ
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
    // 🟡6 (UX1 2026-11-21): tính CẢ dòng MỚI. Trước đây lọc `!r.is_new` rồi
    // báo "Chưa có dòng sản phẩm nào." trong khi lưới CÓ dòng — sai trạng thái.
    // `preview_bom` nhận `params` + `parent` nên tính được dòng chưa lưu.
    const rows = (frm.doc.items || []);
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
        if (!row.al_bom_vars) missing.push(__("chưa nhập tham số (mở Tham số BOM và bấm Áp dụng vào dòng)"));
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
    // Dòng rơi vào nhánh BOM lớn (async): server ⛔ không ghi DB, nên nếu
    // client không nghe realtime thì kết quả KHÔNG bao giờ tới dòng. Chỉ nghe
    // job do chính lượt này enqueue (lọc theo job_id).
    const pending_jobs = Object.create(null);
    let realtime_handler = null;
    const cleanup_realtime = () => {
        if (realtime_handler && frappe.realtime) {
            try { frappe.realtime.off("alumglass_bom_calc_done", realtime_handler); } catch (e) {}
        }
        realtime_handler = null;
    };
    const ensure_realtime = () => {
        if (realtime_handler || !frappe.realtime
            || typeof frappe.realtime.on !== "function") return;
        realtime_handler = function (data) {
            if (!data || !data.job_id || !pending_jobs[data.job_id]) return;
            // `pending_jobs[job_id]` = chính OBJECT dòng đã gửi job — cần cho
            // dòng MỚI (server trả `qi_name = ""` vì dòng chưa có tên trong
            // DB; dò theo tên sẽ ⛔ thấy dòng nào ⇒ kết quả rơi vào hư không).
            const target = pending_jobs[data.job_id];
            delete pending_jobs[data.job_id];
            const cdn = (target && target.name) || data.qi_name || "";
            if (data.status === "Success") {
                alumglass.quotation._apply_result_to_row(
                    frm, "Quotation Item", cdn, data.result || null,
                    { row: target });
                alumglass.quotation._refresh_totals(frm);
                if (typeof frm.dirty === "function") frm.dirty();
            } else {
                alumglass.quotation._apply_result_to_row(
                    frm, "Quotation Item", cdn, null, {
                        row: target,
                        status: "Failed",
                        error: data.error || "",
                    });
            }
            if (!Object.keys(pending_jobs).length) cleanup_realtime();
        };
        frappe.realtime.on("alumglass_bom_calc_done", realtime_handler);
    };
    const total = rows.length;
    const finish = () => {
        // `rate` của các dòng vừa đổi ⇒ tính lại tổng MỘT lần cho cả lô (⛔ không
        // gọi trong vòng lặp). Preview ⛔ không ghi DB nên server không ghi
        // tổng giúp; màn hình phải tự tính.
        alumglass.quotation._refresh_totals(frm);
        let msg = __("Đã tính {0}/{1} dòng", [done, total]);
        if (queued) msg += ` · ${__("{0} dòng đang tính nền — kết quả tự hiện khi xong", [queued])}`;
        if (failed) msg += ` · ${__("{0} dòng lỗi", [failed])}`;
        // 🔴3 (UX1 2026-11-21): preview ⛔ ghi DB ⇒ xanh lá (đã ghi thật) là
        // NÓI SAI. Xanh dương + nói rõ chưa lưu + việc cần làm; đỏ khi có lỗi.
        msg += __(" — chưa lưu vào báo giá. Bấm Lưu để ghi lại.");
        frappe.show_alert({ message: msg, indicator: failed ? "red" : "blue" }, 7);
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
    // Tham số gửi `preview_bom` cho 1 dòng — đúng thứ đang có trên FORM.
    // ⛔ Không gửi tiền tệ/bảng giá/khách hàng: server lấy từ Quotation cha.
    const preview_params = (row) => {
        const params = {
            al_bom: row.al_bom || "",
            al_bom_version: row.al_bom_version || "",
            al_bom_vars: row.al_bom_vars || "{}",
            item_code: row.item_code || "",
            item_name: row.item_name || "",
            parent: (frm.doc && frm.doc.name) || "",
            parenttype: "Quotation",
        };
        ["qty", "uom"].forEach((fieldname) => {
            if (row[fieldname] !== undefined && row[fieldname] !== null) {
                params[fieldname] = row[fieldname];
            }
        });
        return params;
    };
    const next = (i) => {
        if (i >= rows.length) { finish(); return; }
        const row = rows[i];
        const realName = row.name || "";
        const is_local = !realName || String(realName).indexOf("new-") === 0;
        // Ghi kết quả xuống dòng qua CÙNG hàm với dialog — nếu không, dòng
        // trên form lệch DB và lần Lưu báo giá ghi đè kết quả.
        const apply = (result, extra) => alumglass.quotation._apply_result_to_row(
            frm, "Quotation Item", realName, result,
            Object.assign({ row: row }, extra || {}));
        // ⛔ KHÔNG `_sync_row_to_db` (phase 1 "Preview không ghi DB"): tham số
        // đi trong `params`, engine dựng dòng từ đó.
        frappe.call({
            method: "alumglass.api.preview_bom",
            args: {
                quotation_item_name: is_local ? "" : realName,
                params: JSON.stringify(preview_params(row)),
            },
            callback: (r) => {
                if (!r.message) {
                    // Máy chủ trả rỗng cũng là một lượt HỎNG — phải nằm
                    // trên dòng, ⛔ không im lặng bỏ qua.
                    failed++;
                    apply(null, {
                        status: "Failed",
                        error: __("Tính giá thất bại. Vui lòng thử lại hoặc báo quản trị."),
                    });
                    next(i + 1);
                    return;
                }
                if (r.message.async) {
                    queued++;
                    // Nhớ job để nhận kết quả qua realtime (server ⛔ ghi DB,
                    // không nghe thì kết quả mất).
                    const job_id = r.message.job_id || "";
                    if (job_id) {
                        // Giữ ĐÚNG object dòng (⛔ chỉ cờ true): dòng MỚI có
                        // `qi_name = ""` nên ⛔ dò lại được theo tên.
                        pending_jobs[job_id] = row;
                        ensure_realtime();
                    }
                    apply(null, {
                        status: "Queued",
                        job_id: job_id,
                    });
                    next(i + 1);
                    return;
                }
                done++;
                // F2: response đồng bộ có `errors` (cảnh báo kính vượt khổ...).
                alumglass.collect_calc_errors(r.message.errors).forEach((it) => {
                    calc_issues.push({
                        severity: it.severity,
                        message: `${row.item_code || row.item_name || realName}: ${it.message}`,
                    });
                });
                // ĐỦ bộ: al_bom_result + al_gia_ban + al_gia_vat + rate
                // + trạng thái. Giá lấy từ `result.gia_ban/gia_vat`
                // (máy chủ đã tính), chỉ rơi về cost template khi
                // response bản cũ — ⛔ không `GIA_VAT || 0`.
                apply(r.message, { status: "Success" });
                if (typeof frm.dirty === "function") frm.dirty();
                next(i + 1);
            },
            error: (err) => {
                failed++;
                // D2: chỉ lưu câu người-đọc-được, không lưu stack trace.
                // `result = null` ⇒ ⛔ không xoá kết quả cũ trên dòng.
                apply(null, {
                    status: "Failed",
                    error: alumglass.sanitize_calc_error(
                        (err && err.message) || err || "").message,
                });
                next(i + 1);
            },
        });
    };
    frappe.show_alert({ message: __("Đang tính giá {0} dòng...", [total]), indicator: "orange" });
    next(0);
}

// ── C2 — Preview giá toàn bộ: dialog 90vw, từng sản phẩm + collapsible ──
function _preview_all_items(frm) {
    const all_rows = (frm.doc.items || []);
    // 🟡6 (UX1 2026-11-21): "Preview giá toàn bộ" đọc `get_result_display`
    // (đường ĐỌC DB) nên ⛔ dựng chi tiết cho dòng chưa lưu. Nhưng ⛔ được
    // báo "Chưa có dòng sản phẩm nào." khi lưới CÓ dòng — nói đúng trạng thái
    // và chỉ đúng việc cần làm.
    const rows = all_rows.filter((r) => !alumglass.quotation._row_is_new(r));
    const local_rows = all_rows.filter((r) => alumglass.quotation._row_is_new(r));
    const LOCAL_HINT = "{0} dòng chưa lưu trên báo giá nên chưa tính — mở 📐 Tham số BOM để tính.";
    if (!all_rows.length) {
        frappe.msgprint(__("Chưa có dòng sản phẩm nào."));
        return;
    }
    if (!rows.length) {
        frappe.msgprint(__(LOCAL_HINT, [local_rows.length]));
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

    // 🟡4: nói rõ nguồn số. Bảng tổng đọc `rate` trên FORM (có thể là giá vừa
    // preview, CHƯA lưu) còn chi tiết từng dòng đọc DB — trộn 2 nguồn mà ⛔
    // nói gì thì người dùng tin nhầm. Dòng preview chưa lưu ⇒ truyền chính
    // `al_bom_result` của dòng để chi tiết dùng ĐÚNG kết quả đang hiện.
    const notes = [];
    if (rows.some((r) => alumglass.quotation._is_preview_unsaved(r))) {
        notes.push(`<div class="al-pv-preview-note" style="margin-bottom:8px;padding:6px 8px;
            background:#eef2ff;border:1px solid #c7d2fe;border-radius:4px;font-size:12px;color:#3730a3;">
            💾 ${__("Giá đang hiện chưa lưu vào báo giá.")}</div>`);
    }
    if (local_rows.length) {
        notes.push(`<div class="al-pv-local-note" style="margin-bottom:8px;padding:6px 8px;
            background:#fffbeb;border:1px solid #fde68a;border-radius:4px;font-size:12px;color:#92400e;">
            ${__(LOCAL_HINT, [local_rows.length])}</div>`);
    }

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
    $c.html(notes.join("") + sum + details);

    // Nạp chi tiết từng sản phẩm (async, không chặn UI)
    rows.forEach((row) => {
        // 🟡4: dòng đang mang kết quả preview CHƯA lưu ⇒ đưa chính kết quả đó
        // cho server dựng display (API đã nhận `result_json`), nếu không chi
        // tiết đọc DB = giá CŨ trong khi bảng tổng đã là giá MỚI.
        const unsaved_result = alumglass.quotation._is_preview_unsaved(row)
            ? row.al_bom_result : null;
        const args = {
            quotation_item_name: row.name,
            result_json: unsaved_result
                ? (typeof unsaved_result === "string"
                    ? unsaved_result : JSON.stringify(unsaved_result))
                : undefined,
        };
        frappe.call({
            method: "alumglass.api.get_result_display",
            args: args,
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
// Đường "Tính giá" hàng loạt (form-level) — test Node thuần gọi trực tiếp qua
// `alumglass.quotation._calc_all_items` (test_quotation_glass_pick.js).
alumglass.quotation._calc_all_items = _calc_all_items;
// Cùng lý do: "Preview giá toàn bộ" (🟡4/🟡6 — nguồn số + dòng chưa lưu).
alumglass.quotation._preview_all_items = _preview_all_items;
// Cùng lý do: cảnh báo trước khi in (🟡9) — kiểm được mà ⛔ cần dựng cả form.
alumglass.quotation._attach_print_guard = _attach_print_guard;
// Cùng lý do: hộp thoại "Lưu rồi in" (phase 2) — test gọi trực tiếp.
alumglass.quotation._offer_save_then_print = _al_offer_save_then_print;
// Cùng lý do: chặn `frm` thiếu `fields_dict` (lỗi rò ra từ timer `after_save`).
alumglass.quotation._attach_row_actions = _attach_row_actions;

// File này là doctype_js nạp trong trình duyệt (không có `module`). Khi nạp
// bằng `require()` trong test Node thuần thì trả namespace `alumglass` để
// kiểm các hàm thuần (glass_pick...).
if (typeof module !== "undefined" && module.exports) {
    module.exports = alumglass;
}