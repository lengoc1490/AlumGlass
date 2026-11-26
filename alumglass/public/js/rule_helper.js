// ═══════════════════════════════════════════════════════════════════════════
// AlumGlass — Trợ giúp "chèn công thức" + "thử tra quy tắc"
// ═══════════════════════════════════════════════════════════════════════════
//
// VÌ SAO CÓ TỆP NÀY
// -----------------
// Người dựng báo giá phải điền số lượng nẹp / keo / bản lề bằng cách GÕ TAY
// `lookup_rule('RULE-...', items.kinh_tren.glass_thick)` — phải nhớ mã quy tắc
// và tên field kỹ thuật. Thiết kế `docs/design/tra-cuu-quy-tac-de-hieu.md`
// (chốt 2026-11-25) đổi thành: chọn bằng TÊN, hệ thống chèn đúng chuỗi.
//
// TỆP NÀY GỒM 2 PHẦN
// ------------------
//   1. HÀM THUẦN (không đụng DOM/frappe) — dựng chuỗi công thức, lọc quy tắc,
//      dựng danh sách "dữ liệu đem tra" có nhãn người đọc. Test bằng Node:
//          node alumglass/tests/js/test_rule_helper.js
//   2. HỘP THOẠI (chỉ chạy trên Desk) — chọn công thức / thử tra quy tắc.
//
// HỢP ĐỒNG API THỬ TRA (server do DEV1 làm — docs §3.2 + §7):
//   alumglass.api.preview_rule(rule_code, input_value) ->
//     { success, rule_name, rule_description, input_label, input_unit,
//       input_variable, input_scope, output_label, is_active,
//       matched:{kind,from,to,key}|null,
//       result:{value}|{item_code,item_name}|null,
//       rows:[{from,to,key,result_text,is_match}], message }
//   Lỗi gọi API KHÔNG bị nuốt thành "im lặng": helper trả một object đánh dấu
//   `__preview_error` kèm NGUYÊN VĂN câu `_server_messages` để hộp thoại hiện
//   đúng lý do (rỗng mới dùng câu trung tính + nút Thử lại).
//
// CHẶNG 3 — QUY TẮC TỰ KHAI "TRA THEO CÁI GÌ" (docs §7):
//   `AL Rule.input_variable` (biến đem tra) + `input_scope` (ROW/GLOBAL) do
//   server suy từ `AL Variable Library.category`. Client CHỈ đọc 2 field đó:
//     · ROW    ⇒ dòng BOM chọn DÒNG NGUỒN (`AL Bom Item.rule_input_row`);
//                công thức chèn `lookup_rule('MÃ', items.<dòng>.<cột>)`.
//     · GLOBAL ⇒ engine tự chèn biến; công thức `lookup_rule('MÃ')`.
//     · chưa khai / site chưa migrate ⇒ giữ nguyên đường cũ.
//   ⛔ KHÔNG hardcode danh sách field hợp lệ: mọi danh sách suy từ chính quy
//   tắc (biến + phạm vi) và dữ liệu đang có của các dòng.
//
// CHẶNG 4 — ĐIỀU KIỆN TRA NGAY TẠI CHỖ CHỌN QUY TẮC (Owner 2026-11-25):
//   "khi chọn nẹp theo độ dày kính thì phải chuyển danh sách các điều kiện
//   công thức tra ra kính lên gần chỗ rule". Tệp này dựng câu + khối HTML:
//     ruleConditionLines · ruleConditionSummary · ruleConditionPreviewHtml
//     (thuần — test Node) và fetchRuleConditionsDoc / fetchItemNames (Desk).
//   Hộp "Chọn công thức" chỉ nạp điều kiện của quy tắc ĐANG chọn (cache theo
//   mã trong phiên); kết quả về muộn của mã đã đổi thì bỏ.
//
// NGUYÊN TẮC
//   - Câu chữ dành cho người dùng cuối đi qua `__()`; câu cấu hình (màn hình
//     quản trị) mới được hiện mã kỹ thuật.
//   - Lỗi gọi API KHÔNG chặn nhập liệu, nhưng cũng ⛔ bị nuốt: hộp thoại thử
//     tra hiện nguyên văn câu server; hộp chèn công thức bỏ qua lượt thử lỗi.
// ═══════════════════════════════════════════════════════════════════════════

(function (root) {
    "use strict";

    // ── 0. Tiện ích chung ──────────────────────────────────────────────
    function translate(text) {
        try {
            return typeof __ === "function" ? __(text) : text;
        } catch (e) {
            return text;
        }
    }

    function trim(value) {
        if (value === null || value === undefined) return "";
        return String(value).trim();
    }

    function isBlank(value) {
        return value === null || value === undefined || String(value).trim() === "";
    }

    function escapeHtml(value) {
        return String(value === null || value === undefined ? "" : value)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }

    /** Escape dấu nháy đơn để nhét mã quy tắc vào chuỗi công thức. */
    function escapeSingleQuote(text) {
        return String(text).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
    }

    /** Số hữu hạn (number hoặc chuỗi số); còn lại null. */
    function toNumberOrNull(value) {
        if (value === null || value === undefined || value === "") return null;
        var n = Number(value);
        return isFinite(n) ? n : null;
    }

    /** In số KHÔNG phân nhóm nghìn — khớp ví dụ trong thiết kế ("3200"). */
    function formatNumberRaw(value) {
        if (value === null || value === undefined) return "";
        if (typeof value === "number") return isFinite(value) ? String(value) : "";
        return String(value);
    }

    /** In số trên hộp thoại — dùng format_number của Desk nếu có. */
    function formatNumberUi(value) {
        if (value === null || value === undefined || value === "") return "—";
        try {
            if (typeof format_number === "function" && typeof value !== "string") {
                return format_number(value);
            }
        } catch (e) { /* rơi về String */ }
        return String(value);
    }

    /**
     * Ô cột "Đến" của bảng điều kiện trong hộp "Thử tra".
     *
     * Dải MỞ (`Đến` trống, có `Từ`) ⇒ "trở lên" — khớp nhãn cột form
     * ("Đến (…) – bỏ trống = trở lên"). Trước đây hiện "—" ⇒ người dùng đọc
     * thành "dải không có cận trên" thay vì "từ mốc này trở lên".
     * HÀM THUẦN — test Node: alumglass/tests/js/test_rule_helper.js
     */
    function rangeToCellText(from, to) {
        var toBlank = to === null || to === undefined || String(to).trim() === "";
        var hasFrom = !(from === null || from === undefined || String(from).trim() === "");
        if (toBlank && hasFrom) return translate("trở lên");
        return formatNumberUi(to);
    }

    // ── 1. Nhãn hiển thị cho các field của dòng vật tư ──────────────────
    // Tên CHUẨN là `total_thick_mm` (xem variable_sources/field_provenance.py);
    // `glass_thick` chỉ là tên cũ vẫn được engine nhận.
    var ITEM_FIELD_LABELS = {
        total_thick_mm: "Độ dày kính",
        glass_thick: "Độ dày kính",
        glass_type: "Loại kính",
        width: "Rộng",
        height: "Cao",
    };
    var ITEM_FIELD_UNITS = {
        total_thick_mm: "mm",
        glass_thick: "mm",
        width: "mm",
        height: "mm",
    };
    var GLASS_VALUE_FIELDS = ["total_thick_mm", "glass_thick", "glass_type"];
    // Alias độ dày: dữ liệu cũ ghi `glass_thick`, danh sách mời dùng tên chuẩn
    // `total_thick_mm`. So khớp phải coi 2 tên là MỘT, nếu không công thức cũ
    // bị hiện thành ô "Nhập tay" kỹ thuật.
    var ITEM_FIELD_ALIASES = {
        glass_thick: "total_thick_mm",
        total_thick_mm: "glass_thick",
    };
    // Cột mà ENGINE thật sự đọc được cho `rule_input_expr`
    // (`bom_orchestrator._resolve_rule_input_for_item` chỉ đọc
    // `glass_data[slug]` — độ dày/loại kính; `row_literals` KHÔNG có
    // width/height/qty). Mời người dùng chọn "Rộng" ⇒ engine đọc ra 0 ÂM THẦM
    // ⇒ dòng không ra mã — đúng loại lỗi im lặng phải chặn từ giao diện.
    var RULE_INPUT_ALLOWED_FIELDS = ["total_thick_mm", "glass_thick", "glass_type"];
    var GROUP_ITEM = "Dòng trong BOM";
    var GROUP_VARIABLE = "Biến của chứng từ";

    // Cột kích thước mời cho MỖI dòng của bảng đang sửa (hộp "Chọn công thức").
    // Dòng kính của AL Bom Item có Rộng/Cao; dòng phụ kiện (AL Accessory Item)
    // KHÔNG có 2 cột đó ⇒ mời vào là chèn `items.ban_le.height` và Lưu báo
    // "Biến 'ban_le__height' chưa được khai báo".
    var DEFAULT_ITEM_FIELDS = ["width", "height"];
    // `qty` không bao giờ được mời: ô công thức số lượng tự tham chiếu chính nó.
    var FORBIDDEN_ITEM_FIELDS = ["qty"];

    // ── 2. Quy tắc: lọc + nhãn ─────────────────────────────────────────
    function normalizeRule(row) {
        if (!row || typeof row !== "object") return null;
        var out = {};
        Object.keys(row).forEach(function (key) { out[key] = row[key]; });
        out.rule_code = trim(out.rule_code) || trim(out.name);
        // Chặng 3: quy tắc tự khai "tra theo cái gì". Site chưa migrate ⇒
        // 2 field này không có ⇒ chuỗi rỗng (mọi nơi đọc ra "chưa khai").
        out.input_variable = trim(out.input_variable);
        out.input_scope = ruleInputScope(out);
        return out;
    }

    /** `is_active` khác 0 ⇒ đang bật. Thiếu field ⇒ coi như bật (site chưa migrate). */
    function isRuleActive(row) {
        if (!row) return false;
        var v = row.is_active;
        if (v === undefined || v === null) return true;
        if (v === 0 || v === false) return false;
        var s = String(v).trim().toLowerCase();
        return s !== "0" && s !== "false";
    }

    /** Chỉ quy tắc trả SỐ, đang bật — dùng cho autocomplete/chèn công thức. */
    function filterNumberRules(rows) {
        if (!Array.isArray(rows)) return [];
        return rows.filter(function (row) {
            return row && trim(row.result_type).toUpperCase() === "NUMBER"
                && isRuleActive(row);
        });
    }

    function findRule(rows, code) {
        var want = trim(code);
        if (!want || !Array.isArray(rows)) return null;
        for (var i = 0; i < rows.length; i++) {
            if (trim(rows[i] && (rows[i].rule_code || rows[i].name)) === want) {
                return rows[i];
            }
        }
        return null;
    }

    /** Chuẩn hoá để SO SÁNH nhãn với tên biến: bỏ hoa/thường + khoảng trắng. */
    function _inputLabelKey(text) {
        return String(text === null || text === undefined ? "" : text)
            .replace(/\s+/g, " ").trim().toLowerCase();
    }

    /**
     * Nhãn người đọc của "dữ liệu đem tra" — ⛔ MÃ BIẾN.
     *
     * Nhãn RỖNG, hoặc TRÙNG ĐÚNG tên biến (bỏ khác biệt hoa/thường và khoảng
     * trắng) ⇒ `fallback` (mặc định "dữ liệu quy tắc đọc"). Dữ liệu CŨ đã lưu
     * `input_label = total_thick_mm` rơi đúng vào ca "trùng tên biến" — trước
     * đây chỉ xử lý ca rỗng nên mã biến vẫn lọt ra câu.
     *
     * MỘT BẢN: form AL Rule (`AlumGlassRuleConditions.ruleInputDisplayLabel`)
     * uỷ quyền cho hàm này khi helper đã nạp.
     * HÀM THUẦN — test Node: alumglass/tests/js/test_rule_helper.js
     */
    function readableInputLabel(label, variable, fallback) {
        var text = trim(label);
        var variableText = trim(variable);
        var emptyLabel = (fallback === null || fallback === undefined)
            ? translate("dữ liệu quy tắc đọc") : String(fallback);
        if (!text) return emptyLabel;
        if (variableText && _inputLabelKey(text) === _inputLabelKey(variableText)) {
            return emptyLabel;
        }
        return text;
    }

    /** Nhãn "dữ liệu đem tra" của quy tắc (kèm đơn vị nếu có). */
    function ruleInputLabel(rule) {
        if (!rule) return translate("giá trị đem tra");
        var variable = trim(rule.input_variable);
        // UX1 chấm chặn: câu người dùng đọc ⛔ chứa MÃ BIẾN (`H_mm`) — nhãn
        // rỗng hoặc trùng tên biến ⇒ "dữ liệu quy tắc đọc".
        var label = readableInputLabel(rule.input_label, variable,
            variable ? translate("dữ liệu quy tắc đọc") : translate("giá trị đem tra"));
        var unit = trim(rule.input_unit);
        if (unit && label.indexOf("(") === -1) return label + " (" + unit + ")";
        return label;
    }

    /** Nhãn "kết quả trả về" của quy tắc. */
    function ruleOutputLabel(rule) {
        if (!rule) return translate("kết quả");
        var label = trim(rule.output_label);
        if (label) return label;
        return trim(rule.result_type).toUpperCase() === "ITEM"
            ? translate("mã vật tư")
            : translate("số");
    }

    /** Câu ngắn "tra theo X → Y" để hiện cạnh tên quy tắc. */
    function ruleSummary(rule) {
        if (!rule) return "";
        return translate("tra theo") + " " + ruleInputLabel(rule)
            + " → " + ruleOutputLabel(rule);
    }

    // ── 2a. Nhãn TIẾNG VIỆT cho enum của AL Rule ───────────────────────
    // Giá trị LƯU trong DB vẫn là tiếng Anh (`CONSTANT`/`THRESHOLD`/`LOOKUP`,
    // `NUMBER`/`ITEM`) — ở đây chỉ đổi NHÃN hiển thị. MỘT bản duy nhất dùng
    // cho form (options dạng `{label, value}`) và danh sách (formatter) để
    // hai bề mặt ⛔ lệch nhau.
    var RULE_TYPE_LABELS = {
        CONSTANT: "Hằng số",
        THRESHOLD: "Tra theo dải",
        LOOKUP: "Tra theo bảng",
    };
    var RESULT_TYPE_LABELS = {
        NUMBER: "Số",
        ITEM: "Mã vật tư",
    };

    function _enumOptions(map) {
        return Object.keys(map).map(function (value) {
            return { value: value, label: translate(map[value]) };
        });
    }

    /** `[{value, label}]` cho ô Select (giữ nguyên thứ tự khai trong JSON). */
    function ruleTypeOptions() { return _enumOptions(RULE_TYPE_LABELS); }
    function ruleResultTypeOptions() { return _enumOptions(RESULT_TYPE_LABELS); }

    /**
     * Nhãn người đọc của một giá trị enum. Giá trị LẠ (server mới thêm enum
     * chưa có nhãn) ⇒ trả nguyên giá trị, ⛔ để ô trống câm lặng.
     */
    function _enumLabel(map, value) {
        var key = trim(value).toUpperCase();
        if (!key) return "";
        return map[key] ? translate(map[key]) : trim(value);
    }

    function ruleTypeLabel(value) { return _enumLabel(RULE_TYPE_LABELS, value); }
    function ruleResultTypeLabel(value) { return _enumLabel(RESULT_TYPE_LABELS, value); }

    // ── 2b. Quy tắc tự khai "tra theo cái gì" (chặng 3 — thiết kế §7) ──
    // Quy tắc khai `input_variable` (Link `AL Variable Library`) + `input_scope`
    // (ROW/GLOBAL, server suy từ category của biến). Client ⛔ đoán lại phạm vi
    // bằng danh sách field cứng — mọi phân nhánh đọc từ 2 field này.
    // Site CHƯA migrate ⇒ 2 field rỗng ⇒ toàn bộ đường cũ (legacy) chạy nguyên.

    /** Tên biến quy tắc tra theo (rỗng = quy tắc chưa khai). */
    function ruleInputVariable(rule) {
        return trim(rule && rule.input_variable);
    }

    /** "ROW" | "GLOBAL" | "" (chưa khai / site chưa migrate). */
    function ruleInputScope(rule) {
        var raw = trim(rule && rule.input_scope).toUpperCase();
        if (raw === "ROW" || raw === "GLOBAL") return raw;
        return "";
    }

    /** Quy tắc đã khai đủ "tra theo" (biến + phạm vi) hay chưa. */
    function hasDeclaredRuleInput(rule) {
        return !!ruleInputVariable(rule) && !!ruleInputScope(rule);
    }

    /** Cờ boolean chịu được 3 kiểu server trả (bool / 0-1 / chữ); thiếu ⇒ mặc định. */
    function _flagIsTrue(value, defaultValue) {
        if (value === undefined || value === null) return defaultValue;
        if (typeof value === "boolean") return value;
        if (typeof value === "number") return value !== 0;
        var text = trim(value).toLowerCase();
        if (!text) return defaultValue;
        return text !== "0" && text !== "false";
    }

    /**
     * Tên các biến DÙNG ĐƯỢC ở bước chọn mã — đọc `resolvable` của API
     * `alumglass.api.get_rule_input_variables()` (mỗi phần tử
     * `{name, label, category, scope, resolvable}`).
     *
     * Thiếu cờ `resolvable` (server cũ) ⇒ coi như dùng được — ⛔ lọc oan.
     */
    function ruleInputResolvableNames(variables) {
        var out = [];
        var seen = {};
        (Array.isArray(variables) ? variables : []).forEach(function (entry) {
            if (!entry) return;
            var name = trim(entry.name);
            if (!name || seen[name]) return;
            if (!_flagIsTrue(entry.resolvable, true)) return;
            seen[name] = true;
            out.push(name);
        });
        return out;
    }

    /**
     * Biến đang chọn có dùng được ở bước chọn mã không.
     * Chưa chọn (rỗng), CHƯA có danh sách, hoặc danh sách RỖNG ⇒ `true`
     * (⛔ cảnh báo oan khi chưa đủ dữ liệu để kết luận).
     */
    function isRuleInputResolvable(variables, name) {
        var want = trim(name);
        if (!want) return true;
        if (!Array.isArray(variables)) return true;
        var names = ruleInputResolvableNames(variables);
        if (!names.length) return true;
        return names.indexOf(want) !== -1;
    }

    /**
     * Kế hoạch dựng bước "dữ liệu đem tra" cho hộp chèn công thức — THUẦN,
     * test được bằng Node:
     *   GLOBAL ⇒ không hỏi dữ liệu (quy tắc tự lấy), chèn `lookup_rule('MÃ')`.
     *   ROW    ⇒ hỏi DÒNG chứa biến, chèn `lookup_rule('MÃ', items.<dòng>.<cột>)`.
     *   ""     ⇒ đường cũ (mọi biểu thức hợp lệ của ô công thức).
     */
    function ruleInsertPlan(rule) {
        var variable = ruleInputVariable(rule);
        var scope = ruleInputScope(rule);
        var declared = !!variable && !!scope;
        return {
            declared: declared,
            scope: declared ? scope : "",
            variable: declared ? variable : "",
            label: ruleInputLabel(rule),
            needs_input: declared ? scope !== "GLOBAL" : true,
            single_arg: declared ? scope === "GLOBAL" : false,
        };
    }

    /**
     * "Quy tắc tự lấy <b>Độ dày kính (mm)</b>" — câu cho người dùng.
     * ⛔ mã biến (`H_mm`) trong câu: người dựng báo giá chỉ cần đọc NHÃN
     * (UX1 chấm chặn 2026-11-25).
     */
    function ruleGlobalSentenceHtml(rule) {
        return translate("Quy tắc tự lấy")
            + " <b>" + escapeHtml(ruleInputLabel(rule)) + "</b>";
    }

    /** "Quy tắc khai tra theo <b>Độ dày kính</b> · lấy từ dòng <b>Kính trên</b>". */
    function ruleRowSentenceHtml(rule, lineName) {
        var html = translate("Quy tắc khai tra theo")
            + " <b>" + escapeHtml(ruleInputLabel(rule)) + "</b>";
        var line = trim(lineName);
        if (line) {
            html += " · " + translate("lấy từ dòng")
                + " <b>" + escapeHtml(line) + "</b>";
        }
        return html;
    }

    /** "· hiện tại <b>24</b> → <b>C3211-20</b>" (kết quả rỗng ⇒ bỏ phần mũi tên). */
    function ruleCurrentValueHtml(value, result) {
        var html = " · " + translate("hiện tại")
            + " <b>" + escapeHtml(_previewValue(value)) + "</b>";
        var text = trim(result);
        if (text) html += " → <b>" + escapeHtml(text) + "</b>";
        return html;
    }

    // ── 2c. ĐIỀU KIỆN TRA CỦA QUY TẮC — xem ngay tại chỗ chọn quy tắc ──
    // Owner 2026-11-25: "khi chọn nẹp theo độ dày kính thì phải chuyển danh
    // sách các điều kiện công thức tra ra kính lên gần chỗ rule". Người dựng
    // báo giá chọn quy tắc trên dòng BOM (hoặc trong hộp "Chọn công thức")
    // phải thấy NGAY quy tắc tra theo cái gì, mấy điều kiện, phạm vi nào —
    // ⛔ phải mở form `AL Rule` mới đọc được.
    //
    // Ba hàm THUẦN (test Node: alumglass/tests/js/test_rule_helper.js):
    //   ruleConditionLines(ruleDoc, opts)          → mảng câu điều kiện
    //   ruleConditionSummary(ruleDoc, opts)        → {count, spanText, gapText, overlapText}
    //   ruleConditionPreviewHtml(ruleDoc, opts)    → chuỗi HTML (đã escape)
    //
    // NGUỒN SỰ THẬT cho khe hở/chồng lấn là `window.AlumGlassRuleConditions`
    // (al_rule.js — form quy tắc đã có findGaps/findOverlaps/summarizeThresholds).
    // Tệp đó là `doctype_js` của `AL Rule`, nên form BOM KHÔNG nạp nó ⇒ dưới
    // đây có bản dự phòng cùng thuật toán, CHỈ dùng khi thiếu module; test đối
    // chiếu hai bản phải ra cùng kết quả. Khi `AlumGlassRuleConditions` được
    // nạp toàn cục thì bản dự phòng không còn chạy (xem báo cáo để hợp nhất).

    var CONDITION_DASH = "–";
    var CONDITION_ARROW = " → ";
    var RULE_CONDITIONS_TTL = 5 * 60 * 1000;

    /** API điều kiện dùng chung nếu trang đã nạp `al_rule.js`; thiếu ⇒ null. */
    function _conditionsApi() {
        var scope = (typeof window !== "undefined") ? window
            : (typeof globalThis !== "undefined" ? globalThis : null);
        if (!scope) return null;
        var api = scope.AlumGlassRuleConditions;
        return (api && typeof api === "object") ? api : null;
    }

    /** Số về chuỗi người-đọc: "10" / "10,5"; rỗng/không phải số ⇒ "". */
    function _formatConditionNumber(value) {
        var api = _conditionsApi();
        if (api && typeof api.formatNumber === "function") {
            return api.formatNumber(value);
        }
        return _localFormatNumber(value);
    }

    /** Bản dự phòng của `formatNumber` (al_rule.js) — xem ghi chú đầu mục 2c. */
    function _localFormatNumber(value) {
        var num = _conditionNumber(value);
        if (num === null) return "";
        if (Math.abs(num - Math.round(num)) < 1e-9) return String(Math.round(num));
        var text = String(num);
        if (text.indexOf("e") !== -1 || text.indexOf("E") !== -1) {
            text = String(Number(num.toFixed(6)));
        }
        if (text.indexOf(".") !== -1) {
            text = text.replace(/0+$/, "").replace(/\.$/, "");
        }
        return text.replace(".", ",");
    }

    /** Ép số an toàn: rỗng/không phải số ⇒ null (KHÔNG phải 0). */
    function _conditionNumber(value) {
        if (value === null || value === undefined) return null;
        if (typeof value === "number") return isFinite(value) ? value : null;
        var text = trim(value);
        if (!text) return null;
        var num = Number(text.replace(/\s/g, "").replace(",", "."));
        return isFinite(num) ? num : null;
    }

    function _conditionUnit(rule, opts) {
        if (opts && opts.unit !== undefined && opts.unit !== null) {
            return trim(opts.unit);
        }
        return trim(rule && rule.input_unit);
    }

    function _conditionResultType(rule, opts) {
        if (opts && opts.result_type !== undefined && opts.result_type !== null) {
            return trim(opts.result_type).toUpperCase();
        }
        return trim(rule && rule.result_type).toUpperCase();
    }

    /**
     * Kết quả của 1 dòng điều kiện, người-đọc-được:
     *   NUMBER ⇒ số ("10", "10,5")
     *   ITEM    ⇒ "Nẹp nhôm 10 (N10)" khi biết tên, thiếu tên ⇒ mã ("N10")
     *
     * Tên vật tư lấy từ chính dòng (`result_item_name` — server/form có thể
     * gắn) hoặc `opts.item_names` (client tra nền). ⛔ tự đoán tên từ mã.
     */
    function _conditionResultText(row, resultType, opts) {
        if (resultType === "ITEM") {
            var code = trim(row && row.result_item);
            var name = trim(row && row.result_item_name);
            if (!name && code && opts && opts.item_names) {
                name = trim(opts.item_names[code]);
            }
            if (!code) return name;
            return name ? name + " (" + code + ")" : code;
        }
        return _formatConditionNumber(row && row.result_value);
    }

    /** Bảng ngưỡng của quy tắc: `{has_table, rows}` — thiếu bảng ≠ bảng rỗng. */
    function _conditionThresholdRows(ruleDoc) {
        var rows = ruleDoc && ruleDoc.threshold_rows;
        if (!Array.isArray(rows)) return { has_table: false, rows: [] };
        return { has_table: true, rows: rows };
    }

    function _conditionLookupRows(ruleDoc) {
        var rows = ruleDoc && ruleDoc.lookup_rows;
        if (!Array.isArray(rows)) return { has_table: false, rows: [] };
        return { has_table: true, rows: rows };
    }

    /** Dòng ngưỡng đọc được: phải có "Từ" (dòng thiếu là dòng đang khai dở). */
    function _readableThresholdRows(rows) {
        return (Array.isArray(rows) ? rows : []).filter(function (row) {
            return row && _conditionNumber(row.from_value) !== null;
        });
    }

    /** Dòng tra bảng đọc được: phải có giá trị cần tra. */
    function _readableLookupRows(rows) {
        return (Array.isArray(rows) ? rows : []).filter(function (row) {
            return row && !!trim(row.key_field);
        });
    }

    /** Câu khi không đọc được điều kiện — nói việc cần làm, ⛔ đoán số. */
    function ruleConditionsUnreadableText() {
        return translate("Chưa đọc được điều kiện của quy tắc này — mở quy tắc để xem.");
    }

    /**
     * Nhãn "dữ liệu đem tra" cho CÂU MỞ ĐẦU khối điều kiện — ⛔ kèm đơn vị
     * (đơn vị đã nằm trong từng dải: "0–10 mm"). Quy tắc chưa khai nhãn hoặc
     * nhãn TRÙNG tên biến ⇒ "dữ liệu quy tắc đọc", ⛔ lấy mã biến kỹ thuật.
     */
    function _conditionInputLabel(rule) {
        var variable = trim(rule && rule.input_variable);
        return readableInputLabel(rule && rule.input_label, variable,
            variable ? translate("dữ liệu quy tắc đọc") : translate("giá trị đem tra"));
    }

    /** "0–10 mm" / "≥ 20 mm" / "20 mm trở lên"; đơn vị rỗng ⇒ ⛔ khoảng trắng thừa. */
    function _conditionReachText(from, to, unit) {
        var suffix = unit ? " " + unit : "";
        if (to === null || to === undefined) {
            return "≥ " + _formatConditionNumber(from) + suffix;
        }
        return _formatConditionNumber(from) + CONDITION_DASH
            + _formatConditionNumber(to) + suffix;
    }

    /**
     * Câu cho dòng điều kiện CHƯA khai kết quả — gọi tên kết quả theo
     * `output_label` của quy tắc ("chưa có số keo"), thiếu nhãn ⇒ "chưa có
     * kết quả". ⛔ đoán số.
     */
    function _conditionMissingResult(rule) {
        var label = trim(rule && rule.output_label);
        return label
            ? translate("chưa có") + " " + label.toLowerCase()
            : translate("chưa có kết quả");
    }

    /**
     * Mỗi điều kiện thành MỘT câu người-đọc-được (dùng đúng metadata quy tắc):
     *   THRESHOLD: "0–10 mm → Nẹp 10", "≥ 20 mm → Nẹp 30" (to_value trống)
     *   LOOKUP:    "Kính cường lực → Keo A"
     *   CONSTANT:  "Mọi trường hợp → 5"
     *
     * Quy tắc có bảng nhưng chưa dòng nào đọc được ⇒ `[]` (caller nói "chưa có
     * điều kiện"). Thiếu hẳn bảng / loại quy tắc lạ ⇒ đúng MỘT câu
     * "Chưa đọc được điều kiện…", ⛔ đoán số.
     */
    function ruleConditionLines(ruleDoc, opts) {
        opts = opts || {};
        if (!ruleDoc) return [];
        var type = trim(ruleDoc.rule_type).toUpperCase();
        var unit = _conditionUnit(ruleDoc, opts);
        var resultType = _conditionResultType(ruleDoc, opts);
        var missingResult = _conditionMissingResult(ruleDoc);

        if (type === "CONSTANT") {
            var constant = _conditionResultText(
                { result_value: ruleDoc.constant_value }, resultType, opts);
            return [translate("Mọi trường hợp") + CONDITION_ARROW
                + (constant || missingResult)];
        }
        if (type === "THRESHOLD") {
            var threshold = _conditionThresholdRows(ruleDoc);
            if (!threshold.has_table) return [ruleConditionsUnreadableText()];
            return _readableThresholdRows(threshold.rows).map(function (row) {
                var from = _conditionNumber(row.from_value);
                var to = _conditionNumber(row.to_value);
                var result = _conditionResultText(row, resultType, opts);
                return _conditionReachText(from, to, unit) + CONDITION_ARROW
                    + (result || missingResult);
            });
        }
        if (type === "LOOKUP") {
            var lookup = _conditionLookupRows(ruleDoc);
            if (!lookup.has_table) return [ruleConditionsUnreadableText()];
            return _readableLookupRows(lookup.rows).map(function (row) {
                var result = _conditionResultText(row, resultType, opts);
                return trim(row.key_field) + CONDITION_ARROW
                    + (result || missingResult);
            });
        }
        return [ruleConditionsUnreadableText()];
    }

    /** Mã vật tư đang xuất hiện ở kết quả — để tra TÊN hiển thị ("Nẹp (N10)"). */
    function ruleConditionItemCodes(ruleDoc) {
        var out = [];
        var seen = {};
        if (!ruleDoc || _conditionResultType(ruleDoc, null) !== "ITEM") return out;
        var type = trim(ruleDoc.rule_type).toUpperCase();
        var rows = type === "THRESHOLD"
            ? _readableThresholdRows(_conditionThresholdRows(ruleDoc).rows)
            : (type === "LOOKUP"
                ? _readableLookupRows(_conditionLookupRows(ruleDoc).rows) : []);
        rows.forEach(function (row) {
            var code = trim(row && row.result_item);
            if (!code || seen[code]) return;
            seen[code] = true;
            out.push(code);
        });
        return out;
    }

    // ── Dự phòng thuật toán khe hở/chồng lấn (chỉ dùng khi thiếu module) ──
    function _localThresholdRanges(rows) {
        var ranges = [];
        (Array.isArray(rows) ? rows : []).forEach(function (row) {
            if (!row) return;
            var from = _conditionNumber(row.from_value);
            if (from === null) return;
            ranges.push({ from: from, to: _conditionNumber(row.to_value) });
        });
        ranges.sort(function (a, b) { return a.from - b.from; });
        return ranges;
    }

    function _localFindGaps(ranges) {
        if (!ranges.length) return [];
        var gaps = [];
        if (ranges[0].from > 0) gaps.push({ from: 0, to: ranges[0].from });
        var reach = ranges[0].to;
        for (var i = 1; i < ranges.length; i++) {
            var range = ranges[i];
            if (reach !== null && range.from > reach) {
                gaps.push({ from: reach, to: range.from });
            }
            if (reach === null) continue;
            if (range.to === null || range.to > reach) reach = range.to;
        }
        return gaps;
    }

    function _localFindOverlaps(ranges) {
        var overlaps = [];
        var furthest = null;
        ranges.forEach(function (range) {
            if (furthest && (furthest.to === null || furthest.to > range.from)) {
                overlaps.push({
                    first: { from: furthest.from, to: furthest.to },
                    second: { from: range.from, to: range.to },
                });
            }
            if (!furthest) {
                furthest = range;
                return;
            }
            if (furthest.to === null) return;
            if (range.to === null || range.to > furthest.to) furthest = range;
        });
        return overlaps;
    }

    /** Phạm vi đang phủ ("0–30 mm", "20 mm trở lên") — bản dự phòng. */
    function _localRangeText(ranges, unit) {
        if (!ranges.length) return "";
        var from = null;
        var to = null;
        var openEnded = false;
        ranges.forEach(function (range) {
            if (from === null || range.from < from) from = range.from;
            if (range.to === null) openEnded = true;
            else if (to === null || range.to > to) to = range.to;
        });
        var suffix = unit ? " " + unit : "";
        if (openEnded) return _formatConditionNumber(from) + suffix + " "
            + translate("trở lên");
        if (to !== null) {
            return _formatConditionNumber(from) + CONDITION_DASH
                + _formatConditionNumber(to) + suffix;
        }
        return _formatConditionNumber(from) + suffix;
    }

    /** "0–10 mm" cho 1 khe hở; mở tới trên cùng ⇒ "40 mm trở lên". */
    function _conditionGapLabel(gap, unit) {
        var suffix = unit ? " " + unit : "";
        if (gap && gap.to === null) {
            return _formatConditionNumber(gap.from) + suffix + " "
                + translate("trở lên");
        }
        return _formatConditionNumber(gap.from) + CONDITION_DASH
            + _formatConditionNumber(gap.to) + suffix;
    }

    /**
     * Dải ngưỡng đã chuẩn hoá — CHỈ trả khi KHÔNG có module dùng chung
     * (`null` = caller gọi `AlumGlassRuleConditions.findGaps/findOverlaps`).
     */
    function _fallbackRangesIfNeeded(ruleDoc) {
        var api = _conditionsApi();
        if (api && typeof api.findGaps === "function"
                && typeof api.findOverlaps === "function") {
            return null;
        }
        return _localThresholdRanges(_conditionThresholdRows(ruleDoc).rows);
    }

    /**
     * Thống kê điều kiện: số điều kiện đọc được, phạm vi đang phủ, câu cảnh
     * báo khe hở / chồng lấn (rỗng = không có). Chỉ THRESHOLD mới có phạm vi
     * số + khe hở; LOOKUP chỉ có số điều kiện.
     */
    function ruleConditionSummary(ruleDoc, opts) {
        opts = opts || {};
        var summary = { count: 0, spanText: "", gapText: "", overlapText: "" };
        if (!ruleDoc) return summary;
        var type = trim(ruleDoc.rule_type).toUpperCase();
        var unit = _conditionUnit(ruleDoc, opts);
        var raw = [];

        if (type === "THRESHOLD") {
            var table = _conditionThresholdRows(ruleDoc);
            if (!table.has_table) return summary;
            raw = table.rows;
            summary.count = _readableThresholdRows(raw).length;
            var api = _conditionsApi();
            if (summary.count) {
                if (api && typeof api.summarizeThresholds === "function") {
                    var stats = api.summarizeThresholds(raw, unit) || {};
                    summary.spanText = trim(stats.rangeText);
                } else {
                    summary.spanText = _localRangeText(
                        _localThresholdRanges(raw), unit);
                }
            }
        } else if (type === "LOOKUP") {
            var lookup = _conditionLookupRows(ruleDoc);
            if (!lookup.has_table) return summary;
            summary.count = _readableLookupRows(lookup.rows).length;
            return summary;  // khoá chữ ⇒ không có phạm vi số
        } else {
            return summary;
        }

        if (!summary.count) return summary;

        var ranges = _fallbackRangesIfNeeded(ruleDoc);
        var gaps;
        var overlaps;
        if (ranges === null) {
            gaps = api.findGaps(raw) || [];
            overlaps = api.findOverlaps(raw) || [];
        } else {
            gaps = _localFindGaps(ranges);
            overlaps = _localFindOverlaps(ranges);
        }

        if (gaps.length) {
            summary.gapText = fillPlaceholders(
                "Còn trống {0} — giá trị trong khoảng này không tra ra kết quả.",
                [gaps.map(function (gap) {
                    return _conditionGapLabel(gap, unit);
                }).join(", ")]);
        }
        if (overlaps.length) {
            summary.overlapText = fillPlaceholders(
                // Engine xếp dải theo mốc `Từ` TĂNG DẦN rồi lấy dòng khớp ĐẦU
                // TIÊN ⇒ dải có mốc bắt đầu THẤP HƠN thắng, ⛔ phải nói ngược
                // lại ("dải khai trước" — thứ tự khai trong bảng không quyết định).
                "Dải chồng lấn {0} — dải có mốc bắt đầu thấp hơn được chọn.",
                [overlaps.map(function (pair) {
                    return _conditionGapLabel(pair.first, unit) + " "
                        + translate("và") + " "
                        + _conditionGapLabel(pair.second, unit);
                }).join("; ")]);
        }
        return summary;
    }

    /**
     * Khối HTML "điều kiện tra" để nhúng ngay dưới chỗ chọn quy tắc.
     *
     * `opts`:
     *   max        — số điều kiện hiện trước (mặc định 3), phần còn lại "+ … và N nữa"
     *   item_names — map mã vật tư → tên ("N10" → "Nẹp nhôm 10")
     *   heading    — "full" (mặc định): "Quy tắc tra theo <b>Độ dày kính</b>:"
     *                "compact": "Tra theo: <b>Độ dày kính</b> · 4 điều kiện:"
     *   show_link  — `false` ⇒ không render "Xem tất cả"
     *
     * Mã quy tắc CHỈ nằm trong URL; câu chữ ⛔ mã/slug/tên field kỹ thuật.
     */
    function ruleConditionPreviewHtml(ruleDoc, opts) {
        opts = opts || {};
        if (!ruleDoc) return "";
        var max = _conditionNumber(opts.max);
        max = (max === null || max < 1) ? 3 : Math.floor(max);
        var lines = ruleConditionLines(ruleDoc, opts);
        var summary = ruleConditionSummary(ruleDoc, opts);
        var code = trim(ruleDoc.name) || trim(ruleDoc.rule_code);
        var label = _conditionInputLabel(ruleDoc);
        var unreadable = lines.length === 1
            && lines[0] === ruleConditionsUnreadableText();
        var compact = trim(opts.heading).toLowerCase() === "compact";

        var html = '<div class="al-rule-conditions" style="margin-top:6px;'
            + 'font-size:12px;color:#0f172a;line-height:1.5;">';

        if (compact) {
            var head = translate("Tra theo:") + " <b>" + escapeHtml(label) + "</b>";
            if (summary.count) {
                head += " · " + escapeHtml(fillPlaceholders("{0} điều kiện",
                    [summary.count]));
            }
            html += '<div class="al-rule-conditions-head">' + head + ":</div>";
        } else {
            html += '<div class="al-rule-conditions-head">'
                + fillPlaceholders("Quy tắc tra theo {0}:",
                    ["<b>" + escapeHtml(label) + "</b>"])
                + "</div>";
        }

        if (unreadable) {
            html += '<div class="al-rule-conditions-empty" style="color:#b45309;">'
                + escapeHtml(lines[0]) + "</div>";
        } else if (!lines.length) {
            html += '<div class="al-rule-conditions-empty" style="color:#64748b;">'
                + escapeHtml(translate("Quy tắc chưa có điều kiện nào.")) + "</div>";
        } else {
            var shown = lines.slice(0, max);
            html += '<ul class="al-rule-conditions-list" '
                + 'style="margin:2px 0 0 16px;padding:0;">';
            shown.forEach(function (line) {
                html += "<li>" + escapeHtml(line) + "</li>";
            });
            html += "</ul>";
            var meta = [];
            if (lines.length > shown.length) {
                meta.push(fillPlaceholders("… và {0} nữa",
                    [lines.length - shown.length]));
            }
            // Dòng "full" đã có số điều kiện ngay câu đầu; "compact" thì có
            // ngay tiêu đề ⇒ chỉ giữ phạm vi ở đây.
            if (!compact && summary.count) {
                meta.push(fillPlaceholders("{0} điều kiện", [summary.count]));
            }
            if (summary.spanText) meta.push(summary.spanText);
            if (meta.length) {
                html += '<div class="al-rule-conditions-meta" '
                    + 'style="font-size:11px;color:#64748b;">'
                    + escapeHtml(meta.join(" · ")) + "</div>";
            }
        }

        if (summary.gapText) {
            html += '<div class="al-rule-conditions-warn" '
                + 'style="font-size:11px;color:#b45309;">⚠ '
                + escapeHtml(summary.gapText) + "</div>";
        }
        if (summary.overlapText) {
            html += '<div class="al-rule-conditions-warn" '
                + 'style="font-size:11px;color:#b45309;">⚠ '
                + escapeHtml(summary.overlapText) + "</div>";
        }

        var route = (opts.show_link === false) ? "" : ruleFormRoute(code);
        if (route) {
            html += '<div style="margin-top:2px;">'
                + '<a class="al-rule-conditions-link" href="' + escapeHtml(route)
                + '" target="_blank" rel="noopener">'
                + escapeHtml(translate("Xem tất cả")) + "</a></div>";
        }
        return html + "</div>";
    }

    // ── 2d. Tên vật tư cho câu điều kiện (cache trong phiên) ────────────
    var _itemNameCache = {};

    /** Tên đã biết của các mã (chỉ trả mã đã tra) — vẽ ngay, ⛔ chờ API. */
    function cachedItemNames(codes) {
        var out = {};
        (Array.isArray(codes) ? codes : []).forEach(function (code) {
            var key = trim(code);
            if (key && _itemNameCache[key] !== undefined) {
                out[key] = _itemNameCache[key];
            }
        });
        return out;
    }

    /**
     * Tra tên vật tư cho các mã (1 lượt `get_list`); lỗi/không quyền ⇒ coi
     * như không có tên (câu hiện mã) — ⛔ chặn giao diện, ⛔ gọi lặp.
     */
    function fetchItemNames(codes) {
        var list = [];
        var seen = {};
        (Array.isArray(codes) ? codes : []).forEach(function (code) {
            var key = trim(code);
            if (!key || seen[key]) return;
            seen[key] = true;
            list.push(key);
        });
        var missing = list.filter(function (code) {
            return _itemNameCache[code] === undefined;
        });
        if (!missing.length) return Promise.resolve(cachedItemNames(list));
        return new Promise(function (resolve) {
            if (!_hasFrappe() || !frappe.db || typeof frappe.db.get_list !== "function") {
                return resolve(cachedItemNames(list));
            }
            // Chưa biết tên ⇒ để mã hiện một mình (⛔ "N10 (N10)").
            missing.forEach(function (code) { _itemNameCache[code] = ""; });
            frappe.db.get_list("Item", {
                filters: { name: ["in", missing] },
                fields: ["name", "item_name"],
                // Không đặt `limit`: danh sách mã do quy tắc quyết định, và
                // `db.get_list` mặc định trả hết (⛔ cắt ở 20 như API phân trang).
            }).then(function (rows) {
                (rows || []).forEach(function (row) {
                    var code = trim(row && row.name);
                    if (!code) return;
                    _itemNameCache[code] = trim(row.item_name);
                });
                resolve(cachedItemNames(list));
            }).catch(function () {
                resolve(cachedItemNames(list));
            });
        });
    }

    // ── 2e. Đọc doc quy tắc cho khối điều kiện (cache 5 phút) ───────────
    var _conditionsDocCache = {};

    /**
     * Doc `AL Rule` đầy đủ (có bảng điều kiện) — cache theo mã trong phiên để
     * ⛔ gọi lặp khi người dùng đổi qua lại / giao diện vẽ lại. Lỗi hoặc
     * không có quyền ⇒ `null` (caller ẩn khối, ⛔ làm vỡ form).
     *
     * Một lượt đọc, KHÔNG bao giờ đọc cả danh sách quy tắc: hộp chọn quy tắc
     * chỉ nạp điều kiện của quy tắc đang được chọn.
     */
    function fetchRuleConditionsDoc(code) {
        var want = trim(code);
        if (!want) return Promise.resolve(null);
        var cached = _conditionsDocCache[want];
        if (cached && (Date.now() - cached.ts) < cached.ttl) {
            return Promise.resolve(cached.data);
        }
        return fetchRuleMeta(want).then(function (doc) {
            // Lỗi tạm thời ⇒ cache ngắn, lần sau thử lại (⛔ giữ "không đọc
            // được" suốt phiên).
            _conditionsDocCache[want] = {
                data: doc,
                ts: Date.now(),
                ttl: doc ? RULE_CONDITIONS_TTL : 30 * 1000,
            };
            return doc;
        });
    }

    // ── 3. Dựng chuỗi công thức ────────────────────────────────────────
    /**
     * `lookup_rule('CODE', input)` — có `multiplier` thì thêm ` * multiplier`.
     * `input` rỗng ⇒ null (caller tự hiện hướng dẫn), TRỪ khi `single_arg`:
     * quy tắc khai biến toàn cục thì engine tự chèn biến ⇒ `lookup_rule('CODE')`
     * là dạng hợp lệ (thiết kế §7.2 điểm 4).
     */
    function buildSnippet(opts) {
        opts = opts || {};
        var code = trim(opts.code);
        var input = trim(opts.input);
        if (!code) return null;
        if (!input && !opts.single_arg) return null;
        var core = input
            ? "lookup_rule('" + escapeSingleQuote(code) + "', " + input + ")"
            : "lookup_rule('" + escapeSingleQuote(code) + "')";
        var multiplier = trim(opts.multiplier);
        return multiplier ? core + " * " + multiplier : core;
    }

    /**
     * Công thức dựng sẵn cho người KHÔNG biết code:
     *   fixed   — số lượng cố định (nhập số)
     *   panels  — theo số cánh: `n_panel`
     *   panels2 — 2 × số cánh: `2 * n_panel`
     * Nhánh "rule" dùng `buildSnippet` (không xử lý ở đây).
     */
    function buildPresetSnippet(opts) {
        opts = opts || {};
        var kind = trim(opts.preset);
        if (kind === "panels") return "n_panel";
        if (kind === "panels2") return "2 * n_panel";
        if (kind === "fixed") {
            var raw = trim(opts.value);
            if (!raw) return null;
            // Chấp nhận "4", "2,5" (người Việt gõ dấu phẩy); từ chối chữ.
            if (!/^-?\d+(?:[.,]\d+)?$/.test(raw)) return null;
            var n = Number(raw.replace(",", "."));
            return isFinite(n) ? String(n) : null;
        }
        return null;
    }

    /**
     * Đọc 1 chuỗi `lookup_rule('MÃ'[, input]) [* multiplier]` → {code, input,
     * multiplier}; không đúng dạng ⇒ null. Tự bỏ phần thoát nháy của mã.
     * Dạng MỘT tham số (`lookup_rule('MÃ')`) hợp lệ với quy tắc khai biến
     * toàn cục — trả `input: ""`.
     */
    function parseLookupSnippet(text) {
        var src = trim(text);
        var prefix = "lookup_rule(";
        if (src.indexOf(prefix) !== 0) return null;

        var i = prefix.length;
        while (i < src.length && /\s/.test(src[i])) i++;
        var quote = src[i];
        if (quote !== "'" && quote !== "\"") return null;
        i++;

        var code = "";
        var closed = false;
        while (i < src.length) {
            var ch = src[i];
            if (ch === "\\" && i + 1 < src.length) {
                var next = src[i + 1];
                if (next === quote || next === "\\") { code += next; i += 2; continue; }
                code += ch;
                i += 1;
                continue;
            }
            if (ch === quote) { closed = true; i += 1; break; }
            code += ch;
            i += 1;
        }
        if (!closed) return null;

        while (i < src.length && /\s/.test(src[i])) i++;

        // Dạng 1 tham số: `lookup_rule('MÃ')` — quy tắc tự lấy dữ liệu tra.
        if (src[i] === ")") {
            var tail = trim(src.slice(i + 1));
            var singleMultiplier = "";
            if (tail) {
                if (tail.charAt(0) !== "*") return null;
                singleMultiplier = trim(tail.slice(1));
                if (!singleMultiplier) return null;
            }
            return { code: code, input: "", multiplier: singleMultiplier };
        }

        if (src[i] !== ",") return null;
        i += 1;

        // Tìm dấu `)` đóng lời gọi — bỏ qua ngoặc lồng nhau và chuỗi bên trong.
        var depth = 0;
        var inputStart = i;
        var inputEnd = -1;
        var innerQuote = "";
        while (i < src.length) {
            var c = src[i];
            if (innerQuote) {
                if (c === "\\") { i += 2; continue; }
                if (c === innerQuote) innerQuote = "";
                i += 1;
                continue;
            }
            if (c === "'" || c === "\"") { innerQuote = c; i += 1; continue; }
            if (c === "(") { depth += 1; i += 1; continue; }
            if (c === ")") {
                if (depth === 0) { inputEnd = i; i += 1; break; }
                depth -= 1;
                i += 1;
                continue;
            }
            i += 1;
        }
        if (inputEnd === -1) return null;

        var input = trim(src.slice(inputStart, inputEnd));
        if (!input) return null;

        var rest = trim(src.slice(i));
        var multiplier = "";
        if (rest) {
            if (rest.charAt(0) !== "*") return null;
            multiplier = trim(rest.slice(1));
            if (!multiplier) return null;
        }
        return { code: code, input: input, multiplier: multiplier };
    }

    /**
     * Phân tích giá trị ĐANG CÓ của ô công thức thành trạng thái của hộp
     * "Chọn công thức" (4 preset + nhánh quy tắc). Mở hộp thoại mà không phản
     * chiếu giá trị cũ ⇒ bấm Chèn là ghi đè im lặng.
     *
     * Trả {preset, fixed, rule, input, multiplier, single_arg, raw}. `preset`
     * rỗng nghĩa là công thức chưa thuộc dạng dựng sẵn nào (vẫn hiện "Ô đang
     * có: …"). `single_arg` = lời gọi 1 tham số (`lookup_rule('MÃ')`) — chỉ hợp
     * lệ khi quy tắc khai biến toàn cục.
     */
    function parseFormulaSnippet(value) {
        var raw = trim(value);
        var out = {
            preset: "", fixed: "", rule: "", input: "", multiplier: "",
            single_arg: false, raw: raw,
        };
        if (!raw) return out;
        if (raw === "n_panel") {
            out.preset = "panels";
            return out;
        }
        if (/^2\s*\*\s*n_panel$/.test(raw)) {
            out.preset = "panels2";
            return out;
        }
        if (/^-?\d+(?:[.,]\d+)?$/.test(raw)) {
            out.preset = "fixed";
            out.fixed = raw;
            return out;
        }
        var lookup = parseLookupSnippet(raw);
        if (lookup) {
            out.preset = "rule";
            out.rule = lookup.code;
            out.input = lookup.input;
            out.multiplier = lookup.multiplier;
            out.single_arg = !lookup.input;
        }
        return out;
    }

    /**
     * Route THUẦN mở form `AL Rule` — dùng làm URL cho `window.open`.
     *
     * ⛔ KHÔNG dùng `frappe.utils.get_form_link("AL Rule", code, true)`:
     * tham số thứ 3 `html=true` trả chuỗi `<a href="/app/al-rule/…">…</a>`;
     * đưa chuỗi đó vào `window.open` sẽ thành URL méo
     * `/desk/custom-workspaces/…/%3Ca%20href=…`.
     */
    function ruleFormRoute(ruleCode) {
        var code = trim(ruleCode);
        if (!code) return "";
        return "/app/al-rule/" + encodeURIComponent(code);
    }

    // ── 3b. Câu giải thích THƯỜNG TRỰC cho ô công thức (AL Accessory Item) ──
    // Hộp thoại đóng rồi thì người dùng không còn câu nào giải thích ô
    // `qty_formula` đang chứa gì. Câu dưới đây dựng từ CHÍNH chuỗi công thức
    // (`parseFormulaSnippet`), dùng nhãn người đọc — ⛔ mã biến/mã quy tắc
    // trong câu (UX1 #3).
    var VARIABLE_DISPLAY = {
        H_mm: "chiều cao",
        W_mm: "chiều rộng",
        n_panel: "số cánh",
        total_thick_mm: "độ dày kính",
        glass_thick: "độ dày kính",
        glass_type: "loại kính",
        width: "chiều rộng",
        height: "chiều cao",
    };

    /** "{0}" thay bằng tham số — `__()` của Frappe chỉ nhận 1 chuỗi ở đây. */
    function fillPlaceholders(text, values) {
        var out = translate(text);
        (Array.isArray(values) ? values : []).forEach(function (value, index) {
            out = out.split("{" + index + "}").join(String(value));
        });
        return out;
    }

    /** Mô tả 1 biểu thức nguồn dữ liệu bằng lời; không nhận ra ⇒ "". */
    function _describeSource(expr) {
        var text = trim(expr);
        if (!text) return "";
        var ref = parseItemExpr(text);
        if (ref) {
            var fieldLabel = ITEM_FIELD_LABELS[ref.field];
            return fieldLabel ? translate(fieldLabel).toLowerCase() : "";
        }
        if (/^[A-Za-z_]\w*$/.test(text) && VARIABLE_DISPLAY[text]) {
            return translate(VARIABLE_DISPLAY[text]);
        }
        // Số thật trong biểu thức nhân ⇒ được đọc thành số (không phải mã).
        if (/^-?\d+(?:[.,]\d+)?$/.test(text)) return text.replace(",", ".");
        return "";
    }

    /**
     * Câu giải thích công thức của ô số lượng — THUẦN, test bằng Node:
     *   {text, rule_code, linkable}
     * `text` luôn là câu người-đọc-được; `rule_code` chỉ để dựng nút
     * "Xem quy tắc" (⛔ đưa mã vào câu). Công thức lạ ⇒ câu trung tính
     * "Công thức tự nhập", ⛔ đoán số.
     */
    function describeFormula(value) {
        var parsed = parseFormulaSnippet(value);
        var result = { text: translate("Công thức tự nhập"), rule_code: "", linkable: false };
        if (!parsed.raw) {
            result.text = translate("Chưa đặt công thức số lượng.");
            return result;
        }
        if (parsed.preset === "fixed") {
            result.text = fillPlaceholders("Số lượng cố định: {0}", [parsed.fixed]);
            return result;
        }
        if (parsed.preset === "panels") {
            result.text = translate("Số lượng = số cánh của bộ");
            return result;
        }
        if (parsed.preset === "panels2") {
            result.text = translate("Số lượng = 2 × số cánh");
            return result;
        }
        if (parsed.preset !== "rule") return result;

        var text = translate("Số lượng = kết quả tra quy tắc");
        var source = _describeSource(parsed.input);
        if (source) text += " " + fillPlaceholders("theo {0}", [source]);
        var multiplier = _describeSource(parsed.multiplier);
        if (multiplier) text += " × " + multiplier;
        result.text = text;
        result.rule_code = trim(parsed.rule);
        result.linkable = !!result.rule_code;
        return result;
    }

    // ── 3c. Trạng thái THIẾU GIÁ TRỊ / THIẾU QUY TẮC — câu + việc cần làm ──
    /**
     * Câu cảnh báo khi lượt tính CHƯA có giá trị cho biến quy tắc đọc (vd
     * chưa nhập chiều cao). ⛔ im lặng ra 0.
     */
    function variableMissingNoticeText(label) {
        var name = trim(label) || translate("dữ liệu quy tắc đọc");
        return fillPlaceholders(
            "Chưa có {0} cho lượt tính này — kiểm tra tham số báo giá (chiều cao, số cánh…) rồi tính lại.",
            [name]);
    }

    /** HTML khối cảnh báo hổ phách của câu trên. */
    function variableMissingNoticeHtml(label) {
        return '<div data-role="variable-missing" style="font-size:12px;color:#b45309;'
            + 'background:#fffbeb;border:1px solid #fde68a;border-radius:4px;'
            + 'padding:6px 8px;line-height:1.45;">⚠ '
            + escapeHtml(variableMissingNoticeText(label)) + "</div>";
    }

    /**
     * Trạng thái quy tắc đang chọn khi mở lại hộp thoại (UX1 #12):
     *   active   — bình thường (rỗng)
     *   inactive — quy tắc đã bị TẮT
     *   missing  — quy tắc đã bị XOÁ
     *   unknown  — chưa kiểm tra được (⛔ bịa lý do)
     * `opts.not_listed` = quy tắc đang bật nhưng không nằm trong danh sách
     * (vd không trả số) ⇒ vẫn phải nói vì sao không chọn được.
     */
    function ruleStateNoticeText(state, opts) {
        opts = opts || {};
        var kind = trim(state).toLowerCase();
        if (kind === "inactive") {
            return translate("Quy tắc đang chọn đã bị tắt — chọn quy tắc khác để tính đúng.");
        }
        if (kind === "missing") {
            return translate("Quy tắc đang chọn không còn tồn tại — chọn quy tắc khác.");
        }
        if (kind === "unknown") {
            return translate("Chưa kiểm tra được quy tắc đang chọn — mở «Xem quy tắc» kiểm tra, hoặc chọn quy tắc khác.");
        }
        if (kind === "active" && opts.not_listed) {
            return translate("Quy tắc đang chọn không trả về số lượng — chọn quy tắc khác.");
        }
        return "";
    }

    /** Đọc trạng thái 1 quy tắc: active | inactive | missing | unknown. */
    function fetchRuleState(code) {
        var want = trim(code);
        if (!want) return Promise.resolve({ state: "missing", rule_name: "" });
        if (!_hasFrappe() || !frappe.db) {
            return Promise.resolve({ state: "unknown", rule_name: "" });
        }
        function fromMeta(meta) {
            if (!meta) return { state: "unknown", rule_name: "" };
            return {
                state: isRuleActive(meta) ? "active" : "inactive",
                rule_name: trim(meta.rule_name),
            };
        }
        var existsRequest = null;
        try {
            if (typeof frappe.db.exists === "function") {
                existsRequest = Promise.resolve(frappe.db.exists("AL Rule", want));
            }
        } catch (e) { existsRequest = null; }
        if (existsRequest) {
            return existsRequest.then(function (exists) {
                if (exists === null || exists === undefined) {
                    return { state: "unknown", rule_name: "" };
                }
                if (!exists) return { state: "missing", rule_name: "" };
                return fetchRuleMeta(want).then(fromMeta);
            }).catch(function () {
                return { state: "unknown", rule_name: "" };
            });
        }
        // Không có `db.exists` ⇒ chỉ đọc được meta; null không phân biệt được
        // "đã xoá" với "lỗi đọc" ⇒ nói chưa kiểm tra được, ⛔ đoán.
        return fetchRuleMeta(want).then(fromMeta).catch(function () {
            return { state: "unknown", rule_name: "" };
        });
    }

    /** 4 lựa chọn hiện trong hộp thoại "Chọn công thức" (thứ tự cố định). */
    function presetDefinitions() {
        return [
            {
                kind: "fixed", icon: "🧩",
                label: translate("Số lượng cố định"),
                desc: translate("Mỗi dòng dùng đúng một số lượng, không phụ thuộc kích thước."),
                example: translate("Ví dụ: nhập 4 → mỗi dòng luôn là 4."),
            },
            {
                kind: "panels", icon: "🧩",
                label: translate("Theo số cánh"),
                desc: translate("Mỗi cánh dùng 1 cái; số lượng đi theo số cánh của bộ."),
                example: translate("Ví dụ: bộ 2 cánh → số lượng 2."),
            },
            {
                kind: "panels2", icon: "🧩",
                label: translate("2 × số cánh"),
                desc: translate("Mỗi cánh dùng 2 cái (ví dụ bản lề trên và dưới)."),
                example: translate("Ví dụ: bộ 2 cánh → số lượng 4."),
            },
            {
                kind: "rule", icon: "🧩",
                label: translate("Tra quy tắc theo giá trị"),
                desc: translate("Tra bảng quy tắc theo một giá trị (độ dày kính, chiều cao…) để ra số lượng."),
                example: translate("Ví dụ: độ dày kính 10 mm → số bản lề mỗi cánh."),
            },
        ];
    }

    // ── 4. Dòng vật tư trong bộ / biến của chứng từ → option chọn ──────
    /** Bỏ dấu tiếng Việt để so khớp "kính"/"kinh" không phân biệt dấu. */
    function plainText(value) {
        return String(value === null || value === undefined ? "" : value)
            .toLowerCase()
            .normalize("NFD").replace(/[̀-ͯ]/g, "")
            .replace(/đ/g, "d");
    }

    /** Dòng kính: có khai kính mặc định, hoặc tên/nhóm/slug chứa "kính". */
    function isGlassRow(row) {
        if (!row) return false;
        if (!isBlank(row.default_glass_master)) return true;
        var hay = plainText(row.line_name) + " " + plainText(row.category)
            + " " + plainText(row.slug);
        return /(^|[^a-z])kinh([^a-z]|$)/.test(hay);
    }

    /**
     * Nhãn người-đọc của 1 dòng BOM: `line_name`; chưa đặt tên ⇒
     * "Dòng chưa đặt tên (Dòng N)" — ⛔ slug kỹ thuật trong mọi danh sách
     * chọn (UX1 chấm chặn 2026-11-25).
     */
    function rowDisplayName(row, index) {
        var name = trim(row && row.line_name);
        if (name) return name;
        var fallback = translate("Dòng chưa đặt tên");
        if (typeof index === "number" && index >= 0) {
            return fallback + " (" + translate("Dòng") + " " + (index + 1) + ")";
        }
        return fallback;
    }

    /** Vị trí (0-based) của dòng có `slug` trong mảng — -1 nếu không thấy. */
    function rowIndexBySlug(items, slug) {
        var want = trim(slug);
        if (!want || !Array.isArray(items)) return -1;
        for (var i = 0; i < items.length; i++) {
            if (items[i] && trim(items[i].slug) === want) return i;
        }
        return -1;
    }

    /** Tách `items.<slug>.<field>` → {slug, field}; sai dạng ⇒ null. */
    function parseItemExpr(expr) {
        var m = trim(expr).match(/^items\.([A-Za-z_][\w-]*)\.([A-Za-z_]\w*)$/);
        return m ? { slug: m[1], field: m[2] } : null;
    }

    function findRowBySlug(items, slug) {
        if (!Array.isArray(items)) return null;
        var want = trim(slug);
        for (var i = 0; i < items.length; i++) {
            if (items[i] && trim(items[i].slug) === want) return items[i];
        }
        return null;
    }

    /**
     * Đọc giá trị hiện tại của `items.<slug>.<field>` từ các dòng đang có.
     * Alias độ dày: `glass_thick` ↔ `total_thick_mm` (engine nhận cả hai).
     * Trả {value, row, field} hoặc null.
     */
    function resolveItemValue(items, expr) {
        var ref = parseItemExpr(expr);
        if (!ref) return null;
        var row = findRowBySlug(items, ref.slug);
        if (!row) return null;
        var candidates = [ref.field];
        if (ref.field === "glass_thick" || ref.field === "total_thick_mm") {
            candidates = ["total_thick_mm", "glass_thick"];
        }
        for (var i = 0; i < candidates.length; i++) {
            var value = row[candidates[i]];
            if (!isBlank(value)) {
                return { value: value, row: row, field: candidates[i] };
            }
        }
        return null;
    }

    function _optionLabel(lineName, field) {
        var label = translate(ITEM_FIELD_LABELS[field] || field);
        var unit = ITEM_FIELD_UNITS[field];
        if (unit) label += " (" + unit + ")";
        return lineName + " — " + label;
    }

    function _numericSample(value) {
        if (isBlank(value)) return null;
        return toNumberOrNull(value) === null ? null : toNumberOrNull(value);
    }

    /**
     * Dựng danh sách option "dữ liệu đem tra" từ dòng của bộ + biến chứng từ.
     * Mỗi option: {value, label, group, sample_value} — KHÔNG trùng `value`.
     *
     * `input.item_fields` — cột kích thước được mời cho MỖI dòng (mặc định
     * `["width","height"]`). Bảng phụ kiện không có 2 cột đó ⇒ truyền `[]`.
     * `qty` luôn bị loại (ô công thức số lượng tự tham chiếu).
     */
    function buildInputOptions(input) {
        input = input || {};
        var items = Array.isArray(input.items) ? input.items : [];
        var variables = Array.isArray(input.variables) ? input.variables : [];
        var itemFields = Array.isArray(input.item_fields)
            ? input.item_fields : DEFAULT_ITEM_FIELDS;
        var out = [];
        var seen = {};

        function push(value, label, group, sample) {
            if (!value || seen[value]) return;
            seen[value] = true;
            out.push({
                value: value,
                label: label,
                group: group,
                sample_value: sample === undefined ? null : sample,
            });
        }

        items.forEach(function (row, rowIndex) {
            if (!row || isBlank(row.slug)) return;
            // ⛔ slug làm nhãn: dòng chưa đặt tên hiện "Dòng chưa đặt tên (Dòng N)".
            var lineName = rowDisplayName(row, rowIndex);
            var glass = isGlassRow(row);
            if (glass) {
                var thick = row.total_thick_mm;
                if (isBlank(thick)) thick = row.glass_thick;
                push("items." + row.slug + ".total_thick_mm",
                    _optionLabel(lineName, "total_thick_mm"), translate(GROUP_ITEM),
                    _numericSample(thick));
                push("items." + row.slug + ".glass_type",
                    _optionLabel(lineName, "glass_type"), translate(GROUP_ITEM),
                    isBlank(row.glass_type) ? null : row.glass_type);
            }
            itemFields.forEach(function (field) {
                var name = trim(field);
                if (!name || FORBIDDEN_ITEM_FIELDS.indexOf(name) !== -1) return;
                push("items." + row.slug + "." + name,
                    _optionLabel(lineName, name), translate(GROUP_ITEM),
                    _numericSample(row[name]));
            });
        });

        variables.forEach(function (variable) {
            if (!variable) return;
            var name = trim(variable.name);
            if (!name) return;
            var label = trim(variable.label) || name;
            if (label !== name) label += " (" + name + ")";
            push(name, label, translate(GROUP_VARIABLE), isBlank(variable.value) ? null : variable.value);
        });

        return out;
    }

    /** Option biến (dùng cho ô "Nhân với") — loại option dòng vật tư. */
    function buildVariableOptions(input) {
        return buildInputOptions(input).filter(function (option) {
            return option.group === translate(GROUP_VARIABLE);
        });
    }

    /**
     * Option cho ô `rule_input_expr` — CHỈ thứ engine đọc được:
     *   dòng kính × {độ dày kính (`total_thick_mm`), loại kính (`glass_type`)}
     * KHÔNG width/height/qty, KHÔNG biến, KHÔNG dòng không phải kính
     * (xem `bom_orchestrator._resolve_rule_input_for_item`).
     */
    function buildRuleInputOptions(items) {
        var out = [];
        var seen = {};
        (Array.isArray(items) ? items : []).forEach(function (row, rowIndex) {
            if (!row || isBlank(row.slug) || !isGlassRow(row)) return;
            var lineName = rowDisplayName(row, rowIndex);

            var thickField = "total_thick_mm";
            var thickValue = "items." + row.slug + "." + thickField;
            if (!seen[thickValue]) {
                seen[thickValue] = true;
                var thick = row.total_thick_mm;
                if (isBlank(thick)) thick = row.glass_thick;
                out.push({
                    value: thickValue,
                    label: _optionLabel(lineName, thickField),
                    group: translate(GROUP_ITEM),
                    sample_value: _numericSample(thick),
                });
            }

            var typeValue = "items." + row.slug + ".glass_type";
            if (!seen[typeValue]) {
                seen[typeValue] = true;
                out.push({
                    value: typeValue,
                    label: _optionLabel(lineName, "glass_type"),
                    group: translate(GROUP_ITEM),
                    sample_value: isBlank(row.glass_type) ? null : row.glass_type,
                });
            }
        });
        return out;
    }

    // ── 4b. Quy tắc khai biến THEO DÒNG (input_scope = ROW) ────────────
    // Chặng 3 (thiết kế §7.2): quy tắc khai biến theo dòng ⇒ dòng BOM chỉ chọn
    // DÒNG NGUỒN (`rule_input_row` = slug), không chọn cột. Danh sách dòng mời
    // suy từ chính biến của quy tắc — ⛔ danh sách field cứng của từng bảng.
    var ROW_SLUG_PATTERN = /^[A-Za-z_][\w-]*$/;

    /** Giá trị của `variable` trên 1 dòng (nhận alias độ dày); rỗng ⇒ null. */
    function rowVariableValue(row, variable) {
        if (!row) return null;
        var name = trim(variable);
        if (!name) return null;
        var candidates = [name];
        var alias = ITEM_FIELD_ALIASES[name];
        if (alias) candidates.push(alias);
        for (var i = 0; i < candidates.length; i++) {
            if (!isBlank(row[candidates[i]])) return row[candidates[i]];
        }
        return null;
    }

    /**
     * Dòng có cung cấp được `variable` cho quy tắc hay không.
     * - Biến lấy từ dữ liệu KÍNH (`GLASS_VALUE_FIELDS`) ⇒ chỉ dòng kính.
     * - Biến khác ⇒ dòng phải THẬT SỰ có giá trị; dòng trống thì engine đọc ra
     *   rỗng ⇒ chọn vào là dòng không có mã (lỗi im lặng phải chặn từ UI).
     */
    function rowSupportsVariable(row, variable) {
        if (!row || isBlank(row.slug)) return false;
        var name = trim(variable);
        if (!name) return false;
        if (GLASS_VALUE_FIELDS.indexOf(name) !== -1) return isGlassRow(row);
        return !isBlank(rowVariableValue(row, name));
    }

    /** Biểu thức `items.<slug>.<variable>` cho 1 dòng nguồn. */
    function ruleRowOptionExpr(slug, variable) {
        var line = trim(slug);
        var name = trim(variable);
        if (!line || !name || !ROW_SLUG_PATTERN.test(line)) return "";
        return "items." + line + "." + name;
    }

    /** Mẫu thử tra của 1 dòng: số nếu đọc được số, còn lại giữ nguyên chữ. */
    function _rowVariableSample(row, variable) {
        var value = rowVariableValue(row, variable);
        if (isBlank(value)) return null;
        var number = toNumberOrNull(value);
        return number === null ? value : number;
    }

    /**
     * Biến theo dòng do ENGINE TỰ TÍNH (`computed = true` trong
     * `get_rule_input_variables`) ⇒ chọn được MỌI dòng BOM, không lọc theo
     * field kính. Thiếu cờ / chưa có danh mục (server cũ) ⇒ `null` = chưa
     * biết, nơi gọi giữ hành vi cũ (⛔ đoán).
     */
    function ruleInputVariableComputed(variables, name) {
        var want = trim(name);
        if (!want || !Array.isArray(variables)) return null;
        for (var i = 0; i < variables.length; i++) {
            var entry = variables[i];
            if (!entry || trim(entry.name) !== want) continue;
            return _flagIsTrue(entry.computed, false);
        }
        return null;
    }

    /**
     * Biến của quy tắc có phải loại ENGINE TỰ TÍNH không — đọc từ 3 nguồn
     * theo thứ tự: metadata quy tắc (`input_computed`), cờ truyền tay
     * (`opts.computed`), rồi danh mục biến (`opts.variables`).
     */
    function ruleVariableIsComputed(rule, opts) {
        opts = opts || {};
        if (_flagIsTrue(rule && rule.input_computed, false)) return true;
        if (_flagIsTrue(opts.computed, false)) return true;
        return ruleInputVariableComputed(opts.variables, ruleInputVariable(rule)) === true;
    }

    /**
     * Danh sách "dòng lấy dữ liệu" của quy tắc ROW:
     *   [{slug, line_name, value: "items.<slug>.<var>", label, sample_value}]
     * `value` rỗng khi slug không dựng được biểu thức hợp lệ.
     * Quy tắc chưa khai biến ⇒ [] (caller rơi về đường cũ).
     *
     * `opts.variables` = danh mục `get_rule_input_variables()`; biến có
     * `computed = true` (engine tự tính) ⇒ liệt kê MỌI dòng BOM (UX1 #4).
     */
    function buildRuleRowOptions(rule, items, opts) {
        var variable = ruleInputVariable(rule);
        if (!variable) return [];
        var label = ruleInputLabel(rule);
        var computed = ruleVariableIsComputed(rule, opts);
        var out = [];
        var seen = {};
        (Array.isArray(items) ? items : []).forEach(function (row, rowIndex) {
            if (!row || isBlank(row.slug)) return;
            // Biến engine TỰ TÍNH theo dòng ⇒ dòng nào cũng dùng được. Biến
            // thường vẫn phải dòng đó THẬT SỰ có dữ liệu.
            if (!computed && !rowSupportsVariable(row, variable)) return;
            var slug = trim(row.slug);
            if (seen[slug]) return;
            seen[slug] = true;
            var lineName = rowDisplayName(row, rowIndex);
            out.push({
                slug: slug,
                line_name: lineName,
                value: ruleRowOptionExpr(slug, variable),
                label: lineName + " — " + label,
                group: translate(GROUP_ITEM),
                sample_value: computed ? null : _rowVariableSample(row, variable),
                computed: !!computed,
            });
        });
        return out;
    }

    /**
     * Câu ghi chú khi biến là loại ENGINE TỰ TÍNH: nói rõ vì sao mời được
     * mọi dòng. Rỗng khi biến thường / chưa biết.
     */
    function ruleRowComputedNote(rule, opts) {
        if (!ruleVariableIsComputed(rule, opts)) return "";
        return translate("Hệ thống tự tính")
            + " " + ruleInputLabel(rule)
            + " " + translate("khi tính giá — chọn dòng nào cũng được.");
    }

    /** Tìm option dòng nguồn theo slug (dùng để phản chiếu `rule_input_row`). */
    function findRuleRowOption(options, slug) {
        var want = trim(slug);
        if (!want) return null;
        for (var i = 0; i < (options || []).length; i++) {
            if (options[i] && trim(options[i].slug) === want) return options[i];
        }
        return null;
    }

    /**
     * Danh sách lựa chọn cho bước "dữ liệu đem tra" của hộp chèn công thức —
     * phân nhánh theo quy tắc tự khai (chặng 3):
     *   ROW    ⇒ chỉ các dòng có biến của quy tắc (`items.<dòng>.<cột>`).
     *   GLOBAL ⇒ rỗng (quy tắc tự lấy, ⛔ hỏi người dùng).
     *   chưa khai ⇒ như cũ (dòng × `item_fields` + biến chứng từ).
     */
    function buildRuleInsertOptions(input) {
        input = input || {};
        var plan = ruleInsertPlan(input.rule);
        if (plan.scope === "ROW") {
            return buildRuleRowOptions(input.rule, input.items, {
                variables: input.input_variables,
            });
        }
        if (plan.scope === "GLOBAL") return [];
        return buildInputOptions({
            items: input.items,
            variables: input.variables,
            item_fields: input.item_fields,
        });
    }

    /**
     * Cột `rule_input_expr` mà ENGINE đọc được cho dòng kính
     * (`glass_data[slug]` — xem `bom_orchestrator` dựng `glass_data`).
     * Rộng hơn allowlist của ô chọn (3 cột) vì dữ liệu cũ có thể dùng
     * `max_area_m2`/`glass_name`/`glass_type_name` — vẫn chạy đúng.
     */
    var RULE_INPUT_READABLE_FIELDS = RULE_INPUT_ALLOWED_FIELDS.concat(
        ["max_area_m2", "glass_name", "glass_type_name"]);

    function isRuleInputReadable(expr, items) {
        var ref = parseItemExpr(expr);
        if (!ref) return false;
        var row = findRowBySlug(items, ref.slug);
        if (!row || !isGlassRow(row)) return false;
        return RULE_INPUT_READABLE_FIELDS.indexOf(ref.field) !== -1;
    }

    /**
     * Kiểm 1 giá trị `rule_input_expr` có phải NGUỒN DỮ LIỆU engine đọc được
     * hay không. Trả `{ok, message}` — message là câu người-đọc-được nêu việc
     * cần làm (dùng cho ô nhập tay của hộp chọn).
     */
    function validateRuleInput(expr, items) {
        var text = trim(expr);
        if (!text) {
            return {
                ok: false,
                message: translate("Chọn một nguồn dữ liệu trong danh sách."),
            };
        }
        var ref = parseItemExpr(text);
        if (!ref) {
            return {
                ok: false,
                message: translate("Chưa đúng dạng nguồn dữ liệu — chọn trong danh sách, hoặc nhập đúng dạng items.<dòng>.<cột>."),
            };
        }
        var row = findRowBySlug(items, ref.slug);
        if (!row) {
            return {
                ok: false,
                message: translate("Dòng dữ liệu đã chọn không còn trong bộ này — chọn lại."),
            };
        }
        if (!isGlassRow(row)) {
            return {
                ok: false,
                message: translate("Quy tắc chỉ đọc được độ dày kính hoặc loại kính của DÒNG KÍNH — dòng đang chọn không phải dòng kính."),
            };
        }
        if (RULE_INPUT_ALLOWED_FIELDS.indexOf(ref.field) === -1) {
            return {
                ok: false,
                message: translate("Quy tắc chỉ đọc được độ dày kính hoặc loại kính của dòng kính — cột đang chọn không đọc được."),
            };
        }
        return { ok: true, message: "" };
    }

    // ── 5. Câu chữ kết quả thử tra ─────────────────────────────────────
    function resultText(resp) {
        if (!resp || !resp.result || typeof resp.result !== "object") return "";
        var result = resp.result;
        if (!isBlank(result.item_code)) {
            var itemName = trim(result.item_name);
            return itemName
                ? String(result.item_code) + " (" + itemName + ")"
                : String(result.item_code);
        }
        if (result.value !== undefined && result.value !== null && result.value !== "") {
            return formatNumberRaw(result.value);
        }
        return "";
    }

    /** "Khớp dải 0 – 10,38" / "Khớp khóa LOWE" / "Quy tắc hằng số". */
    function matchText(resp) {
        if (!resp || !resp.matched || typeof resp.matched !== "object") return "";
        var matched = resp.matched;
        if (matched.from !== undefined && matched.from !== null
                && matched.to !== undefined && matched.to !== null) {
            return translate("Khớp dải") + " " + formatNumberUi(matched.from)
                + " – " + formatNumberUi(matched.to);
        }
        if (!isBlank(matched.key)) {
            return translate("Khớp khóa") + " " + String(matched.key);
        }
        return translate("Quy tắc hằng số");
    }

    /** Nhãn chủ ngữ trong câu thử: ưu tiên nhãn người đọc, thiếu mới dùng giá trị. */
    function _previewSubject(option) {
        var label = trim(option && option.label);
        if (label) return label;
        return trim(option && option.value);
    }

    function _previewValue(value) {
        if (value === null || value === undefined || value === "") return "—";
        return formatNumberRaw(value);
    }

    /**
     * "Chiều cao (H_mm) = 3200 → 4 bản lề/cánh × Số cánh (n_panel) 2 = 8"
     * — câu kết quả thử trong hộp chèn công thức.
     * `output_label` chỉ ghép khi kết quả là SỐ (kết quả mã vật tư đã có tên
     * riêng, ghép thêm nhãn sẽ thành "C3209-20 (Nẹp 20) Mã nẹp").
     * `multiplierOption` rỗng ⇒ bỏ phần "× …".
     */
    function samplePreviewText(option, resp, multiplierOption) {
        if (!option) return "";
        var line = _previewSubject(option) + " = " + _previewValue(option.sample_value);
        var out = resultText(resp);
        var hasItemResult = !!(resp && resp.result
            && !isBlank(resp.result.item_code));
        var outLabel = hasItemResult ? "" : trim(resp && resp.output_label);
        line += " → " + (out ? out + (outLabel ? " " + outLabel : "") : translate("chưa tra được"));
        if (multiplierOption) {
            var mValue = multiplierOption.sample_value;
            var mText = isBlank(mValue) ? trim(multiplierOption.value) : formatNumberRaw(mValue);
            var mLabel = trim(multiplierOption.label) || trim(multiplierOption.value);
            var extra = "";
            var nResult = resp && resp.result ? toNumberOrNull(resp.result.value) : null;
            var nMultiplier = toNumberOrNull(mValue);
            if (nResult !== null && nMultiplier !== null) {
                extra = " = " + formatNumberRaw(nResult * nMultiplier);
            }
            line += " × " + mLabel + " " + mText + extra;
        }
        return line;
    }

    // ── 6. Gọi server (chỉ Desk) ───────────────────────────────────────
    var _rulesCache = { rows: null, ts: 0 };
    var _ruleMetaCache = {};
    // Danh mục biến "Tra theo" — giữ cả cờ `computed` để hộp chọn dòng biết
    // biến nào do engine tự tính (liệt kê MỌI dòng BOM).
    var _inputVariablesCache = { rows: null, ts: 0 };
    var RULES_TTL = 60000;

    // Object đánh dấu "lượt gọi thử tra THẤT BẠI" — tách khỏi payload nghiệp
    // vụ của server (vốn có `success`/`result`). `text` là nguyên văn câu
    // `_server_messages`; rỗng nghĩa là server không kèm câu nào.
    var PREVIEW_ERROR_KEY = "__preview_error";

    function makePreviewError(text) {
        var out = {};
        out[PREVIEW_ERROR_KEY] = trim(text);
        return out;
    }

    function isPreviewError(resp) {
        return !!(resp && typeof resp === "object"
            && Object.prototype.hasOwnProperty.call(resp, PREVIEW_ERROR_KEY));
    }

    /**
     * Lấy câu người-đọc-được từ lỗi của `frappe.call`.
     * Đọc `_server_messages` (chuỗi JSON của mảng JSON, mỗi phần tử có
     * `message`) — ĐÚNG thứ `frappe.throw()` sinh ra. Không có thì "".
     */
    function extractServerMessage(error) {
        var payload = error;
        if (payload && payload.responseJSON) payload = payload.responseJSON;
        var raw = payload && payload._server_messages;
        if (isBlank(raw)) return "";
        var messages = raw;
        if (typeof raw === "string") {
            try {
                messages = JSON.parse(raw);
            } catch (e) {
                return trim(raw);
            }
        }
        if (!Array.isArray(messages)) return trim(messages);
        for (var i = 0; i < messages.length; i++) {
            var entry = messages[i];
            if (typeof entry === "string") {
                try { entry = JSON.parse(entry); } catch (e2) { /* chuỗi thường */ }
            }
            var text = (entry && typeof entry === "object") ? entry.message : entry;
            text = trim(text);
            if (text) return text;
        }
        return "";
    }

    function _hasFrappe() {
        return typeof frappe !== "undefined" && frappe;
    }

    function _listRules(fields) {
        return new Promise(function (resolve, reject) {
            if (!_hasFrappe() || !frappe.db || typeof frappe.db.get_list !== "function") {
                return resolve([]);
            }
            frappe.db.get_list("AL Rule", {
                filters: { result_type: "NUMBER" },
                fields: fields,
                limit: 200,
                order_by: "rule_name asc",
            }).then(function (rows) {
                resolve(rows || []);
            }).catch(reject);
        });
    }

    /**
     * Danh sách quy tắc trả SỐ đang bật (cache 60 s).
     * Thử đủ field mô tả trước; site CHƯA migrate ⇒ tự lùi về field cũ.
     */
    function fetchNumberRules(opts) {
        opts = opts || {};
        var now = Date.now();
        if (!opts.force && _rulesCache.rows && (now - _rulesCache.ts) < RULES_TTL) {
            return Promise.resolve(_rulesCache.rows);
        }
        var full = ["name", "rule_code", "rule_name", "rule_description",
            "input_label", "input_unit", "output_label", "is_active",
            "rule_type", "result_type",
            // Chặng 3: quy tắc tự khai "tra theo cái gì" (site chưa migrate ⇒
            // lượt đọc này lỗi, tự lùi về `basic` bên dưới).
            "input_variable", "input_scope"];
        var basic = ["name", "rule_code", "rule_name", "is_active",
            "rule_type", "result_type"];
        return _listRules(full).catch(function () {
            // Chưa migrate (thiếu cột mô tả) — vẫn phải chọn được quy tắc.
            return _listRules(basic);
        }).then(function (rows) {
            var out = filterNumberRules((rows || []).map(normalizeRule));
            _rulesCache = { rows: out, ts: Date.now() };
            return out;
        });
    }

    /**
     * Danh mục biến "Tra theo" `[{name, label, category, scope, resolvable,
     * computed}]` — cache 60 s. Thiếu API / lỗi ⇒ [] (nơi gọi giữ hành vi cũ,
     * ⛔ chặn người dùng).
     */
    function fetchInputVariables(opts) {
        opts = opts || {};
        var now = Date.now();
        if (!opts.force && _inputVariablesCache.rows
                && (now - _inputVariablesCache.ts) < RULES_TTL) {
            return Promise.resolve(_inputVariablesCache.rows);
        }
        return new Promise(function (resolve) {
            if (!_hasFrappe() || typeof frappe.call !== "function") {
                return resolve([]);
            }
            frappe.call({
                method: "alumglass.api.get_rule_input_variables",
            }).then(function (r) {
                var rows = r && Array.isArray(r.message) ? r.message
                    : (Array.isArray(r) ? r : []);
                _inputVariablesCache = { rows: rows, ts: Date.now() };
                resolve(rows);
            }).catch(function (e) {
                console.warn("[AlumGlass] Không tải được danh mục biến:", e);
                resolve([]);
            });
        });
    }

    /** Danh mục biến đã cache (rỗng khi chưa nạp) — dùng đồng bộ lúc vẽ. */
    function cachedInputVariables() {
        return Array.isArray(_inputVariablesCache.rows)
            ? _inputVariablesCache.rows : [];
    }

    /** Đọc 1 quy tắc (có cache) — chịu được meta/DB chưa có field mô tả. */
    function fetchRuleMeta(code) {
        var want = trim(code);
        if (!want) return Promise.resolve(null);
        var cached = _ruleMetaCache[want];
        if (cached && (Date.now() - cached.ts) < RULES_TTL) {
            return Promise.resolve(cached.data);
        }
        return new Promise(function (resolve) {
            if (!_hasFrappe() || !frappe.db) return resolve(null);
            var request;
            if (typeof frappe.db.get_doc === "function") {
                request = frappe.db.get_doc("AL Rule", want);
            } else if (typeof frappe.call === "function") {
                request = frappe.call({
                    method: "frappe.client.get",
                    args: { doctype: "AL Rule", name: want },
                }).then(function (r) { return r && r.message; });
            } else {
                return resolve(null);
            }
            Promise.resolve(request).then(function (doc) {
                var data = normalizeRule(doc);
                _ruleMetaCache[want] = { data: data, ts: Date.now() };
                resolve(data);
            }).catch(function (e) {
                console.warn("[AlumGlass] Không đọc được quy tắc", want, e);
                _ruleMetaCache[want] = { data: null, ts: Date.now() };
                resolve(null);
            });
        });
    }

    /**
     * Mẫu để thử tra cho 1 option: ưu tiên `sample_value`; thiếu thì lấy từ
     * kính mặc định của dòng (độ dày/loại kính) nếu có.
     */
    function fetchOptionSample(option, items) {
        return new Promise(function (resolve) {
            if (!option) return resolve(null);
            if (!isBlank(option.sample_value)) return resolve(option.sample_value);
            var ref = parseItemExpr(option.value);
            if (!ref) return resolve(null);

            // 1. Dòng đang giữ GIÁ TRỊ THẬT (số hoặc khoá) ⇒ dùng luôn.
            //    Ô đang giữ CÔNG THỨC (vd `W_mm / n_panel`) thì bỏ — ⛔ gửi
            //    biểu thức lên server rồi báo "không khớp" gây hiểu nhầm.
            var direct = resolveItemValue(items, option.value);
            if (direct && !isBlank(direct.value)) {
                if (ref.field === "glass_type") return resolve(direct.value);
                var number = toNumberOrNull(direct.value);
                if (number !== null) return resolve(number);
            }

            // 2. Độ dày/loại kính của dòng kính: lấy từ kính mặc định.
            var row = findRowBySlug(items, ref.slug);
            if (!row || isBlank(row.default_glass_master)) return resolve(null);
            if (GLASS_VALUE_FIELDS.indexOf(ref.field) === -1) return resolve(null);
            if (!_hasFrappe() || !frappe.db || typeof frappe.db.get_value !== "function") {
                return resolve(null);
            }
            frappe.db.get_value("AL Glass Master", row.default_glass_master,
                ["total_thick_mm", "glass_type"]).then(function (res) {
                var data = (res && res.message) ? res.message : (res || {});
                var value = data[ref.field];
                if (ref.field === "glass_thick") value = data.total_thick_mm;
                resolve(isBlank(value) ? null : value);
            }).catch(function () { resolve(null); });
        });
    }

    /**
     * Giá trị HIỆN TẠI của 1 biến chứng từ (vd `H_mm`) — lấy từ cache
     * FormulaContext để "Thử tra" của quy tắc khai biến toàn cục điền sẵn.
     * Chưa có cache / biến chưa có số ⇒ null (hộp thoại cho nhập tay).
     */
    function fetchVariableSample(frm, table, variable) {
        return new Promise(function (resolve) {
            var want = trim(variable);
            if (!want || !frm) return resolve(null);
            var variables = [];
            try {
                if (typeof alumglass !== "undefined" && alumglass.FormulaContext
                        && typeof alumglass.FormulaContext.getSync === "function") {
                    var ctx = alumglass.FormulaContext.getSync(
                        frm.doctype, frm.docname || (frm.doc && frm.doc.name) || "",
                        table || "") || {};
                    variables = Array.isArray(ctx.variables) ? ctx.variables : [];
                }
            } catch (e) { /* rơi về null */ }
            for (var i = 0; i < variables.length; i++) {
                var entry = variables[i];
                if (entry && trim(entry.name) === want) {
                    return resolve(isBlank(entry.value) ? null : entry.value);
                }
            }
            resolve(null);
        });
    }

    /**
     * Gọi API thử tra. Thành công ⇒ payload của server.
     * Lỗi ⇒ object `{__preview_error: "<câu server hoặc ''>"}` — KHÔNG nuốt
     * thành null, để hộp thoại hiện đúng lý do thay vì luôn đổ cho quyền.
     */
    function callPreviewRule(ruleCode, inputValue) {
        return new Promise(function (resolve) {
            var code = trim(ruleCode);
            if (!code || !_hasFrappe() || typeof frappe.call !== "function") {
                return resolve(makePreviewError(""));
            }
            frappe.call({
                method: "alumglass.api.preview_rule",
                args: { rule_code: code, input_value: inputValue },
            }).then(function (r) {
                if (r && r.message && typeof r.message === "object") {
                    return resolve(r.message);
                }
                resolve(makePreviewError(""));
            }).catch(function (e) {
                console.warn("[AlumGlass] preview_rule lỗi:", e);
                resolve(makePreviewError(extractServerMessage(e)));
            });
        });
    }

    function fetchRuleForCode(code) {
        return fetchRuleMeta(code);
    }

    // ── 7. Ghi giá trị vào ô công thức (Monaco đang mở / set_value) ────
    function _childDoctype(frm, table) {
        var field = frm && frm.fields_dict && frm.fields_dict[table];
        var df = field && (field.df || (field.grid && field.grid.df));
        return df && df.options ? df.options : "";
    }

    function _gridRow(frm, table, cdn) {
        var field = frm && frm.fields_dict && frm.fields_dict[table];
        var grid = field && field.grid;
        if (!grid) return null;
        if (typeof grid.get_row === "function") return grid.get_row(cdn);
        return (grid.grid_rows_by_docname || {})[cdn] || null;
    }

    /** Wrapper của 1 field HTML trong dòng con đang mở rộng. */
    function rowFieldWrapper(frm, table, cdn, fieldname) {
        var row = _gridRow(frm, table, cdn);
        var gridForm = row && row.grid_form;
        var field = gridForm && gridForm.fields_dict && gridForm.fields_dict[fieldname];
        if (field && field.$wrapper && field.$wrapper.length) return field.$wrapper;
        return $();
    }

    /**
     * Ghi `value` vào field công thức của dòng con.
     * - Luôn ghi model (`frappe.model.set_value`) vì Monaco `setValue` KHÔNG
     *   tự ghi model — nếu chỉ setValue thì "chèn xong ô vẫn trống".
     * - Monaco đang mở ⇒ đồng bộ thêm để người dùng thấy ngay.
     * - Monaco chưa dựng ⇒ gọi set_value của control (nếu có).
     */
    function insertFormula(opts) {
        opts = opts || {};
        var frm = opts.frm;
        var table = opts.child_table;
        var cdn = opts.cdn;
        var fieldname = opts.fieldname;
        var value = opts.value;
        if (!frm || !table || !cdn || !fieldname || isBlank(value)) return false;

        var cdt = opts.child_doctype || _childDoctype(frm, table);
        if (!cdt) {
            console.warn("[AlumGlass] Không xác định được doctype dòng con:", table);
            return false;
        }

        var key = frm.doctype + "::" + table + "::" + cdn + "::" + fieldname;
        // Chụp editor NGAY (trước khi set_value) — nếu để tới sau promise thì
        // một thao tác khác đóng editor trong lúc chờ sẽ làm mất đồng bộ.
        var editorApi = window._afbPatchedEditors && window._afbPatchedEditors[key];
        var wrote = frappe.model.set_value(cdt, cdn, fieldname, value);

        var applyToEditor = function () {
            var api = editorApi || (window._afbPatchedEditors && window._afbPatchedEditors[key]);
            var editorSynced = false;
            if (api && typeof api.setValue === "function") {
                try { api.setValue(value); editorSynced = true; } catch (e) { /* rơi xuống */ }
            }
            // Ô tĩnh trong lưới (khi dòng thu gọn) — Monaco tự cập nhật khi đóng.
            try {
                var cell = document.querySelector(
                    '.grid-row[data-name="' + cdn + '"] .grid-static-col[data-fieldname="'
                    + fieldname + '"] .afb-grid-cell-static');
                if (cell) cell.textContent = value;
            } catch (e) { /* bỏ qua */ }
            if (!editorSynced) {
                var row = _gridRow(frm, table, cdn);
                var control = row && row.grid_form && row.grid_form.fields_dict
                    && row.grid_form.fields_dict[fieldname];
                if (control && typeof control.set_value === "function") {
                    try { control.set_value(value); } catch (e) { /* bỏ qua */ }
                }
            }
            if (typeof frm.dirty === "function") frm.dirty();
        };

        if (wrote && typeof wrote.then === "function") {
            wrote.then(applyToEditor);
        } else {
            applyToEditor();
        }

        if (typeof frappe.show_alert === "function") {
            frappe.show_alert({
                message: opts.toast || translate("Đã chèn công thức"),
                indicator: "green",
            }, 3);
        }
        return true;
    }

    // ── 8. Hộp thoại "Chọn công thức" ─────────────────────────────────
    function _itemsOf(frm, table) {
        var rows = frm && frm.doc && frm.doc[table];
        return Array.isArray(rows) ? rows : [];
    }

    function _formulaContext(frm, table) {
        try {
            if (typeof alumglass !== "undefined" && alumglass.FormulaContext
                    && typeof alumglass.FormulaContext.getSync === "function") {
                return alumglass.FormulaContext.getSync(
                    frm.doctype, frm.docname, table) || {};
            }
        } catch (e) { /* bỏ qua */ }
        return {};
    }

    function _optionByValue(options, value) {
        var want = trim(value);
        if (!want) return null;
        for (var i = 0; i < (options || []).length; i++) {
            if (options[i] && trim(options[i].value) === want) return options[i];
        }
        return null;
    }

    // Alias độ dày `glass_thick` ↔ `total_thick_mm` khai ở §1 (ITEM_FIELD_ALIASES)
    // — dùng chung cho cả danh sách option lẫn cách đọc dữ liệu theo dòng.

    /** Tìm option khớp `value`, tính cả alias `glass_thick` ↔ `total_thick_mm`. */
    function findEquivalentOption(options, value) {
        var want = trim(value);
        if (!want) return null;
        var exact = _optionByValue(options, want);
        if (exact) return exact;
        var ref = parseItemExpr(want);
        if (!ref) return null;
        var alias = ITEM_FIELD_ALIASES[ref.field];
        if (!alias) return null;
        return _optionByValue(options, "items." + ref.slug + "." + alias);
    }

    /** Nhãn dòng đang sửa cho tiêu đề hộp thoại (⛔ không dùng slug kỹ thuật nếu có tên). */
    function _lineLabelFor(frm, table, cdn, opts) {
        var label = trim(opts && opts.line_label);
        if (label) return label;
        var rows = _itemsOf(frm, table);
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            if (!row || trim(row.name) !== trim(cdn)) continue;
            label = trim(row.line_name) || trim(row.label)
                || trim(row.item_name) || trim(row.item_code)
                || rowDisplayName(row, i);
            break;
        }
        return label;
    }

    /** Giá trị ĐANG CÓ của ô công thức (model là nguồn; editor Monaco ghi vào model). */
    function _currentFieldValue(frm, table, cdn, fieldname) {
        var row = _gridRow(frm, table, cdn);
        if (row && row.doc) return trim(row.doc[fieldname]);
        var rows = _itemsOf(frm, table);
        for (var i = 0; i < rows.length; i++) {
            if (rows[i] && trim(rows[i].name) === trim(cdn)) {
                return trim(rows[i][fieldname]);
            }
        }
        return "";
    }

    function _optgroupsHtml(options, selected, placeholder) {
        var groups = [];
        var index = {};
        (options || []).forEach(function (option) {
            var name = option.group || "";
            if (index[name] === undefined) {
                index[name] = groups.length;
                groups.push({ name: name, items: [] });
            }
            groups[index[name]].items.push(option);
        });
        var html = '<option value="">' + escapeHtml(placeholder) + "</option>";
        groups.forEach(function (group) {
            if (group.name) {
                html += '<optgroup label="' + escapeHtml(group.name) + '">';
            }
            group.items.forEach(function (option) {
                html += '<option value="' + escapeHtml(option.value) + '"'
                    + (option.value === selected ? " selected" : "") + ">"
                    + escapeHtml(option.label) + "</option>";
            });
            if (group.name) html += "</optgroup>";
        });
        return html;
    }

    /**
     * Hộp thoại chèn công thức KHÔNG-CẦN-CODE cho ô công thức số lượng:
     *   1. Số lượng cố định   2. Theo số cánh   3. 2 × số cánh
     *   4. Tra quy tắc theo giá trị — quy tắc tự khai "tra theo cái gì" thì
     *      BỎ bước chọn dữ liệu (GLOBAL) hoặc chỉ hỏi DÒNG chứa biến (ROW).
     */
    function openInsert(opts) {
        opts = opts || {};
        var frm = opts.frm;
        var table = opts.child_table;
        var cdn = opts.cdn;
        var fieldname = opts.fieldname;
        if (!frm || !table || !cdn || !fieldname) return;
        if (!_hasFrappe() || !frappe.ui || !frappe.ui.Dialog) return;

        var items = _itemsOf(frm, table);
        var context = _formulaContext(frm, table);
        var contextVariables = Array.isArray(context.variables) ? context.variables : [];
        // Giá trị ĐANG CÓ của ô — phản chiếu vào hộp thoại để không ghi đè
        // im lặng khi người dùng chỉ mở ra xem rồi bấm Chèn.
        var existing = _currentFieldValue(frm, table, cdn, fieldname);
        var parsed = parseFormulaSnippet(existing);
        var state = {
            preset: parsed.preset,
            fixed: parsed.fixed || "",
            rule: parsed.rule || "",
            input: "",
            manual: "",
            multiplier: parsed.multiplier || "",
            rules: [],
            rules_ready: false,
            rules_error: false,
            items: items,
            item_fields: Array.isArray(opts.item_fields) ? opts.item_fields : null,
            variables: contextVariables,
            options: [],
            var_options: [],
            vars_loading: contextVariables.length === 0,
            vars_error: false,
            // Danh mục biến "Tra theo" (có cờ `computed`) — nạp nền để hộp
            // chọn dòng biết biến nào engine tự tính.
            input_variables: cachedInputVariables(),
            // Trạng thái quy tắc đang chọn khi mở lại hộp thoại: "", active,
            // inactive, missing, unknown (UX1 #12).
            rule_state: "",
            existing: existing,
            touched: false,
            preview_seq: 0,
            // Công thức đang có dạng MỘT tham số (`lookup_rule('MÃ')`) — chỉ hợp
            // lệ khi quy tắc tự lấy dữ liệu; giữ để không vẽ lại bước chọn
            // dữ liệu trong lúc danh sách quy tắc còn đang nạp.
            single_arg: !!parsed.single_arg,
            parsed_input: trim(parsed.input),
            // Chặng 4: điều kiện tra của quy tắc ĐANG CHỌN (cache theo mã
            // trong phiên hộp thoại) + tên vật tư đã tra được.
            conditions: {},
            conditions_waiting: {},
            item_names: {},
        };

        /** Metadata quy tắc đang chọn (null khi chưa nạp xong / không còn). */
        function currentRuleMeta() {
            return findRule(state.rules, state.rule);
        }

        /**
         * Kế hoạch bước "dữ liệu đem tra". KHÔNG đọc được metadata quy tắc
         * (danh sách chưa nạp xong / quy tắc không còn trong danh sách) mà
         * công thức đang có dạng 1 tham số ⇒ coi là quy tắc tự lấy dữ liệu
         * (dạng đó chỉ hợp lệ với quy tắc như vậy), ⛔ bày bước chọn thừa.
         */
        function currentPlan() {
            var meta = currentRuleMeta();
            var plan = ruleInsertPlan(meta);
            if (!plan.declared && !meta && state.single_arg) {
                return {
                    declared: true, scope: "GLOBAL", variable: "",
                    label: ruleInputLabel(meta), needs_input: false, single_arg: true,
                };
            }
            return plan;
        }

        function rebuildOptions() {
            // ROW: chỉ dòng có biến của quy tắc (biến engine TỰ TÍNH ⇒ mọi
            // dòng); GLOBAL: không cần dữ liệu; chưa khai: giữ danh sách cũ.
            var meta = currentRuleMeta();
            state.options = buildRuleInsertOptions({
                rule: meta,
                items: items,
                variables: state.variables,
                item_fields: state.item_fields,
                input_variables: state.input_variables,
            });
            state.var_options = buildVariableOptions({
                items: [], variables: state.variables,
            });
        }

        /** Áp công thức đang có lên các ô chọn — chỉ khi người dùng CHƯA sửa. */
        function applyParsedState() {
            if (state.touched || !parsed.raw) return;
            state.preset = parsed.preset || state.preset;
            if (parsed.preset === "fixed") state.fixed = parsed.fixed;
            if (parsed.preset !== "rule") return;
            state.rule = parsed.rule || state.rule;
            state.multiplier = parsed.multiplier || state.multiplier;
            // Danh sách option phụ thuộc quy tắc vừa ánh xạ ⇒ dựng lại trước
            // khi so khớp (ROW ≠ danh sách biểu thức của đường cũ).
            rebuildOptions();
            var input = trim(parsed.input);
            if (!input) {
                state.input = "";
                state.manual = "";
                return;
            }
            if (_optionByValue(state.options, input)) {
                state.input = input;
                state.manual = "";
            } else {
                // Biểu thức chưa có trong danh sách ⇒ để ở ô "Nhập tay" nhưng
                // vẫn hiện đúng chuỗi cũ, ⛔ xoá trắng.
                state.input = "__manual__";
                state.manual = input;
            }
        }

        rebuildOptions();
        applyParsedState();

        var lineLabel = _lineLabelFor(frm, table, cdn, opts);
        // `Dialog.set_title` chèn bằng `.html()` ⇒ phải escape tên dòng.
        var dialogTitle = lineLabel
            ? escapeHtml(translate("Chọn công thức cho dòng") + " " + lineLabel)
            : translate("Chọn công thức");

        var dlg = new frappe.ui.Dialog({
            title: dialogTitle,
            size: "large",
            fields: [{ fieldtype: "HTML", fieldname: "insert_body" }],
            primary_action_label: translate("Chèn công thức"),
            primary_action: function () {
                doInsert();
            },
        });
        dlg.show();
        var $w = dlg.fields_dict.insert_body.$wrapper;

        fetchNumberRules({ force: true }).then(function (rules) {
            state.rules = rules || [];
            state.rules_ready = true;
            render();
            loadRuleState();
        }).catch(function (e) {
            console.warn("[AlumGlass] Không tải được danh sách quy tắc:", e);
            state.rules = [];
            state.rules_ready = true;
            state.rules_error = true;
            render();
            loadRuleState();
        });

        /**
         * Quy tắc đang có nhưng KHÔNG nằm trong danh sách chọn ⇒ đọc trạng
         * thái thật để nói đúng lý do (tắt/xoá/không trả số/chưa kiểm tra
         * được). ⛔ đoán bừa "không tồn tại".
         */
        function loadRuleState() {
            var code = trim(state.rule);
            if (!code || findRule(state.rules, code)) {
                state.rule_state = "";
                return;
            }
            fetchRuleState(code).then(function (info) {
                // Người dùng đã đổi quy tắc trong lúc chờ ⇒ ⛔ vẽ đè.
                if (trim(state.rule) !== code) return;
                state.rule_state = info && info.state ? info.state : "unknown";
                render(true);
            });
        }

        function readDom() {
            var $fixed = $w.find('input[data-role="fixed"]');
            if ($fixed.length) state.fixed = String($fixed.val() || "");
            var $rule = $w.find('select[data-role="rule"]');
            if ($rule.length) {
                var pickedRule = String($rule.val() || "");
                // Quy tắc đang có mà KHÔNG nằm trong danh sách (đã tắt / đã
                // xoá) ⇒ ô chọn rơi về "" — ⛔ coi là người dùng bỏ chọn, nếu
                // không sẽ mất luôn cảnh báo "quy tắc đã tắt/xoá" (#12).
                if (pickedRule || !state.rule) state.rule = pickedRule;
            }
            var $input = $w.find('select[data-role="input"]');
            if ($input.length) state.input = String($input.val() || "");
            var $manual = $w.find('input[data-role="manual"]');
            if ($manual.length) state.manual = String($manual.val() || "");
            var $multiplier = $w.find('select[data-role="multiplier"]');
            if ($multiplier.length) {
                var multiplierValue = String($multiplier.val() || "");
                // Biến đang chọn CHƯA có trong danh sách (cache đang nạp) ⇒ ô
                // select chỉ hiện "Không nhân"; ⛔ đọc "" rồi xoá mất giá trị
                // vừa phản chiếu từ công thức cũ.
                var known = _optionByValue(state.var_options, state.multiplier);
                if (multiplierValue || known) state.multiplier = multiplierValue;
            }
        }

        /**
         * Đồng bộ `state.input` với danh sách option của quy tắc đang chọn.
         * Đổi quy tắc (legacy → ROW…) làm option cũ không còn ⇒ giữ nguyên
         * chuỗi ở ô "Nhập tay" thay vì câm lặng mất.
         */
        function syncInputWithPlan() {
            var plan = currentPlan();
            if (!plan.needs_input) {
                state.input = "";
                return;
            }
            if (state.input === "__manual__") return;
            var current = trim(state.input);
            if (!current) return;
            if (_optionByValue(state.options, current)
                    || findEquivalentOption(state.options, current)) return;
            state.input = "__manual__";
            state.manual = current;
        }

        function currentSnippet() {
            if (state.preset === "fixed") {
                return buildPresetSnippet({ preset: "fixed", value: state.fixed });
            }
            if (state.preset === "panels") return buildPresetSnippet({ preset: "panels" });
            if (state.preset === "panels2") return buildPresetSnippet({ preset: "panels2" });
            if (state.preset === "rule") {
                var plan = currentPlan();
                if (plan.scope === "GLOBAL") {
                    // Quy tắc tự lấy dữ liệu tra ⇒ engine tự chèn biến, công
                    // thức chỉ cần mã quy tắc (+ hệ số nhân nếu có).
                    return buildSnippet({
                        code: state.rule,
                        multiplier: state.multiplier,
                        single_arg: true,
                    });
                }
                var input = state.input === "__manual__" ? trim(state.manual) : state.input;
                return buildSnippet({
                    code: state.rule,
                    input: input,
                    multiplier: state.multiplier,
                });
            }
            return null;
        }

        function previewHtml() {
            var snippet = currentSnippet();
            var html = "";
            if (snippet) {
                html += '<div style="font-size:11px;color:#64748b;">'
                    + escapeHtml(translate("Công thức sẽ chèn")) + "</div>"
                    + '<div style="font-family:monospace;font-size:12px;color:#0f172a;'
                    + 'word-break:break-all;">' + escapeHtml(snippet) + "</div>";
            } else {
                html += '<div style="font-size:12px;color:#94a3b8;">'
                    + escapeHtml(translate("Chưa đủ thông tin để chèn.")) + "</div>";
            }
            html += '<div data-role="sample" style="font-size:12px;color:#047857;'
                + 'margin-top:4px;"></div>';
            return html;
        }

        function ruleSectionHtml() {
            var html = '<div class="form-group"><label class="control-label">'
                + escapeHtml(translate("Quy tắc")) + "</label>";
            if (!state.rules_ready) {
                html += '<div style="font-size:12px;color:#94a3b8;">'
                    + escapeHtml(translate("Đang tải danh sách quy tắc…")) + "</div>";
                return html + "</div>";
            }
            if (!state.rules.length) {
                var hint = state.rules_error
                    ? translate("Chưa tải được danh sách quy tắc. Kiểm tra quyền xem quy tắc rồi thử lại.")
                    : translate("Chưa có quy tắc trả số nào. Tạo quy tắc trước rồi mở lại hộp này.");
                html += '<div style="font-size:12px;color:#64748b;padding:6px 8px;'
                    + 'border:1px dashed #cbd5e1;border-radius:6px;">'
                    + escapeHtml(hint) + "</div>";
                html += '<div style="margin-top:6px;"><button type="button" '
                    + 'class="btn btn-xs btn-default" data-role="new-rule">'
                    + escapeHtml(translate("Tạo quy tắc mới")) + "</button></div>";
                return html + "</div>";
            }
            html += '<select class="form-control input-sm" data-role="rule">'
                + '<option value="">' + escapeHtml(translate("— Chọn quy tắc —")) + "</option>";
            state.rules.forEach(function (rule) {
                var code = trim(rule.rule_code);
                html += '<option value="' + escapeHtml(code) + '"'
                    + (code === state.rule ? " selected" : "") + ">"
                    + escapeHtml(trim(rule.rule_name) || code) + "</option>";
            });
            html += "</select>";
            var current = findRule(state.rules, state.rule);
            if (current) {
                html += '<div style="font-size:11px;color:#64748b;margin-top:3px;">';
                // Quy tắc tự khai "tra theo": nói rõ nó lấy dữ liệu gì thay vì
                // để người dùng tự suy từ bảng bên dưới.
                if (ruleInputScope(current) === "GLOBAL") {
                    html += ruleGlobalSentenceHtml(current);
                } else {
                    html += escapeHtml(ruleSummary(current));
                }
                if (!isBlank(current.rule_description)) {
                    html += " — " + escapeHtml(current.rule_description);
                }
                html += "</div>";
                // ĐIỀU KIỆN TRA ngay dưới ô chọn (Owner 2026-11-25) — người
                // dựng báo giá thấy quy tắc tra cái gì trước khi bấm Chèn,
                // ⛔ phải mở form quy tắc.
                html += '<div data-role="rule-conditions" style="margin-top:4px;">'
                    + conditionsBlockHtml(current) + "</div>";
            } else if (state.rule) {
                // Quy tắc đang có KHÔNG nằm trong danh sách chọn (đã tắt / đã
                // xoá / không trả số / chưa kiểm tra được) ⇒ nói rõ + cho
                // chọn quy tắc khác thay vì im lặng mất lựa chọn (UX1 #12).
                var notice = ruleStateNoticeText(state.rule_state, { not_listed: true });
                if (notice) {
                    html += '<div style="font-size:12px;color:#b45309;background:#fffbeb;'
                        + 'border:1px solid #fde68a;border-radius:4px;padding:6px 8px;'
                        + 'margin-top:4px;line-height:1.45;">⚠ '
                        + escapeHtml(notice) + "</div>";
                }
            }
            html += '<div style="margin-top:4px;"><button type="button" '
                + 'class="btn btn-xs btn-default" data-role="new-rule">'
                + escapeHtml(translate("Tạo quy tắc mới")) + "</button></div>";
            return html + "</div>";
        }

        /**
         * Điều kiện tra của quy tắc ĐANG CHỌN, dựng từ cache trong phiên hộp
         * thoại. Chưa đọc xong ⇒ câu "đang đọc"; đọc lỗi/không quyền ⇒ câu
         * "Chưa đọc được…" + link (⛔ giấu quy tắc, ⛔ làm vỡ hộp thoại).
         *
         * Metadata trong `state.rules` KHÔNG có bảng điều kiện ⇒ khi chưa có
         * doc thì loại quy tắc phải để trống, ⛔ lấy `rule_type` của danh sách
         * rồi đoán điều kiện.
         */
        function conditionsBlockHtml(rule) {
            var code = trim(rule && rule.rule_code);
            if (!code) return "";
            var doc = state.conditions[code];
            if (doc === undefined) {
                return '<div style="font-size:11px;color:#94a3b8;">'
                    + escapeHtml(translate("Đang đọc điều kiện tra…")) + "</div>";
            }
            var source = doc;
            if (!source) {
                source = {
                    name: trim(rule.name) || code,
                    rule_code: code,
                    input_label: rule.input_label,
                    // Cần cả TÊN BIẾN: nhãn cũ trùng tên biến phải được làm sạch
                    // (đọc từ DB có thể là `total_thick_mm`) — xem readableInputLabel.
                    input_variable: rule.input_variable,
                    input_unit: rule.input_unit,
                    output_label: rule.output_label,
                    rule_type: "",
                    result_type: "",
                };
            }
            return ruleConditionPreviewHtml(source, {
                max: 3,
                heading: "compact",
                item_names: state.item_names,
            });
        }

        /** Vẽ RIÊNG ô điều kiện — ⛔ render lại cả hộp thoại (mất ô đang chọn). */
        function paintConditionsSlot() {
            var $slot = $w.find('[data-role="rule-conditions"]');
            if (!$slot.length) return;
            $slot.html(conditionsBlockHtml(currentRuleMeta()));
        }

        /** Tra TÊN vật tư của kết quả ("N10" → "Nẹp nhôm 10") rồi vẽ lại ô. */
        function loadConditionItemNames(code, doc) {
            var codes = ruleConditionItemCodes(doc);
            var missing = codes.filter(function (itemCode) {
                return state.item_names[itemCode] === undefined;
            });
            if (!missing.length) return;
            fetchItemNames(codes).then(function (names) {
                Object.keys(names || {}).forEach(function (itemCode) {
                    state.item_names[itemCode] = names[itemCode];
                });
                if (trim(state.rule) !== code) return;
                paintConditionsSlot();
            });
        }

        /**
         * Nạp điều kiện cho quy tắc ĐANG chọn — một lượt, KHÔNG đọc cho cả
         * danh sách. Kết quả về muộn (người dùng đã đổi mã) ⇒ vẫn ghi cache
         * nhưng ⛔ vẽ đè quy tắc đang chọn.
         */
        function loadRuleConditions() {
            var rule = currentRuleMeta();
            var code = trim(rule && rule.rule_code);
            if (!code) return;
            if (state.conditions[code] !== undefined) {
                if (state.conditions[code]) {
                    loadConditionItemNames(code, state.conditions[code]);
                }
                return;
            }
            if (state.conditions_waiting[code]) return;
            state.conditions_waiting[code] = true;
            fetchRuleConditionsDoc(code).then(function (doc) {
                delete state.conditions_waiting[code];
                // Ghi cache kể cả khi đã đổi quy tắc — lần chọn lại không gọi
                // API lần nữa.
                state.conditions[code] = doc || null;
                if (trim(state.rule) !== code) return;
                paintConditionsSlot();
                if (doc) loadConditionItemNames(code, doc);
            }).catch(function () {
                delete state.conditions_waiting[code];
                state.conditions[code] = null;
                if (trim(state.rule) !== code) return;
                paintConditionsSlot();
            });
        }

        /** Quy tắc tự lấy dữ liệu (GLOBAL) ⇒ ⛔ hỏi dữ liệu, chỉ nói nó lấy gì. */
        function globalInputNoticeHtml() {
            return '<div class="form-group"><label class="control-label">'
                + escapeHtml(translate("Dữ liệu đem tra")) + "</label>"
                + '<div data-role="global-input" style="font-size:13px;color:#0f172a;'
                + 'padding:6px 8px;border:1px dashed #cbd5e1;border-radius:6px;">'
                + ruleGlobalSentenceHtml(currentRuleMeta())
                + "</div>"
                + '<div style="font-size:11px;color:#64748b;margin-top:3px;">'
                + escapeHtml(translate("Quy tắc tự lấy giá trị khi tính — bạn không phải chọn."))
                + "</div>";
        }

        function inputSectionHtml() {
            var plan = currentPlan();
            if (!plan.needs_input) {
                var block = globalInputNoticeHtml();
                if (state.parsed_input) {
                    // Công thức đang có TRUYỀN giá trị riêng; chèn mới sẽ đổi
                    // sang dạng tự lấy ⇒ phải nói trước, ⛔ đổi im lặng.
                    block += '<div style="font-size:11px;color:#b45309;margin-top:3px;">'
                        + escapeHtml(translate("Công thức đang có truyền giá trị riêng — chèn mới sẽ dùng dạng quy tắc tự lấy dữ liệu."))
                        + "</div>";
                }
                return block + "</div>";
            }
            var isRow = plan.scope === "ROW";
            var label = isRow
                ? translate("Dòng lấy dữ liệu") : translate("Dữ liệu đem tra");
            var html = '<div class="form-group"><label class="control-label">'
                + escapeHtml(label) + "</label>"
                + '<select class="form-control input-sm" data-role="input">'
                + _optgroupsHtml(state.options, state.input,
                    isRow ? translate("— Chọn dòng —") : translate("— Chọn dữ liệu —"))
                + '<option value="__manual__"' + (state.input === "__manual__" ? " selected" : "")
                + ">" + escapeHtml(translate("Nhập tay…")) + "</option></select>";
            if (isRow && !state.options.length) {
                // Không có dòng nào chứa biến ⇒ nói đúng việc cần làm, ⛔ để
                // ô chọn rỗng câm lặng.
                html += '<div style="font-size:11px;color:#b45309;margin-top:3px;">'
                    + escapeHtml(translate("Bộ này chưa có dòng nào chứa dữ liệu quy tắc cần — chọn dữ liệu ở dòng nguồn (vd dòng kính) trước."))
                    + "</div>";
            }
            if (isRow) {
                var computedNote = ruleRowComputedNote(currentRuleMeta(), {
                    variables: state.input_variables,
                });
                if (computedNote) {
                    // Biến do ENGINE TỰ TÍNH ⇒ mọi dòng đều dùng được; nói rõ
                    // để người dùng không tưởng danh sách liệt kê sai (#4).
                    html += '<div style="font-size:11px;color:#047857;margin-top:3px;">'
                        + escapeHtml(computedNote) + "</div>";
                } else {
                    html += '<div style="font-size:11px;color:#64748b;margin-top:3px;">'
                        + escapeHtml(translate("Danh sách chỉ gồm những dòng có dữ liệu quy tắc đọc."))
                        + "</div>";
                }
            }
            if (state.input === "__manual__") {
                html += '<input type="text" class="form-control input-sm" data-role="manual" '
                    + 'style="margin-top:4px;" value="' + escapeHtml(state.manual) + '" '
                    + 'placeholder="' + escapeHtml(translate("Ví dụ: H_mm - 100")) + '">';
            }
            return html + "</div>";
        }

        function multiplierSectionHtml() {
            var html = '<div class="form-group"><label class="control-label">'
                + escapeHtml(translate("Nhân với (tuỳ chọn)")) + "</label>"
                + '<select class="form-control input-sm" data-role="multiplier">'
                + '<option value="">' + escapeHtml(translate("Không nhân")) + "</option>";
            state.var_options.forEach(function (option) {
                html += '<option value="' + escapeHtml(option.value) + '"'
                    + (option.value === state.multiplier ? " selected" : "") + ">"
                    + escapeHtml(option.label) + "</option>";
            });
            html += "</select>";
            // Cache biến chưa có ⇒ nói rõ đang tải; tải xong vẫn rỗng ⇒ nói
            // việc cần làm thay vì để ô trống không giải thích.
            if (state.vars_loading) {
                html += '<div style="font-size:11px;color:#94a3b8;margin-top:3px;">'
                    + escapeHtml(translate("Đang tải danh sách biến…")) + "</div>";
            } else if (!state.var_options.length) {
                html += '<div style="font-size:11px;color:#b45309;margin-top:3px;">'
                    + escapeHtml(translate("Chưa lấy được danh sách biến — tải lại trang.")) + "</div>";
            }
            return html + "</div>";
        }

        /** Nạp biến của chứng từ khi cache chưa có (mở form lần đầu / đổi bảng). */
        function loadVariables() {
            var contextApi = (typeof alumglass !== "undefined" && alumglass.FormulaContext)
                ? alumglass.FormulaContext : null;
            if (!contextApi || typeof contextApi.fetch !== "function") {
                state.vars_loading = false;
                state.vars_error = true;
                render();
                return;
            }
            var docname = frm.docname || (frm.doc && frm.doc.name) || "";
            state.vars_loading = true;
            state.vars_error = false;
            render();
            Promise.resolve(contextApi.fetch(frm.doctype, docname, table))
                .then(function (data) {
                    state.vars_loading = false;
                    state.variables = (data && Array.isArray(data.variables))
                        ? data.variables : [];
                    rebuildOptions();
                    if (!state.variables.length) state.vars_error = true;
                    applyParsedState();
                    render(true);
                })
                .catch(function (e) {
                    console.warn("[AlumGlass] Không tải được danh sách biến:", e);
                    state.vars_loading = false;
                    state.vars_error = true;
                    applyParsedState();
                    render(true);
                });
        }

        function bind() {
            $w.off(".alrule");
            $w.on("click.alrule", "[data-preset]", function () {
                readDom();
                state.touched = true;
                state.preset = String($(this).attr("data-preset") || "");
                render();
            });
            $w.on("click.alrule", "[data-role='new-rule']", function () {
                dlg.hide();
                if (typeof frappe.new_doc === "function") frappe.new_doc("AL Rule");
            });
            $w.on("change.alrule", "select[data-role]", function () {
                readDom();
                state.touched = true;
                render();
            });
            $w.on("input.alrule", "input[data-role]", function () {
                readDom();
                state.touched = true;
                updatePreview();
            });
        }

        function render(skipRead) {
            // `skipRead`: state vừa được dựng lại từ dữ liệu mới (vd biến về
            // muộn) ⇒ ⛔ đọc DOM cũ đè lên, nếu không lựa chọn vừa ánh xạ lại
            // bị kéo về giá trị cũ.
            if (!skipRead) readDom();
            // Danh sách dữ liệu đem tra phụ thuộc QUY TẮC đang chọn (GLOBAL /
            // ROW / chưa khai) ⇒ dựng lại mỗi lượt vẽ, rồi đồng bộ lựa chọn.
            rebuildOptions();
            syncInputWithPlan();
            var html = '<div style="font-size:13px;color:#475569;margin-bottom:10px;">'
                + escapeHtml(translate("Chọn cách tính số lượng cho ô đang mở — không cần biết công thức."))
                + "</div>";
            if (state.existing) {
                // Bề mặt cấu hình công thức ⇒ hiện nguyên chuỗi ô đang có để
                // người dùng đối chiếu trước khi thay (không phải câu cho
                // người dùng cuối).
                html += '<div style="font-size:12px;color:#64748b;margin-bottom:10px;'
                    + 'word-break:break-all;">'
                    + escapeHtml(translate("Ô đang có:")) + " "
                    + '<span style="font-family:monospace;color:#0f172a;">'
                    + escapeHtml(state.existing) + "</span></div>";
            }
            html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;">';
            presetDefinitions().forEach(function (preset) {
                var active = state.preset === preset.kind;
                html += '<div data-preset="' + preset.kind + '" style="cursor:pointer;'
                    + "border:1px solid " + (active ? "#f59e0b" : "#e2e8f0")
                    + ";border-radius:6px;padding:8px 10px;background:"
                    + (active ? "#fffbeb" : "#fff") + ';">'
                    + '<div style="font-weight:600;font-size:13px;">' + preset.icon + " "
                    + escapeHtml(preset.label) + "</div>"
                    + '<div style="font-size:11px;color:#64748b;margin-top:2px;">'
                    + escapeHtml(preset.desc) + "</div>"
                    + '<div style="font-size:11px;color:#94a3b8;margin-top:2px;">'
                    + escapeHtml(preset.example) + "</div></div>";
            });
            html += "</div>";

            if (!state.preset) {
                html += '<div style="font-size:12px;color:#94a3b8;">'
                    + escapeHtml(translate("Chọn một cách ở trên để xem chi tiết.")) + "</div>";
            } else if (state.preset === "fixed") {
                html += '<div class="form-group"><label class="control-label">'
                    + escapeHtml(translate("Số lượng mỗi dòng")) + "</label>"
                    + '<input type="text" class="form-control input-sm" data-role="fixed" '
                    + 'style="max-width:160px;" value="' + escapeHtml(state.fixed) + '" '
                    + 'placeholder="' + escapeHtml(translate("Ví dụ: 4")) + '"></div>';
            } else if (state.preset === "rule") {
                html += ruleSectionHtml() + inputSectionHtml() + multiplierSectionHtml();
            }

            html += '<div id="al-rule-insert-preview" style="margin-top:10px;padding:8px 10px;'
                + 'background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;min-height:40px;">'
                + previewHtml() + "</div>";

            $w.html(html);
            bind();
            scheduleSamplePreview();
            // Quy tắc đang chọn ⇒ đọc điều kiện tra ngay dưới ô chọn (chỉ
            // quy tắc đang chọn; đổi mã thì lượt cũ bị bỏ).
            if (state.preset === "rule") loadRuleConditions();
        }

        function updatePreview() {
            $w.find("#al-rule-insert-preview").html(previewHtml());
            scheduleSamplePreview();
        }

        function scheduleSamplePreview() {
            var $sample = $w.find('[data-role="sample"]');
            if (!$sample.length) return;
            $sample.text("");
            if (state.preset !== "rule") return;

            var code = trim(state.rule);
            if (!code) return;

            var plan = currentPlan();
            var option = null;
            var manual = "";
            if (plan.scope === "GLOBAL") {
                // Quy tắc tự lấy dữ liệu ⇒ mẫu thử là giá trị HIỆN TẠI của
                // chính biến đó (lấy từ biến chứng từ), ⛔ hỏi người dùng.
                if (!plan.variable) return;
                for (var i = 0; i < state.variables.length; i++) {
                    var entry = state.variables[i];
                    if (!entry || trim(entry.name) !== plan.variable) continue;
                    option = {
                        value: plan.variable,
                        label: (trim(entry.label) || plan.variable)
                            + " (" + plan.variable + ")",
                        sample_value: isBlank(entry.value) ? null : entry.value,
                    };
                    break;
                }
                if (!option || isBlank(option.sample_value)) {
                    // Thiếu giá trị ⇒ KHÔNG im lặng (trước đây bỏ trống, người
                    // dùng tưởng đã có số). Nói rõ thiếu gì + kiểm tra đâu.
                    $sample.html(variableMissingNoticeHtml(plan.label));
                    return;
                }
            } else {
                option = state.input === "__manual__"
                    ? null : _optionByValue(state.options, state.input);
                manual = state.input === "__manual__" ? trim(state.manual) : "";
                if (!option && !manual) return;
                // Nhập tay là BIỂU THỨC (vd `H_mm - 100`) ⇒ không có giá trị
                // hiện tại để thử, ⛔ gửi nguyên chuỗi biểu thức lên server.
                if (manual && toNumberOrNull(manual) === null) return;
            }

            var multiplierOption = _optionByValue(state.var_options, state.multiplier);
            var seq = ++state.preview_seq;
            var subject = option || { value: manual, label: manual, sample_value: manual };

            fetchOptionSample(subject, state.items).then(function (sample) {
                if (seq !== state.preview_seq) return;
                if (isBlank(sample)) return;  // không có mẫu ⇒ im lặng
                return callPreviewRule(code, sample).then(function (resp) {
                    if (seq !== state.preview_seq || !resp) return;
                    // Lỗi gọi API ⇒ ⛔ đoán "chưa tra được" như một kết quả.
                    if (isPreviewError(resp)) return;
                    var shown = {};
                    Object.keys(subject).forEach(function (k) { shown[k] = subject[k]; });
                    shown.sample_value = sample;
                    $sample.text(samplePreviewText(shown, resp, multiplierOption));
                });
            });
        }

        function doInsert() {
            readDom();
            // Quy tắc đã tắt / đã xoá ⇒ chèn công thức là chèn một lời gọi
            // chắc chắn không ra kết quả. Chặn + nói việc cần làm (#12).
            if (state.rule && (state.rule_state === "missing"
                    || state.rule_state === "inactive")) {
                frappe.show_alert({
                    message: ruleStateNoticeText(state.rule_state),
                    indicator: "orange",
                }, 6);
                return;
            }
            var snippet = currentSnippet();
            if (!snippet) {
                frappe.show_alert({
                    message: translate("Chọn đủ thông tin rồi bấm Chèn công thức."),
                    indicator: "orange",
                }, 4);
                return;
            }
            var apply = function () {
                insertFormula({
                    frm: frm,
                    child_table: table,
                    cdn: cdn,
                    fieldname: fieldname,
                    value: snippet,
                });
                dlg.hide();
            };
            // Ô đang có công thức KHÁC ⇒ hỏi trước khi thay (mở hộp thoại chỉ
            // để xem rồi bấm Chèn không được ghi đè im lặng).
            if (state.existing && state.existing !== trim(snippet)
                    && typeof frappe.confirm === "function") {
                frappe.confirm(
                    translate("Ô đang có công thức khác. Thay bằng công thức mới?")
                    + '<div style="margin-top:8px;font-size:12px;color:#64748b;">'
                    + escapeHtml(translate("Hiện tại:")) + " "
                    + '<span style="font-family:monospace;word-break:break-all;">'
                    + escapeHtml(state.existing) + "</span></div>"
                    + '<div style="font-size:12px;color:#0f766e;">'
                    + escapeHtml(translate("Sẽ thay bằng:")) + " "
                    + '<span style="font-family:monospace;word-break:break-all;">'
                    + escapeHtml(snippet) + "</span></div>",
                    apply);
                return;
            }
            apply();
        }

        render();
        // Cache biến chưa có ⇒ nạp rồi vẽ lại (ô "Nhân với" không được rỗng
        // câm lặng khi người dùng vừa mở form).
        if (state.vars_loading) loadVariables();
        // Danh mục biến "Tra theo" (cờ `computed`) chưa có ⇒ nạp nền rồi vẽ
        // lại: biến engine tự tính phải liệt kê MỌI dòng BOM (#4).
        if (!state.input_variables.length) {
            fetchInputVariables().then(function (rows) {
                state.input_variables = rows || [];
                rebuildOptions();
                render(true);
            });
        }
    }

    // ── 9. Hộp thoại "Thử tra" ────────────────────────────────────────
    function _previewInputLabel(state) {
        var resp = state.resp || {};
        var variable = trim(resp.input_variable);
        // `state.label` do caller truyền (đã làm sạch ở form/BOM) — nhưng
        // `resp.input_label` là giá trị ĐỌC TỪ DB, dữ liệu cũ có thể đã lưu
        // đúng MÃ BIẾN ⇒ vẫn phải đi qua hàm chung.
        var raw = trim(state.label) || trim(resp.input_label);
        var base = readableInputLabel(raw, variable, translate("Giá trị đem tra"));
        var unit = state.unit || resp.input_unit || "";
        if (unit && base.indexOf("(") === -1) return base + " (" + unit + ")";
        return base;
    }

    function _rowsTable(rows) {
        rows = Array.isArray(rows) ? rows : [];
        if (!rows.length) return "";
        var hasFrom = rows.some(function (r) { return r && r.from !== undefined && r.from !== null; });
        // Cột "Đến" phải hiện khi có dải số — kể cả dải MỞ (Đến trống =
        // "trở lên"), nếu không người dùng không thấy cận trên ở đâu cả.
        var hasTo = rows.some(function (r) {
            if (!r) return false;
            var hasToValue = r.to !== undefined && r.to !== null;
            var hasFromValue = r.from !== undefined && r.from !== null;
            return hasToValue || hasFromValue;
        });
        var hasKey = rows.some(function (r) { return r && !isBlank(r.key); });
        var head = "";
        if (hasFrom) head += "<th>" + escapeHtml(translate("Từ")) + "</th>";
        if (hasTo) head += "<th>" + escapeHtml(translate("Đến")) + "</th>";
        if (hasKey) head += "<th>" + escapeHtml(translate("Khóa")) + "</th>";
        head += "<th>" + escapeHtml(translate("Kết quả")) + "</th>";
        var body = rows.map(function (row) {
            row = row || {};
            var style = row.is_match
                ? ' style="background:#fef3c7;font-weight:600;"' : "";
            var cells = "";
            if (hasFrom) cells += "<td>" + escapeHtml(formatNumberUi(row.from)) + "</td>";
            if (hasTo) cells += "<td>" + escapeHtml(rangeToCellText(row.from, row.to)) + "</td>";
            if (hasKey) cells += "<td>" + escapeHtml(formatNumberUi(row.key)) + "</td>";
            cells += "<td>" + escapeHtml(row.result_text || "") + "</td>";
            return "<tr" + style + ">" + cells + "</tr>";
        }).join("");
        return '<table class="table table-condensed table-bordered" '
            + 'style="margin-top:8px;font-size:12px;"><thead><tr>' + head
            + "</tr></thead><tbody>" + body + "</tbody></table>";
    }

    function _previewResultHtml(state) {
        if (state.loading) {
            return '<div style="font-size:12px;color:#94a3b8;">'
                + escapeHtml(translate("Đang tra…")) + "</div>";
        }
        if (state.failed) {
            // Ưu tiên NGUYÊN VĂN câu server (`frappe.throw`); server không kèm
            // câu nào mới dùng câu trung tính — ⛔ không luôn đổ cho quyền.
            var reason = trim(state.error)
                || translate("Chưa thử tra được quy tắc này. Kiểm tra kết nối rồi thử lại.");
            return '<div style="font-size:12px;color:#b45309;">'
                + escapeHtml(reason) + "</div>"
                + '<div style="margin-top:6px;"><button type="button" '
                + 'class="btn btn-xs btn-default" data-role="retry">'
                + escapeHtml(translate("Thử lại")) + "</button></div>";
        }
        var resp = state.resp;
        if (!resp) {
            return '<div style="font-size:12px;color:#94a3b8;">'
                + escapeHtml(translate("Nhập một giá trị rồi bấm Thử tra.")) + "</div>";
        }
        var html = "";
        var title = trim(resp.rule_name) || state.rule_name;
        if (title) {
            html += '<div style="font-weight:600;margin-bottom:2px;">'
                + escapeHtml(title) + "</div>";
        }
        if (!isBlank(resp.rule_description)) {
            html += '<div style="font-size:12px;color:#64748b;margin-bottom:6px;">'
                + escapeHtml(resp.rule_description) + "</div>";
        }
        var matched = matchText(resp);
        var result = resultText(resp);
        if (matched) {
            html += '<div style="font-size:13px;margin-bottom:2px;">'
                + escapeHtml(matched) + "</div>";
        }
        if (result) {
            html += '<div style="font-size:13px;margin-bottom:2px;"><strong>'
                + escapeHtml(translate("Kết quả")) + ":</strong> "
                + escapeHtml(result) + "</div>";
        }
        if (!isBlank(resp.message)) {
            var color = (result || matched) ? "#64748b" : "#b45309";
            html += '<div style="font-size:12px;color:' + color + ';margin:4px 0;">'
                + escapeHtml(resp.message) + "</div>";
        }
        html += _rowsTable(resp.rows);
        return html;
    }

    /**
     * Mở hộp thoại thử tra 1 quy tắc. Nút "Thử tra" trên form AL Rule và
     * dòng AL Bom Item đều gọi hàm này.
     */
    function openRulePreview(opts) {
        opts = opts || {};
        if (!_hasFrappe() || !frappe.ui || !frappe.ui.Dialog) return;
        var ruleCode = trim(opts.rule_code);
        if (!ruleCode) {
            if (typeof frappe.msgprint === "function") {
                frappe.msgprint(translate("Chưa chọn quy tắc để thử tra."));
            }
            return;
        }
        var state = {
            input: (opts.input_value === undefined || opts.input_value === null)
                ? "" : opts.input_value,
            resp: null,
            failed: false,
            error: "",
            loading: false,
            seq: 0,
            label: trim(opts.input_label),
            unit: trim(opts.input_unit),
            rule_name: trim(opts.rule_name),
            // Lượt tính CHƯA có giá trị cho biến quy tắc đọc (GLOBAL) ⇒ nói
            // hổ phách + việc cần làm, ⛔ để người dùng tưởng đã có số (#6).
            global_value_missing: !!opts.global_value_missing,
            variable_label: trim(opts.variable_label),
            // Hộp thoại thử trên BẢN ĐÃ LƯU (API đọc DB) — phải nói rõ để
            // quản trị không tưởng là đang thử bản vừa sửa.
            notice: opts.draft_dirty
                ? translate("Đang thử trên bản đã lưu — bấm Lưu trước để thử bản đang sửa.")
                : "",
        };
        var dlg = new frappe.ui.Dialog({
            title: translate("Thử tra quy tắc"),
            size: "large",
            fields: [{ fieldtype: "HTML", fieldname: "preview_body" }],
            primary_action_label: translate("Đóng"),
            primary_action: function () { dlg.hide(); },
        });
        dlg.show();
        var $w = dlg.fields_dict.preview_body.$wrapper;
        $w.html(
            '<div style="font-size:13px;">'
            + (state.notice
                ? '<div style="font-size:12px;color:#b45309;margin-bottom:8px;">'
                    + escapeHtml(state.notice) + "</div>"
                : "")
            + ((state.global_value_missing && isBlank(state.input))
                ? '<div style="margin-bottom:8px;">'
                    + variableMissingNoticeHtml(state.variable_label || state.label)
                    + "</div>"
                : "")
            + '<label class="control-label" data-role="input-label">'
            + escapeHtml(_previewInputLabel(state)) + "</label>"
            + '<div style="display:flex;gap:6px;align-items:center;">'
            + '<input type="text" class="form-control input-sm" data-role="input" '
            + 'style="max-width:220px;" value="' + escapeHtml(state.input) + '">'
            + '<button type="button" class="btn btn-sm btn-primary" data-role="run">'
            + escapeHtml(translate("Thử tra")) + "</button></div>"
            + '<div data-role="result" style="margin-top:10px;"></div></div>'
        );

        function renderResult() {
            $w.find("[data-role='input-label']").text(_previewInputLabel(state));
            $w.find("[data-role='result']").html(_previewResultHtml(state));
        }

        function currentInputValue() {
            return String($w.find("input[data-role='input']").val() || "");
        }

        function run(value) {
            state.input = value;
            state.loading = true;
            state.failed = false;
            state.error = "";
            var seq = ++state.seq;
            renderResult();
            callPreviewRule(ruleCode, value).then(function (resp) {
                if (seq !== state.seq) return;
                state.loading = false;
                if (isPreviewError(resp)) {
                    state.failed = true;
                    state.error = resp[PREVIEW_ERROR_KEY] || "";
                    state.resp = null;
                } else {
                    state.failed = false;
                    state.error = "";
                    state.resp = resp;
                }
                renderResult();
            });
        }

        $w.on("click", "[data-role='run']", function () {
            run(currentInputValue());
        });
        $w.on("click", "[data-role='retry']", function () {
            run(currentInputValue());
        });
        $w.on("keydown", "input[data-role='input']", function (event) {
            if (event.which === 13) {
                event.preventDefault();
                run(currentInputValue());
            }
        });

        renderResult();
        if (!isBlank(state.input)) run(state.input);
    }

    // ── 10. Hộp thoại "Chọn dữ liệu tra" ─────────────────────────────
    /**
     * Chọn `items.<slug>.<field>` từ danh sách có nhãn người đọc, ghi vào
     * field cấu hình của dòng (mặc định `rule_input_expr`).
     */
    function openInputPicker(opts) {
        opts = opts || {};
        var frm = opts.frm;
        var table = opts.child_table;
        var cdn = opts.cdn;
        var fieldname = opts.fieldname || "rule_input_expr";
        if (!frm || !table || !cdn) return;
        if (!_hasFrappe() || !frappe.ui || !frappe.ui.Dialog) return;

        var items = _itemsOf(frm, table);
        // CHỈ dòng kính × độ dày/loại kính — engine không đọc width/height/qty
        // (chọn "Rộng" sẽ ra 0 âm thầm, dòng không có mã).
        var options = buildRuleInputOptions(items);
        var state = { value: "", manual: "" };
        var row = _gridRow(frm, table, cdn);
        var current = row && row.doc ? String(row.doc[fieldname] || "") : "";
        // Alias `glass_thick` ↔ `total_thick_mm`: công thức cũ (tên cũ) phải
        // khớp option tên chuẩn, ⛔ rơi xuống ô "Nhập tay" kỹ thuật.
        var currentOption = findEquivalentOption(options, current);
        if (currentOption) state.value = currentOption.value;
        else if (current) { state.value = "__manual__"; state.manual = current; }

        var NO_GLASS_MESSAGE = translate(
            "Bộ này chưa có dòng kính để lấy dữ liệu — chọn kính ở dòng kính trước.");

        var dlg = new frappe.ui.Dialog({
            title: translate("Chọn dữ liệu đem tra"),
            size: "large",
            fields: [{ fieldtype: "HTML", fieldname: "picker_body" }],
            primary_action_label: translate("Dùng dữ liệu này"),
            primary_action: function () {
                // Đọc lại DOM: người dùng có thể đổi ô chọn rồi bấm ngay, chưa
                // kịp phát `change` (state khi đó còn giá trị cũ).
                var $value = $w.find("select[data-role='value']");
                if ($value.length) state.value = String($value.val() || "");
                var $manual = $w.find("input[data-role='manual']");
                if ($manual.length) state.manual = String($manual.val() || "");
                if (!options.length) {
                    frappe.show_alert({ message: NO_GLASS_MESSAGE, indicator: "orange" }, 4);
                    return;
                }
                var value = state.value === "__manual__"
                    ? trim(state.manual) : trim(state.value);
                var check = validateRuleInput(value, items);
                if (!check.ok) {
                    frappe.show_alert({ message: check.message, indicator: "orange" }, 4);
                    return;
                }
                insertFormula({
                    frm: frm,
                    child_table: table,
                    cdn: cdn,
                    fieldname: fieldname,
                    value: value,
                    toast: translate("Đã chọn dữ liệu tra"),
                });
                if (typeof opts.on_applied === "function") opts.on_applied(value);
                dlg.hide();
            },
        });
        dlg.show();
        var $w = dlg.fields_dict.picker_body.$wrapper;

        function html() {
            var out = '<div style="font-size:13px;color:#475569;margin-bottom:8px;">'
                + escapeHtml(translate("Chọn nguồn dữ liệu mà quy tắc sẽ đọc — quy tắc chỉ đọc được độ dày kính hoặc loại kính của DÒNG KÍNH."))
                + "</div>";
            if (!options.length) {
                out += '<div style="font-size:12px;color:#b45309;padding:6px 8px;'
                    + 'border:1px dashed #fcd34d;border-radius:6px;margin-bottom:8px;">'
                    + escapeHtml(NO_GLASS_MESSAGE) + "</div>";
                return out;
            }
            out += '<div class="form-group"><select class="form-control input-sm" data-role="value">'
                + _optgroupsHtml(options, state.value, translate("— Chọn dữ liệu —"))
                + '<option value="__manual__"' + (state.value === "__manual__" ? " selected" : "")
                + ">" + escapeHtml(translate("Nhập tay (nguồn dữ liệu)")) + "</option></select></div>";
            if (state.value === "__manual__") {
                out += '<div class="form-group"><input type="text" class="form-control input-sm" '
                    + 'data-role="manual" value="' + escapeHtml(state.manual) + '" '
                    + 'placeholder="' + escapeHtml(translate("Nguồn dữ liệu: items.<dòng>.<cột> — ví dụ items.kinh_tren.glass_thick")) + '"></div>'
                    + '<div style="font-size:11px;color:#64748b;">'
                    + escapeHtml(translate("Chỉ nhận độ dày kính (total_thick_mm / glass_thick) hoặc loại kính (glass_type) của dòng kính."))
                    + "</div>";
            }
            return out;
        }

        function bind() {
            $w.off(".alrule");
            $w.on("change.alrule", "select[data-role='value']", function () {
                state.value = String($(this).val() || "");
                rerender();
            });
            $w.on("input.alrule", "input[data-role='manual']", function () {
                state.manual = String($(this).val() || "");
            });
        }

        function rerender() {
            $w.html(html());
            bind();
        }

        rerender();
    }

    // ── 10b. Hộp thoại "Chọn dòng lấy dữ liệu" (chặng 3) ──────────────
    /**
     * Quy tắc khai biến THEO DÒNG ⇒ dòng BOM chỉ chọn DÒNG NGUỒN (ghi slug
     * vào `rule_input_row`). Danh sách = các dòng có biến của quy tắc, nhãn
     * "Kính trên — Độ dày kính (mm)". ⛔ mời cột khác: cột do quy tắc quyết
     * định, người dùng không chọn.
     *
     * `opts.rule` — metadata quy tắc (đã có `input_variable`/`input_scope`);
     * thiếu thì dùng `opts.rule_code` để đọc, hoặc suy từ `rule_input_row`
     * của dòng (chế độ cũ) — hết cách thì báo chưa đọc được quy tắc.
     */
    function openRuleRowPicker(opts) {
        opts = opts || {};
        var frm = opts.frm;
        var table = opts.child_table;
        var cdn = opts.cdn;
        var fieldname = opts.fieldname || "rule_input_row";
        if (!frm || !table || !cdn) return;
        if (!_hasFrappe() || !frappe.ui || !frappe.ui.Dialog) return;

        var items = _itemsOf(frm, table);
        var row = _gridRow(frm, table, cdn);
        var current = row && row.doc ? trim(row.doc[fieldname]) : "";
        var rule = opts.rule || null;

        var dlg = new frappe.ui.Dialog({
            title: translate("Chọn dòng lấy dữ liệu"),
            size: "large",
            fields: [{ fieldtype: "HTML", fieldname: "picker_body" }],
            primary_action_label: translate("Dùng dòng này"),
            primary_action: function () {
                apply();
            },
        });
        dlg.show();
        var $w = dlg.fields_dict.picker_body.$wrapper;

        function paint(state) {
            $w.html(buildHtml(state));
            $w.off(".alrule");
            $w.on("change.alrule", "select[data-role='row']", function () {
                state.slug = String($(this).val() || "");
                $w.find("[data-role='run']").prop("disabled", !trim(state.slug));
            });
            $w.on("click.alrule", "[data-role='run']", function () {
                apply();
            });
        }

        function apply() {
            // Quy tắc đã TẮT ⇒ chọn dòng cũng không ra kết quả. Nói việc cần
            // làm (đổi quy tắc) thay vì ghi một cấu hình vô dụng (#12).
            if (rule && !isRuleActive(rule)) {
                frappe.show_alert({
                    message: ruleStateNoticeText("inactive"),
                    indicator: "orange",
                }, 6);
                return;
            }
            var $value = $w.find("select[data-role='row']");
            if ($value.length) state.slug = String($value.val() || "");
            var slug = trim(state.slug);
            if (!slug) {
                frappe.show_alert({
                    message: translate("Chọn một dòng rồi bấm Dùng dòng này."),
                    indicator: "orange",
                }, 4);
                return;
            }
            frappe.model.set_value(cdt, cdn, fieldname, slug);
            if (typeof frm.dirty === "function") frm.dirty();
            frappe.show_alert({
                message: translate("Đã chọn dòng lấy dữ liệu"),
                indicator: "green",
            }, 3);
            if (typeof opts.on_applied === "function") opts.on_applied(slug);
            dlg.hide();
        }

        var state = { slug: "", variables: cachedInputVariables(), rule_state: "" };

        function buildHtml(currentState) {
            if (!rule) {
                // Không đọc được metadata ⇒ nói đúng mức hiểu biết: đã xoá,
                // hay chưa kiểm tra được — ⛔ bịa "không tồn tại" (#12).
                var lostText = ruleStateNoticeText(currentState.rule_state)
                    || translate("Chưa đọc được thông tin quy tắc — mở «Xem quy tắc» kiểm tra, hoặc chọn lại quy tắc cho dòng này.");
                return '<div style="font-size:12px;color:#b45309;background:#fffbeb;'
                    + 'border:1px solid #fde68a;border-radius:4px;padding:6px 8px;'
                    + 'line-height:1.45;">⚠ ' + escapeHtml(lostText)
                    + "</div>";
            }
            var options = buildRuleRowOptions(rule, items, {
                variables: currentState.variables,
            });
            var variable = ruleInputVariable(rule);
            var computedNote = ruleRowComputedNote(rule, {
                variables: currentState.variables,
            });

            var out = "";
            if (!isRuleActive(rule)) {
                // Quy tắc đã bị tắt: chọn dòng cũng không ra kết quả ⇒ cảnh
                // báo TRƯỚC, vẫn cho đóng hộp thoại chọn quy tắc khác (#12).
                out += '<div style="font-size:12px;color:#b45309;background:#fffbeb;'
                    + 'border:1px solid #fde68a;border-radius:4px;padding:6px 8px;'
                    + 'margin-bottom:8px;line-height:1.45;">⚠ '
                    + escapeHtml(ruleStateNoticeText("inactive")) + "</div>";
            }
            out += '<div style="font-size:13px;color:#475569;margin-bottom:8px;">'
                + escapeHtml(translate("Chọn dòng chứa dữ liệu quy tắc đọc."))
                + "</div>";
            if (variable && ruleInputScope(rule) !== "") {
                out += '<div style="font-size:12px;color:#0f172a;margin-bottom:8px;">'
                    + ruleRowSentenceHtml(rule, "")
                    + "</div>";
            }
            if (computedNote) {
                out += '<div style="font-size:12px;color:#047857;margin-bottom:8px;'
                    + 'line-height:1.45;">' + escapeHtml(computedNote) + "</div>";
            }
            if (!options.length) {
                out += '<div style="font-size:12px;color:#b45309;padding:6px 8px;'
                    + 'border:1px dashed #fcd34d;border-radius:6px;">'
                    + escapeHtml(translate("Bộ này chưa có dòng nào chứa dữ liệu quy tắc cần — chọn dữ liệu ở dòng nguồn (vd dòng kính) trước."))
                    + "</div>";
                return out;
            }
            var selected = findRuleRowOption(options, currentState.slug) ? currentState.slug : "";
            if (!selected && findRuleRowOption(options, current)) selected = current;
            currentState.slug = selected;
            out += '<div class="form-group"><select class="form-control input-sm" data-role="row">'
                + '<option value="">' + escapeHtml(translate("— Chọn dòng —")) + "</option>";
            options.forEach(function (option) {
                out += '<option value="' + escapeHtml(option.slug) + '"'
                    + (option.slug === selected ? " selected" : "") + ">"
                    + escapeHtml(option.label) + "</option>";
            });
            out += "</select></div>";
            if (!selected) {
                out += '<div style="font-size:11px;color:#64748b;">'
                    + escapeHtml(translate("Dòng này chưa chọn nguồn — chọn một dòng rồi bấm Dùng dòng này."))
                    + "</div>";
            } else {
                var chosen = findRuleRowOption(options, selected);
                if (chosen && !isBlank(chosen.sample_value)) {
                    out += '<div style="font-size:11px;color:#64748b;">'
                        + escapeHtml(translate("Giá trị hiện tại") + ": "
                            + formatNumberRaw(chosen.sample_value))
                        + "</div>";
                }
            }
            out += '<div style="margin-top:8px;"><button type="button" '
                + 'class="btn btn-sm btn-primary" data-role="run"'
                + (selected ? "" : " disabled") + ">"
                + escapeHtml(translate("Dùng dòng này")) + "</button></div>";
            return out;
        }

        function loadInputVariables() {
            if (state.variables.length) return;
            fetchInputVariables().then(function (rows) {
                state.variables = rows || [];
                paint(state);
            });
        }

        // Chưa có metadata quy tắc ⇒ đọc theo mã trước rồi mới vẽ.
        if (!rule) {
            var code = trim(opts.rule_code);
            if (!code && row && row.doc) code = trim(row.doc.item_rule);
            $w.html('<div style="font-size:12px;color:#94a3b8;">'
                + escapeHtml(translate("Đang đọc thông tin quy tắc…")) + "</div>");
            fetchRuleForCode(code).then(function (meta) {
                rule = meta;
                if (rule) {
                    paint(state);
                    loadInputVariables();
                    return;
                }
                // Không đọc được ⇒ hỏi trạng thái thật (đã xoá / chưa kiểm
                // tra được) để hộp thoại không im lặng vô cớ.
                return fetchRuleState(code).then(function (info) {
                    state.rule_state = info && info.state ? info.state : "unknown";
                    paint(state);
                });
            });
            return;
        }
        paint(state);
        loadInputVariables();
    }

    // ── 11. Xuất API ──────────────────────────────────────────────────
    var api = {
        // thuần (test bằng Node)
        buildSnippet: buildSnippet,
        buildPresetSnippet: buildPresetSnippet,
        parseLookupSnippet: parseLookupSnippet,
        parseFormulaSnippet: parseFormulaSnippet,
        describeFormula: describeFormula,
        ruleFormRoute: ruleFormRoute,
        presetDefinitions: presetDefinitions,
        filterNumberRules: filterNumberRules,
        buildInputOptions: buildInputOptions,
        buildVariableOptions: buildVariableOptions,
        buildRuleInputOptions: buildRuleInputOptions,
        rowDisplayName: rowDisplayName,
        rowIndexBySlug: rowIndexBySlug,
        variableMissingNoticeText: variableMissingNoticeText,
        variableMissingNoticeHtml: variableMissingNoticeHtml,
        ruleStateNoticeText: ruleStateNoticeText,
        // Chặng 3 — quy tắc tự khai "tra theo cái gì"
        ruleInputVariable: ruleInputVariable,
        ruleInputScope: ruleInputScope,
        hasDeclaredRuleInput: hasDeclaredRuleInput,
        ruleInputResolvableNames: ruleInputResolvableNames,
        isRuleInputResolvable: isRuleInputResolvable,
        ruleInputVariableComputed: ruleInputVariableComputed,
        ruleRowComputedNote: ruleRowComputedNote,
        ruleInsertPlan: ruleInsertPlan,
        ruleGlobalSentenceHtml: ruleGlobalSentenceHtml,
        ruleRowSentenceHtml: ruleRowSentenceHtml,
        ruleCurrentValueHtml: ruleCurrentValueHtml,
        // Chặng 4 — điều kiện tra ngay tại chỗ chọn quy tắc
        ruleConditionsUnreadableText: ruleConditionsUnreadableText,
        ruleConditionLines: ruleConditionLines,
        ruleConditionSummary: ruleConditionSummary,
        ruleConditionPreviewHtml: ruleConditionPreviewHtml,
        ruleConditionItemCodes: ruleConditionItemCodes,
        cachedItemNames: cachedItemNames,
        rowVariableValue: rowVariableValue,
        rowSupportsVariable: rowSupportsVariable,
        ruleRowOptionExpr: ruleRowOptionExpr,
        buildRuleRowOptions: buildRuleRowOptions,
        findRuleRowOption: findRuleRowOption,
        buildRuleInsertOptions: buildRuleInsertOptions,
        validateRuleInput: validateRuleInput,
        isRuleInputReadable: isRuleInputReadable,
        isGlassRow: isGlassRow,
        parseItemExpr: parseItemExpr,
        findRowBySlug: findRowBySlug,
        findEquivalentOption: findEquivalentOption,
        resolveItemValue: resolveItemValue,
        isRuleActive: isRuleActive,
        normalizeRule: normalizeRule,
        findRule: findRule,
        ruleInputLabel: ruleInputLabel,
        readableInputLabel: readableInputLabel,
        ruleOutputLabel: ruleOutputLabel,
        ruleSummary: ruleSummary,
        // Nhãn tiếng Việt cho enum (form + danh sách dùng CHUNG một bản)
        ruleTypeOptions: ruleTypeOptions,
        ruleResultTypeOptions: ruleResultTypeOptions,
        ruleTypeLabel: ruleTypeLabel,
        ruleResultTypeLabel: ruleResultTypeLabel,
        resultText: resultText,
        matchText: matchText,
        samplePreviewText: samplePreviewText,
        escapeHtml: escapeHtml,
        rangeToCellText: rangeToCellText,
        extractServerMessage: extractServerMessage,
        isPreviewError: isPreviewError,
        // Desk (không gọi trong test)
        fetchNumberRules: fetchNumberRules,
        fetchRuleMeta: fetchRuleMeta,
        fetchRuleForCode: fetchRuleForCode,
        fetchRuleState: fetchRuleState,
        fetchRuleConditionsDoc: fetchRuleConditionsDoc,
        fetchItemNames: fetchItemNames,
        fetchInputVariables: fetchInputVariables,
        cachedInputVariables: cachedInputVariables,
        fetchOptionSample: fetchOptionSample,
        fetchVariableSample: fetchVariableSample,
        callPreviewRule: callPreviewRule,
        insertFormula: insertFormula,
        rowFieldWrapper: rowFieldWrapper,
        openInsert: openInsert,
        openRulePreview: openRulePreview,
        openInputPicker: openInputPicker,
        openRuleRowPicker: openRuleRowPicker,
    };

    if (root) root.AlumGlassRuleHelper = api;
    if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window
    : (typeof globalThis !== "undefined" ? globalThis : this));
