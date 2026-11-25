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
// HỢP ĐỒNG API THỬ TRA (server do DEV1 làm — docs §3.2):
//   alumglass.api.preview_rule(rule_code, input_value) ->
//     { success, rule_name, rule_description, input_label, input_unit,
//       output_label, is_active, matched:{kind,from,to,key}|null,
//       result:{value}|{item_code,item_name}|null,
//       rows:[{from,to,key,result_text,is_match}], message }
//   Lỗi gọi API KHÔNG bị nuốt thành "im lặng": helper trả một object đánh dấu
//   `__preview_error` kèm NGUYÊN VĂN câu `_server_messages` để hộp thoại hiện
//   đúng lý do (rỗng mới dùng câu trung tính + nút Thử lại).
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

    /** Nhãn "dữ liệu đem tra" của quy tắc (kèm đơn vị nếu có). */
    function ruleInputLabel(rule) {
        if (!rule) return translate("giá trị đem tra");
        var label = trim(rule.input_label);
        var unit = trim(rule.input_unit);
        if (!label) return translate("giá trị đem tra");
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

    // ── 3. Dựng chuỗi công thức ────────────────────────────────────────
    /**
     * `lookup_rule('CODE', input)` — có `multiplier` thì thêm ` * multiplier`.
     * Thiếu code hoặc input ⇒ null (caller tự hiện hướng dẫn).
     */
    function buildSnippet(opts) {
        opts = opts || {};
        var code = trim(opts.code);
        var input = trim(opts.input);
        if (!code || !input) return null;
        var core = "lookup_rule('" + escapeSingleQuote(code) + "', " + input + ")";
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
     * Đọc 1 chuỗi `lookup_rule('MÃ', input) [* multiplier]` → {code, input,
     * multiplier}; không đúng dạng ⇒ null. Tự bỏ phần thoát nháy của mã.
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
     * Trả {preset, fixed, rule, input, multiplier, raw}. `preset` rỗng nghĩa
     * là công thức chưa thuộc dạng dựng sẵn nào (vẫn hiện "Ô đang có: …").
     */
    function parseFormulaSnippet(value) {
        var raw = trim(value);
        var out = {
            preset: "", fixed: "", rule: "", input: "", multiplier: "", raw: raw,
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
        }
        return out;
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

        items.forEach(function (row) {
            if (!row || isBlank(row.slug)) return;
            var lineName = trim(row.line_name) || trim(row.slug);
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
        (Array.isArray(items) ? items : []).forEach(function (row) {
            if (!row || isBlank(row.slug) || !isGlassRow(row)) return;
            var lineName = trim(row.line_name) || trim(row.slug);

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
            "rule_type", "result_type"];
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

    // Alias độ dày: dữ liệu cũ ghi `glass_thick`, danh sách mời dùng tên
    // chuẩn `total_thick_mm`. So khớp phải coi 2 tên là MỘT, nếu không công
    // thức cũ bị hiện thành ô "Nhập tay" kỹ thuật.
    var ITEM_FIELD_ALIASES = {
        glass_thick: "total_thick_mm",
        total_thick_mm: "glass_thick",
    };

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
                || trim(row.item_name) || trim(row.item_code);
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
     * Hộp thoại 4 bước KHÔNG-CẦN-CODE dùng cho ô công thức số lượng:
     *   1. Số lượng cố định   2. Theo số cánh   3. 2 × số cánh
     *   4. Tra quy tắc theo giá trị (chọn quy tắc → dữ liệu tra → nhân với)
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
            existing: existing,
            touched: false,
            preview_seq: 0,
        };

        function rebuildOptions() {
            state.options = buildInputOptions({
                items: items,
                variables: state.variables,
                item_fields: state.item_fields,
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
        }).catch(function (e) {
            console.warn("[AlumGlass] Không tải được danh sách quy tắc:", e);
            state.rules = [];
            state.rules_ready = true;
            state.rules_error = true;
            render();
        });

        function readDom() {
            var $fixed = $w.find('input[data-role="fixed"]');
            if ($fixed.length) state.fixed = String($fixed.val() || "");
            var $rule = $w.find('select[data-role="rule"]');
            if ($rule.length) state.rule = String($rule.val() || "");
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

        function currentSnippet() {
            if (state.preset === "fixed") {
                return buildPresetSnippet({ preset: "fixed", value: state.fixed });
            }
            if (state.preset === "panels") return buildPresetSnippet({ preset: "panels" });
            if (state.preset === "panels2") return buildPresetSnippet({ preset: "panels2" });
            if (state.preset === "rule") {
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
                html += '<div style="font-size:11px;color:#64748b;margin-top:3px;">'
                    + escapeHtml(ruleSummary(current));
                if (!isBlank(current.rule_description)) {
                    html += " — " + escapeHtml(current.rule_description);
                }
                html += "</div>";
            }
            html += '<div style="margin-top:4px;"><button type="button" '
                + 'class="btn btn-xs btn-default" data-role="new-rule">'
                + escapeHtml(translate("Tạo quy tắc mới")) + "</button></div>";
            return html + "</div>";
        }

        function inputSectionHtml() {
            var html = '<div class="form-group"><label class="control-label">'
                + escapeHtml(translate("Dữ liệu đem tra")) + "</label>"
                + '<select class="form-control input-sm" data-role="input">'
                + _optgroupsHtml(state.options, state.input,
                    translate("— Chọn dữ liệu —"))
                + '<option value="__manual__"' + (state.input === "__manual__" ? " selected" : "")
                + ">" + escapeHtml(translate("Nhập tay…")) + "</option></select>";
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

            var option = state.input === "__manual__" ? null : _optionByValue(state.options, state.input);
            var manual = state.input === "__manual__" ? trim(state.manual) : "";
            if (!option && !manual) return;
            // Nhập tay là BIỂU THỨC (vd `H_mm - 100`) ⇒ không có giá trị hiện
            // tại để thử, ⛔ gửi nguyên chuỗi biểu thức lên server.
            if (manual && toNumberOrNull(manual) === null) return;

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
    }

    // ── 9. Hộp thoại "Thử tra" ────────────────────────────────────────
    function _previewInputLabel(state) {
        var base = state.label
            || (state.resp && state.resp.input_label)
            || translate("Giá trị đem tra");
        var unit = state.unit || (state.resp && state.resp.input_unit) || "";
        if (unit && base.indexOf("(") === -1) return base + " (" + unit + ")";
        return base;
    }

    function _rowsTable(rows) {
        rows = Array.isArray(rows) ? rows : [];
        if (!rows.length) return "";
        var hasFrom = rows.some(function (r) { return r && r.from !== undefined && r.from !== null; });
        var hasTo = rows.some(function (r) { return r && r.to !== undefined && r.to !== null; });
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
            if (hasTo) cells += "<td>" + escapeHtml(formatNumberUi(row.to)) + "</td>";
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

    // ── 11. Xuất API ──────────────────────────────────────────────────
    var api = {
        // thuần (test bằng Node)
        buildSnippet: buildSnippet,
        buildPresetSnippet: buildPresetSnippet,
        parseLookupSnippet: parseLookupSnippet,
        parseFormulaSnippet: parseFormulaSnippet,
        presetDefinitions: presetDefinitions,
        filterNumberRules: filterNumberRules,
        buildInputOptions: buildInputOptions,
        buildVariableOptions: buildVariableOptions,
        buildRuleInputOptions: buildRuleInputOptions,
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
        ruleOutputLabel: ruleOutputLabel,
        ruleSummary: ruleSummary,
        resultText: resultText,
        matchText: matchText,
        samplePreviewText: samplePreviewText,
        escapeHtml: escapeHtml,
        extractServerMessage: extractServerMessage,
        isPreviewError: isPreviewError,
        // Desk (không gọi trong test)
        fetchNumberRules: fetchNumberRules,
        fetchRuleMeta: fetchRuleMeta,
        fetchRuleForCode: fetchRuleForCode,
        fetchOptionSample: fetchOptionSample,
        callPreviewRule: callPreviewRule,
        insertFormula: insertFormula,
        rowFieldWrapper: rowFieldWrapper,
        openInsert: openInsert,
        openRulePreview: openRulePreview,
        openInputPicker: openInputPicker,
    };

    if (root) root.AlumGlassRuleHelper = api;
    if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window
    : (typeof globalThis !== "undefined" ? globalThis : this));
