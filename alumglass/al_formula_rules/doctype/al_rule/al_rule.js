// AL Rule — Client Script
// Module: AL Formula Rules
//
// ═══════════════════════════════════════════════════════════════════════════
// FORM ĐỌC LIỀN MẠCH (bố cục JSON: 1. Quy tắc → 2. Tra theo dữ liệu nào →
// 3. Điều kiện tra → 4. Quản trị; thiết kế
// docs/design/tra-cuu-quy-tac-de-hieu.md §3.1 + §7.3)
//
// NĂM THỨ Ở ĐÂY:
//   1. Hiện `rule_description` + câu "Quy tắc này tra theo <nhãn>" ngay dưới
//      tiêu đề — quản trị đọc là biết quy tắc dùng để làm gì, tra theo dữ liệu
//      gì, không phải suy từ mã + các con số.
//   2. Chọn `input_variable` (Link `AL Variable Library`) mà `input_label`
//      trống ⇒ tự điền nhãn của biến (`var_label`), vẫn sửa tay được.
//   3. Ô "Tra theo" CHỈ mời biến engine đọc được ở bước chọn mã: lọc theo
//      `resolvable` của `alumglass.api.get_rule_input_variables()` (gọi 1 lần,
//      cache theo form; API lỗi ⇒ giữ danh sách đầy đủ). Bản ghi cũ trỏ biến
//      không dùng được ⇒ cảnh báo ngay dưới ô, ⛔ tự đổi giá trị.
//   4. Bảng điều kiện NẰM NGAY DƯỚI phần "Tra theo": nhãn cột đổi theo dữ liệu
//      đang tra ("Từ (Độ dày kính)", "Đến (Độ dày kính) — bỏ trống = trở lên"),
//      cột kết quả đổi theo `output_label`, cột không dùng bị ẩn theo
//      `result_type`. Ngay trên mỗi lưới có nút thêm nhanh, cuối lưới có ô
//      "thử với giá trị" — không phải mở hộp thoại mới đối chiếu được.
//   5. Nút "Thử tra" (đầy đủ, mở hộp thoại) + ô cảnh báo `input_help_html`:
//      thống kê điều kiện, khe hở, khoảng chồng lấn, giá trị tra bị lặp.
//      ⛔ KHÔNG chặn lưu — chỉ cảnh báo để người khai thấy ngay.
//
// CHỊU ĐƯỢC SITE CHƯA MIGRATE: các field mô tả (`rule_description`,
// `input_label`, `input_unit`, `output_label`), `input_variable` và
// `input_help_html` có thể CHƯA có trong DB; lưới có thể chưa có API đổi nhãn.
// Thiếu gì ⇒ bỏ đúng phần đó, KHÔNG lỗi, KHÔNG chặn nút Thử tra.
//
// HÀM THUẦN (test Node: alumglass/tests/js/test_al_rule_conditions.js):
//   findGaps · findOverlaps · summarizeThresholds · conditionRecap ·
//   columnLabels · findDuplicateKeys · ruleInputDisplayLabel ·
//   ruleInputSentenceLabel · lastRangeOpen
// Xuất qua `window.AlumGlassRuleConditions`; handler Frappe chỉ gắn khi có
// `frappe.ui.form.on` ⇒ nạp được bằng `require()` trong Node.
// ═══════════════════════════════════════════════════════════════════════════

(function () {
    "use strict";

    var root = (typeof window !== "undefined") ? window
        : (typeof globalThis !== "undefined" ? globalThis : this);

    var THRESHOLD_TABLE = "threshold_rows";
    var LOOKUP_TABLE = "lookup_rows";
    var WARN_COLOR = "#b45309";
    var MUTED_COLOR = "#6b7280";
    var DASH = "–";
    var ARROW = " → ";

    // ── Tiện ích chung ────────────────────────────────────────────────────
    /** Dịch chuỗi khi có `__` của Desk; test Node không có thì giữ nguyên. */
    function _t(text) {
        return (typeof __ === "function") ? __(text) : String(text);
    }

    function _esc(text) {
        var value = (text === null || text === undefined) ? "" : String(text);
        if (typeof frappe !== "undefined" && frappe.utils
                && typeof frappe.utils.escape_html === "function") {
            return frappe.utils.escape_html(value);
        }
        return value.replace(/&/g, "&amp;").replace(/</g, "&lt;")
            .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    /** Ép số an toàn: rỗng/không phải số ⇒ `null` (KHÔNG phải 0). */
    function _toNumber(value) {
        if (value === null || value === undefined) return null;
        if (typeof value === "number") return isFinite(value) ? value : null;
        var text = String(value).trim();
        if (!text) return null;
        var num = Number(text.replace(/\s/g, "").replace(",", "."));
        return isFinite(num) ? num : null;
    }

    /** Số gọn cho người đọc: 10.0 → "10", 10.5 → "10,5". */
    function formatNumber(value) {
        var num = _toNumber(value);
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

    function _withUnit(text, unit) {
        var label = String(text === null || text === undefined ? "" : text).trim();
        var unitText = String(unit === null || unit === undefined ? "" : unit).trim();
        if (!label) return "";
        if (!unitText || label.indexOf("(") !== -1) return label;
        return label + " (" + unitText + ")";
    }

    /** Chuẩn hoá để SO SÁNH nhãn với tên biến: bỏ khác biệt hoa/thường + khoảng trắng. */
    function _compareKey(text) {
        return String(text === null || text === undefined ? "" : text)
            .replace(/\s+/g, " ").trim().toLowerCase();
    }

    /**
     * Nhãn "dữ liệu quy tắc đọc" cho MỌI câu người dùng đọc — ⛔ mã biến.
     *
     * Nhãn rỗng, hoặc nhãn TRÙNG ĐÚNG tên biến (bỏ qua hoa/thường và khoảng
     * trắng thừa, vd `" Total_Thick_MM "` với biến `total_thick_mm`) ⇒
     * "dữ liệu quy tắc đọc". Đó là trường hợp quản trị chưa đặt nhãn và hệ
     * thống (bản cũ) đã lấy chính tên biến làm nhãn — người dùng không đọc
     * được `total_thick_mm`. Nhãn người dùng thật ⇒ giữ nguyên.
     *
     * MỘT BẢN: `rule_helper.js` (`readableInputLabel`) đã nạp ⇒ uỷ quyền để
     * form và hộp thoại/danh sách ⛔ lệch nhau; chưa nạp (test Node thuần /
     * trang chưa tải helper) ⇒ bản dự phòng cùng thuật toán ngay dưới.
     *
     * HÀM THUẦN — test Node: alumglass/tests/js/test_al_rule_conditions.js
     */
    function ruleInputDisplayLabel(inputLabel, inputVariable) {
        var helper = _al_rule_helper();
        if (helper && typeof helper.readableInputLabel === "function") {
            return helper.readableInputLabel(inputLabel, inputVariable);
        }
        var label = String(inputLabel === null || inputLabel === undefined
            ? "" : inputLabel).trim();
        var variable = String(inputVariable === null || inputVariable === undefined
            ? "" : inputVariable).trim();
        if (!label) return _t("dữ liệu quy tắc đọc");
        if (variable && _compareKey(label) === _compareKey(variable)) {
            return _t("dữ liệu quy tắc đọc");
        }
        return label;
    }

    /**
     * Câu "tra theo" của form — "" khi quy tắc CHƯA khai cả nhãn lẫn biến
     * (caller tự nói "chưa khai"), ngược lại dùng nhãn người đọc. Tách riêng
     * để ⛔ bao giờ rơi về mã biến ở bất kỳ chỗ nào của form.
     */
    function ruleInputSentenceLabel(inputLabel, inputVariable) {
        var label = String(inputLabel === null || inputLabel === undefined
            ? "" : inputLabel).trim();
        var variable = String(inputVariable === null || inputVariable === undefined
            ? "" : inputVariable).trim();
        if (!label && !variable) return "";
        return ruleInputDisplayLabel(label, variable);
    }

    // ── HÀM THUẦN: đọc danh sách dòng điều kiện ───────────────────────────
    /**
     * Chuẩn hoá dòng ngưỡng: `{from, to}` với số thật.
     * `from` thiếu ⇒ bỏ dòng (không xếp được vào trục số).
     * `to` thiếu ⇒ `null` = phủ tới TRÊN CÙNG (theo quy ước nhãn
     * "Đến (bỏ trống = trở lên)").
     */
    function _thresholdRanges(rows) {
        var ranges = [];
        (Array.isArray(rows) ? rows : []).forEach(function (row) {
            if (!row) return;
            var from = _toNumber(row.from_value);
            if (from === null) return;
            ranges.push({ from: from, to: _toNumber(row.to_value) });
        });
        ranges.sort(function (a, b) { return a.from - b.from; });
        return ranges;
    }

    /**
     * Dải ngưỡng CUỐI (xếp theo `from` tăng dần) đang MỞ — `to` trống nghĩa là
     * "trở lên". Lúc đó dòng thêm mới sẽ rơi SAU dải mở ⇒ server chặn lưu
     * ("chỉ dải CUỐI được để trống") ⇒ form phải khoá nút thêm dòng và nói
     * cách sửa, ⛔ để người dùng bấm rồi mới biết lỗi.
     *
     * Bảng rỗng / mọi dòng thiếu `from` ⇒ false (chưa có dải nào để khoá).
     * HÀM THUẦN — test Node: alumglass/tests/js/test_al_rule_conditions.js
     */
    function lastRangeOpen(rows) {
        var ranges = _thresholdRanges(rows);
        if (!ranges.length) return false;
        return ranges[ranges.length - 1].to === null;
    }

    function _reachText(from, to, unit) {
        var suffix = String(unit || "").trim() ? " " + String(unit).trim() : "";
        if (to === null || to === undefined) {
            return formatNumber(from) + suffix + " " + _t("trở lên");
        }
        return formatNumber(from) + DASH + formatNumber(to) + suffix;
    }

    /**
     * Khe hở: vùng số KHÔNG dòng nào phủ.
     *
     * Quy ước nửa mở `[from, to)` ⇒ 0–10 và 10–20 LIỀN nhau (không trống);
     * ⛔ báo trống chỉ khi `to` dòng trước NHỎ HƠN `from` dòng sau.
     * Khoảng đầu > 0 ⇒ báo trống từ 0. `to` rỗng = trở lên ⇒ không trống
     * phía trên. Bảng rỗng ⇒ `[]` (câu "chưa có điều kiện" lo riêng).
     *
     * Trả `[{from, to}]`, `to` chỉ `null` khi khe mở tới trên cùng.
     */
    function findGaps(rows) {
        var ranges = _thresholdRanges(rows);
        if (!ranges.length) return [];
        var gaps = [];
        if (ranges[0].from > 0) {
            gaps.push({ from: 0, to: ranges[0].from });
        }
        var reach = ranges[0].to; // null = phủ tới trên cùng
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

    /**
     * Khoảng CHỒNG LẤN thật: 10–20 và 15–25 CÓ; 10–20 và 20–30 KHÔNG
     * (chạm biên là hợp lệ — dòng trên thắng). Trả `[{first, second}]`.
     */
    function findOverlaps(rows) {
        var ranges = _thresholdRanges(rows);
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
            if (furthest.to === null) return; // đã phủ tới trên cùng
            if (range.to === null || range.to > furthest.to) furthest = range;
        });
        return overlaps;
    }

    /**
     * Thống kê nhanh bảng ngưỡng: số điều kiện, đầu dưới, đầu trên, có phủ
     * tới trên cùng hay không, câu phạm vi ("0–30 mm", "20 mm trở lên").
     */
    function summarizeThresholds(rows, unit) {
        var ranges = _thresholdRanges(rows);
        var summary = {
            count: ranges.length,
            from: null,
            to: null,
            openEnded: false,
            rangeText: "",
        };
        ranges.forEach(function (range) {
            if (summary.from === null || range.from < summary.from) {
                summary.from = range.from;
            }
            if (range.to === null) summary.openEnded = true;
            else if (summary.to === null || range.to > summary.to) {
                summary.to = range.to;
            }
        });
        if (!ranges.length) return summary;
        if (summary.openEnded) {
            summary.rangeText = _reachText(summary.from, null, unit);
        } else if (summary.to !== null) {
            summary.rangeText = _reachText(summary.from, summary.to, unit);
        } else {
            summary.rangeText = formatNumber(summary.from)
                + (String(unit || "").trim() ? " " + String(unit).trim() : "");
        }
        return summary;
    }

    /** Một dòng đọc thành câu: "0–10 mm → Nẹp 10", "LOWE → Nẹp A". */
    function _recapWhen(row, unit) {
        if (row.key_field !== undefined) {
            var key = String(row.key_field === null ? "" : row.key_field).trim();
            return key; // dòng tra bảng: chưa điền khoá ⇒ bỏ
        }
        var from = _toNumber(row.from_value);
        var to = _toNumber(row.to_value);
        var suffix = String(unit || "").trim() ? " " + String(unit).trim() : "";
        if (from !== null && to !== null) {
            return _reachText(from, to, unit);
        }
        // Chỉ có "Từ" ⇒ phủ từ đó tới trên cùng; câu gọn "≥ 20 mm". Dòng
        // thiếu "Từ" là dòng đang khai dở ⇒ bỏ (cùng quy ước với findGaps).
        if (from !== null) return "≥ " + formatNumber(from) + suffix;
        return "";
    }

    /** Kết quả một dòng: ITEM ưu tiên tên vật tư, thiếu mới hiện mã; NUMBER. */
    function _recapResult(row, resultType) {
        if (String(resultType || "").toUpperCase() === "ITEM") {
            var name = String(row.result_item_name === null
                || row.result_item_name === undefined ? "" : row.result_item_name).trim();
            if (name) return name;
            return String(row.result_item === null || row.result_item === undefined
                ? "" : row.result_item).trim();
        }
        return formatNumber(row.result_value);
    }

    /**
     * Đọc nhanh danh sách điều kiện thành câu, mỗi dòng một câu:
     * `["0–10 mm → Nẹp 10", "≥ 20 mm → Nẹp 30"]`.
     *
     * `opts.resultType` quyết định cột kết quả; `opts.unit` ghép vào phạm vi;
     * `opts.resultLabel` chỉ dùng khi cần gọi tên kết quả chưa khai.
     */
    function conditionRecap(rows, opts) {
        opts = opts || {};
        var unit = String(opts.unit === null || opts.unit === undefined
            ? "" : opts.unit).trim();
        var resultType = String(opts.resultType || "").trim().toUpperCase();
        var resultLabel = String(opts.resultLabel === null
            || opts.resultLabel === undefined ? "" : opts.resultLabel).trim();
        var lines = [];
        (Array.isArray(rows) ? rows : []).forEach(function (row) {
            if (!row) return;
            var when = _recapWhen(row, unit);
            if (!when) return;
            var result = _recapResult(row, resultType);
            if (!result) {
                result = resultLabel
                    ? _t("chưa có") + " " + resultLabel.toLowerCase()
                    : _t("chưa có kết quả");
            }
            lines.push(when + ARROW + result);
        });
        return lines;
    }

    /** Giá trị cần tra bị lặp (chỉ dòng tra bảng) — mỗi giá trị một lần. */
    function findDuplicateKeys(rows) {
        var seen = {};
        var duplicates = [];
        (Array.isArray(rows) ? rows : []).forEach(function (row) {
            var key = String(row && row.key_field !== null && row.key_field !== undefined
                ? row.key_field : "").trim();
            if (!key) return;
            if (seen[key]) {
                if (duplicates.indexOf(key) === -1) duplicates.push(key);
                return;
            }
            seen[key] = true;
        });
        return duplicates;
    }

    /**
     * Nhãn cột lưới điều kiện theo dữ liệu đang tra.
     *
     * `inputVariable` (tham số 5) = tên biến "Tra theo" — CẦN để phát hiện dữ
     * liệu CŨ đã lưu `input_label = total_thick_mm`: nhãn trùng tên biến phải
     * nói "dữ liệu quy tắc đọc", ⛔ nhét mã biến vào tiêu đề cột.
     *
     * Trả `{labels, hidden}`:
     *   labels — `fieldname → nhãn người đọc`
     *   hidden — `fieldname → true` khi cột kết quả KHÔNG dùng theo `result_type`
     *            (ITEM ẩn cột số, NUMBER ẩn cột mã vật tư).
     */
    function columnLabels(inputLabel, outputLabel, resultType, kind, inputVariable) {
        // `ruleInputSentenceLabel` trả "" khi quy tắc chưa khai gì ⇒ nhãn cột
        // gọn "Từ"/"Đến"; có khai ⇒ nhãn người đọc (⛔ mã biến).
        var input = ruleInputSentenceLabel(inputLabel, inputVariable);
        var output = String(outputLabel === null || outputLabel === undefined
            ? "" : outputLabel).trim();
        var isItem = String(resultType || "").toUpperCase() === "ITEM";
        var isLookup = String(kind || "").toUpperCase() === "LOOKUP";
        var resultLabel = _t("Kết quả:") + " "
            + (output || (isItem ? _t("mã vật tư") : _t("số")));

        var labels = {};
        if (isLookup) {
            labels.key_field = input ? _t("Giá trị") + " (" + input + ")" : _t("Giá trị");
        } else {
            labels.from_value = input ? _t("Từ") + " (" + input + ")" : _t("Từ");
            labels.to_value = (input ? _t("Đến") + " (" + input + ")" : _t("Đến"))
                + " " + DASH + " " + _t("bỏ trống = trở lên");
        }
        labels.result_value = resultLabel;
        labels.result_item = resultLabel;
        return {
            labels: labels,
            hidden: { result_value: isItem, result_item: !isItem },
        };
    }

    var AlumGlassRuleConditions = {
        findGaps: findGaps,
        findOverlaps: findOverlaps,
        summarizeThresholds: summarizeThresholds,
        conditionRecap: conditionRecap,
        columnLabels: columnLabels,
        findDuplicateKeys: findDuplicateKeys,
        formatNumber: formatNumber,
        // Nhãn người đọc cho "tra theo cái gì" — ⛔ mã biến (UX1 vòng 3).
        ruleInputDisplayLabel: ruleInputDisplayLabel,
        ruleInputSentenceLabel: ruleInputSentenceLabel,
        // Dải ngưỡng cuối đang MỞ (`Đến` trống = trở lên) — khoá nút thêm dòng.
        lastRangeOpen: lastRangeOpen,
        THRESHOLD_TABLE: THRESHOLD_TABLE,
        LOOKUP_TABLE: LOOKUP_TABLE,
    };
    root.AlumGlassRuleConditions = AlumGlassRuleConditions;
    if (typeof module !== "undefined" && module.exports) {
        module.exports = AlumGlassRuleConditions;
    }

    // ══════════════════════════════════════════════════════════════════════
    // PHẦN GIAO DIỆN — chỉ chạy trên Desk
    // ══════════════════════════════════════════════════════════════════════
    function _al_rule_helper() {
        return (typeof window !== "undefined" && window.AlumGlassRuleHelper) || null;
    }

    function _al_rule_grid(frm, table) {
        var field = frm && frm.fields_dict && frm.fields_dict[table];
        return (field && field.grid) ? field.grid : null;
    }

    function _al_rule_rows(frm, table) {
        var doc = (frm && frm.doc) || {};
        var rows = doc[table];
        return Array.isArray(rows) ? rows : [];
    }

    /** Đổi nhãn cột đang hiện; lưới cũ không có API ⇒ sửa ô tiêu đề trực tiếp. */
    function _al_rule_apply_label(grid, fieldname, label) {
        if (!label) return;
        if (typeof grid.update_docfield_property === "function") {
            try {
                grid.update_docfield_property(fieldname, "label", label);
                return;
            } catch (e) {
                // Lưới/site cũ chưa có field này ⇒ rơi xuống lối sửa tiêu đề.
            }
        }
        if (grid.docfields && grid.docfields.forEach) {
            grid.docfields.forEach(function (df) {
                if (df && df.fieldname === fieldname) df.label = label;
            });
        }
        var $parent = grid.parent;
        if ($parent && $parent.find) {
            var $cell = $parent.find(
                '.grid-heading-row [data-fieldname="' + fieldname + '"] .static-area');
            if ($cell.length) $cell.text(label);
        }
    }

    /**
     * Ẩn ô TIÊU ĐỀ của cột điều kiện.
     *
     * `grid.set_column_disp` chỉ ẩn ô DỮ LIỆU; lõi v14 dựng lại `header_row`
     * mỗi lượt `grid.refresh()` và `GridRow.make_column` KHÔNG đọc `df.hidden`
     * ⇒ tiêu đề vẫn nằm lại (cột rỗng nhưng vẫn thấy). Gắn ĐÚNG MỘT lần vào
     * grid: sau mỗi lượt dựng header, ẩn lại các cột đang cần ẩn.
     */
    function _al_rule_toggle_header_cell(grid, fieldname, hidden) {
        try {
            var header = grid.header_row && grid.header_row.columns
                && grid.header_row.columns[fieldname];
            if (header && typeof header.toggle === "function") header.toggle(!hidden);
        } catch (e) {
            // site cũ / header chưa dựng ⇒ thôi
        }
    }

    function _al_rule_bind_header_hidden(grid) {
        if (!grid || grid.__al_header_bound
                || typeof grid.make_head !== "function") return;
        grid.__al_header_bound = true;
        var make_head = grid.make_head.bind(grid);
        grid.make_head = function () {
            var out = make_head();
            var states = grid.__al_hidden_cols || {};
            Object.keys(states).forEach(function (fieldname) {
                _al_rule_toggle_header_cell(grid, fieldname, states[fieldname]);
            });
            return out;
        };
    }

    /**
     * Ẩn/hiện cột kết quả theo loại kết quả.
     *
     * ⚠ Frappe v14: `grid.toggle_display()` chỉ đổi `hidden` trên docfield rồi
     * `debounced_refresh()`, nhưng `Grid.setup_visible_columns()` RETURN SỚM khi
     * `visible_columns` đã dựng, và `GridRow` không đọc `df.hidden` ⇒ cột KHÔNG
     * mất. `grid.set_column_disp(fieldname, show)` mới gọi
     * `set_editable_grid_column_disp` (ẩn/hiện từng ô của các dòng đã dựng) rồi
     * refresh — đúng đường của lõi (grid.js:695). Ô TIÊU ĐỀ phải ẩn thêm bằng
     * `_al_rule_bind_header_hidden` (lõi dựng lại header, ⛔ đọc `df.hidden`).
     *
     * Lưới/site cũ không có hàm ⇒ rơi về `toggle_display`/`update_docfield_property`
     * như trước (không lỗi, chỉ là có thể không ẩn được).
     */
    function _al_rule_apply_hidden(grid, fieldname, hidden) {
        if (!grid) return;
        // Nhớ trạng thái mong muốn để mỗi lượt dựng lại header vẫn ẩn đúng cột.
        grid.__al_hidden_cols = grid.__al_hidden_cols || {};
        grid.__al_hidden_cols[fieldname] = !!hidden;
        _al_rule_bind_header_hidden(grid);
        _al_rule_toggle_header_cell(grid, fieldname, !!hidden);

        if (typeof grid.set_column_disp === "function") {
            // Đã đúng trạng thái ⇒ ⛔ gọi lại: `set_column_disp` kết thúc bằng
            // `grid.refresh()`, gọi mỗi lượt gõ phím sẽ dựng lại cả lưới.
            if (typeof grid.get_docfield === "function") {
                try {
                    var df = grid.get_docfield(fieldname);
                    if (df && !!df.hidden === !!hidden) return;
                } catch (e) {
                    // chưa đọc được docfield ⇒ cứ đặt
                }
            }
            try {
                // `set_column_disp` đã gọi refresh (debounced) bên trong.
                grid.set_column_disp(fieldname, !hidden);
                return;
            } catch (e) {
                // thiếu meta docfield / site cũ ⇒ thử đường cũ bên dưới
            }
        }
        if (typeof grid.toggle_display === "function") {
            try {
                grid.toggle_display(fieldname, !hidden);
                return;
            } catch (e) {
                // rơi xuống update_docfield_property
            }
        }
        if (typeof grid.update_docfield_property === "function") {
            try {
                grid.update_docfield_property(fieldname, "hidden", hidden ? 1 : 0);
            } catch (e) {
                // site cũ chưa có field ⇒ không sao, cột vẫn ẩn theo depends_on
            }
        }
    }

    /** Nhãn cột + cột kết quả của MỘT bảng điều kiện. */
    function _al_rule_sync_table_view(frm, table) {
        var grid = _al_rule_grid(frm, table);
        if (!grid) return;
        var doc = (frm && frm.doc) || {};
        var kind = table === THRESHOLD_TABLE ? "THRESHOLD" : "LOOKUP";
        var spec = columnLabels(doc.input_label, doc.output_label,
            doc.result_type, kind, doc.input_variable);
        Object.keys(spec.labels).forEach(function (fieldname) {
            _al_rule_apply_label(grid, fieldname, spec.labels[fieldname]);
        });
        Object.keys(spec.hidden).forEach(function (fieldname) {
            _al_rule_apply_hidden(grid, fieldname, spec.hidden[fieldname]);
        });
    }

    /**
     * Ô cảnh báo dưới mục "Tra theo": câu giải thích liền mạch + thống kê
     * điều kiện + khe hở / chồng lấn / giá trị lặp. ⛔ KHÔNG chặn lưu.
     */
    function _al_rule_render_input_help(frm) {
        var field = frm && frm.fields_dict && frm.fields_dict.input_help_html;
        var $wrapper = field && field.$wrapper;
        if (!$wrapper || !$wrapper.length) return;

        var doc = (frm && frm.doc) || {};
        var ruleType = String(doc.rule_type || "").trim().toUpperCase();
        // ⛔ rơi về MÃ BIẾN (`total_thick_mm`): chưa có nhãn / nhãn trùng tên
        // biến ⇒ "dữ liệu quy tắc đọc"; chưa khai gì ⇒ câu "chưa khai" bên dưới.
        var label = ruleInputSentenceLabel(doc.input_label, doc.input_variable);
        var unit = String(doc.input_unit || "").trim();
        var lines = [];

        if (label) {
            lines.push({ html: _t("Quy tắc này tra theo") + " <b>"
                + _esc(_withUnit(label, unit)) + "</b>. "
                + _t("Các điều kiện bên dưới đọc theo dữ liệu đó.") });
        } else {
            lines.push({ html: _t("Quy tắc chưa khai tra theo dữ liệu nào — chọn dữ liệu ở ô \"Tra theo\" để nhãn cột và câu hướng dẫn hiện đúng.") });
        }

        if (ruleType === "CONSTANT") {
            lines.push({ html: _t("Quy tắc hằng số luôn trả cùng một giá trị — không có điều kiện để tra.") });
            _al_rule_paint_help($wrapper, lines);
            return;
        }
        if (ruleType !== "THRESHOLD" && ruleType !== "LOOKUP") {
            _al_rule_paint_help($wrapper, lines);
            return;
        }

        if (ruleType === "THRESHOLD") {
            _al_rule_collect_threshold_help(frm, unit, lines);
        } else {
            _al_rule_collect_lookup_help(frm, lines);
        }
        _al_rule_paint_help($wrapper, lines);
    }

    function _al_rule_collect_threshold_help(frm, unit, lines) {
        var rows = _al_rule_rows(frm, THRESHOLD_TABLE);
        var summary = summarizeThresholds(rows, unit);
        if (!summary.count) {
            lines.push({
                html: _t("Chưa có điều kiện nào — quy tắc sẽ không trả được kết quả."),
                warn: true,
            });
            return;
        }
        lines.push({
            html: _t("Đang có") + " " + summary.count + " "
                + _t("điều kiện, phủ") + " " + _esc(summary.rangeText) + ".",
        });

        var gaps = findGaps(rows);
        gaps.slice(0, 3).forEach(function (gap) {
            lines.push({
                html: _t("Có khoảng trống") + " "
                    + _esc(_reachText(gap.from, gap.to, unit)) + ": "
                    + _t("giá trị rơi vào đây sẽ không tra được kết quả."),
                warn: true,
            });
        });
        if (gaps.length > 3) {
            lines.push({
                html: "… " + _t("và") + " " + (gaps.length - 3) + " "
                    + _t("khoảng trống khác."),
                warn: true,
            });
        }

        var overlaps = findOverlaps(rows);
        overlaps.slice(0, 3).forEach(function (pair) {
            lines.push({
                html: _t("Các khoảng") + " "
                    + _esc(_reachText(pair.first.from, pair.first.to, unit))
                    + " " + _t("và") + " "
                    + _esc(_reachText(pair.second.from, pair.second.to, unit))
                    + " " + _t("chồng lên nhau — máy sẽ chặn khi lưu; sửa để khoảng sau bắt đầu đúng bằng giá trị \"đến\" của khoảng trước."),
                warn: true,
            });
        });
        if (overlaps.length > 3) {
            lines.push({
                html: "… " + _t("và") + " " + (overlaps.length - 3) + " "
                    + _t("cặp khoảng chồng lấn khác."),
                warn: true,
            });
        }
    }

    function _al_rule_collect_lookup_help(frm, lines) {
        var rows = _al_rule_rows(frm, LOOKUP_TABLE);
        if (!rows.length) {
            lines.push({
                html: _t("Chưa có điều kiện nào — quy tắc sẽ không trả được kết quả."),
                warn: true,
            });
            return;
        }
        lines.push({
            html: _t("Đang có") + " " + rows.length + " " + _t("giá trị tra."),
        });
        findDuplicateKeys(rows).slice(0, 3).forEach(function (key) {
            lines.push({
                html: _t("Giá trị") + " \"" + _esc(key) + "\" "
                    + _t("bị lặp — dòng đầu tiên khớp sẽ thắng."),
                warn: true,
            });
        });
    }

    function _al_rule_paint_help($wrapper, lines) {
        var html = '<div style="font-size:12px;line-height:1.55;">';
        lines.forEach(function (line) {
            if (!line) return;
            var style = line.warn ? ' style="color:' + WARN_COLOR + ';"' : "";
            html += "<div" + style + ">" + line.html + "</div>";
        });
        html += "</div>";
        $wrapper.html(html);
    }

    // Câu giải thích khi nút thêm dòng bị KHOÁ vì dải cuối đang mở. Nói đúng
    // quy ước ("Đến" trống = trở lên) + việc cần làm, ⛔ chỉ khoá câm lặng.
    var QUICK_ADD_OPEN_RANGE_HINT =
        "Dải cuối đang để trống = trở lên; muốn thêm dải phía trên thì nhập \"Đến\" cho dải cuối trước.";

    /** Thêm dòng ngưỡng bị chặn khi dải CUỐI đang mở (`Đến` trống = trở lên). */
    function _al_rule_quick_add_blocked(frm, table) {
        return table === THRESHOLD_TABLE
            && lastRangeOpen(_al_rule_rows(frm, table));
    }

    /** Nút bị khoá thì tắt bấm + gắn `title` giải thích (site cũ: bỏ qua). */
    function _al_rule_paint_quick_add_button($btn, blocked, hint) {
        if (!$btn || typeof $btn.prop !== "function") return;
        try {
            $btn.prop("disabled", !!blocked);
            if (typeof $btn.attr === "function") {
                $btn.attr("title", blocked ? hint : "");
            }
        } catch (e) {
            // Nút của site cũ — vẫn còn lời nhắc dưới lưới.
        }
    }

    /** Lời nhắc dưới lưới: vì sao khoá + việc cần làm; hết khoá thì dọn đi. */
    function _al_rule_paint_quick_add_note(field, blocked, hint) {
        var $wrapper = field && field.$wrapper;
        if (!$wrapper || !$wrapper.length) return;
        var $note = $wrapper.find(".al-rule-quick-add-note");
        if (!blocked) {
            if ($note.length) $note.remove();
            return;
        }
        if (!$note.length) {
            $note = $('<div class="al-rule-quick-add-note small"></div>')
                .attr("style", "color:" + WARN_COLOR + ";margin:0 0 6px;")
                .prependTo($wrapper);
        }
        $note.text(hint);
    }

    /** Bấm khi đang khoá (hoặc gọi thẳng hàm thêm dòng) ⇒ nói cách sửa. */
    function _al_rule_quick_add_blocked_notice() {
        var text = _t(QUICK_ADD_OPEN_RANGE_HINT);
        if (typeof frappe !== "undefined" && typeof frappe.msgprint === "function") {
            frappe.msgprint({
                title: _t("Chưa thêm dải được"),
                message: text,
                indicator: "orange",
            });
            return;
        }
        if (typeof msgprint === "function") msgprint(text);
    }

    /**
     * Nút thêm nhanh ngay trên lưới. Ưu tiên nút của lưới (thanh công cụ
     * trên); lưới cũ không có API ⇒ chèn nút vào đầu vùng bảng.
     *
     * ⚠ Dải ngưỡng CUỐI đang MỞ (`Đến` trống = trở lên) ⇒ dòng thêm mới nằm
     * SAU dải mở nên server chặn lưu ("chỉ dải CUỐI được để trống"). Khi đó
     * KHOÁ nút + hiện câu giải thích, ⛔ để người dùng thêm rồi mới biết lỗi.
     */
    function _al_rule_attach_quick_add(frm, table) {
        var grid = _al_rule_grid(frm, table);
        if (!grid) return;
        var field = frm && frm.fields_dict && frm.fields_dict[table];
        var blocked = _al_rule_quick_add_blocked(frm, table);
        var hint = _t(QUICK_ADD_OPEN_RANGE_HINT);
        var label = (table === THRESHOLD_TABLE)
            ? _t("＋ Thêm ngưỡng") : _t("＋ Thêm giá trị");
        var onClick = function (event) {
            if (event && event.preventDefault) event.preventDefault();
            if (_al_rule_quick_add_blocked(frm, table)) {
                _al_rule_quick_add_blocked_notice();
                return;
            }
            _al_rule_quick_add_row(frm, table);
        };
        if (typeof grid.add_custom_button === "function") {
            try {
                var $btn = grid.add_custom_button(label, onClick, "top");
                _al_rule_paint_quick_add_button($btn, blocked, hint);
                _al_rule_paint_quick_add_note(field, blocked, hint);
                return;
            } catch (e) {
                // rơi xuống lối chèn tay
            }
        }
        var $wrapper = field && field.$wrapper;
        if (!$wrapper || !$wrapper.length) return;
        var $manual = $wrapper.find(".al-rule-quick-add");
        if (!$manual.length) {
            $manual = $('<button type="button" class="btn btn-xs btn-secondary al-rule-quick-add" style="margin-bottom:6px;"></button>')
                .text(label)
                .on("click", onClick)
                .prependTo($wrapper);
        }
        _al_rule_paint_quick_add_button($manual, blocked, hint);
        _al_rule_paint_quick_add_note(field, blocked, hint);
    }

    /** Đầu trên đang phủ của bảng ngưỡng (số lớn nhất trong cột "Đến"). */
    function _al_rule_threshold_reach(frm) {
        var reach = null;
        _al_rule_rows(frm, THRESHOLD_TABLE).forEach(function (row) {
            var to = _toNumber(row && row.to_value);
            if (to === null) return;
            if (reach === null || to > reach) reach = to;
        });
        return reach;
    }

    /**
     * Dải ngưỡng ĐỔI (sửa "Từ"/"Đến", thêm/xoá dòng) ⇒ vẽ lại câu cảnh báo +
     * cập nhật trạng thái KHOÁ nút "Thêm ngưỡng" theo dải CUỐI. Nhập xong
     * "Đến" cho dải cuối là nút mở lại NGAY, ⛔ phải lưu/tải lại mới dùng được.
     * Chỉ đổi trạng thái nút + câu nhắc, ⛔ refresh lưới khi đang gõ.
     */
    function _al_rule_on_threshold_range_change(frm) {
        _al_rule_render_input_help(frm);
        _al_rule_attach_quick_add(frm, THRESHOLD_TABLE);
    }

    function _al_rule_quick_add_row(frm, table) {
        if (!frm || typeof frm.add_child !== "function") return;
        // Chốt lần nữa ở đây: nút có thể bị bấm qua đường khác (test/script).
        if (_al_rule_quick_add_blocked(frm, table)) {
            _al_rule_quick_add_blocked_notice();
            return;
        }
        var values = {};
        if (table === THRESHOLD_TABLE) {
            // Nối khoảng liền mạch: dòng mới bắt đầu đúng chỗ dải đang phủ.
            var reach = _al_rule_threshold_reach(frm);
            if (reach !== null) values.from_value = reach;
        }
        try {
            frm.add_child(table, values);
            frm.refresh_field(table);
        } catch (e) {
            console.warn("[AlumGlass] Không thêm được dòng điều kiện:", e);
            return;
        }
        _al_rule_focus_last_row(frm, table);
        _al_rule_render_input_help(frm);
    }

    function _al_rule_focus_last_row(frm, table) {        var grid = _al_rule_grid(frm, table);
        if (!grid || !grid.grid_rows || !grid.grid_rows.length) return;
        var last = grid.grid_rows[grid.grid_rows.length - 1];
        try {
            if (last && typeof last.activate === "function") last.activate();
        } catch (e) {
            // lưới không cho sửa tại chỗ ⇒ chỉ đặt con trỏ
        }
        if (typeof grid.set_focus_on_row === "function") {
            grid.set_focus_on_row(grid.grid_rows.length - 1);
            return;
        }
        var field = frm.fields_dict[table];
        var $input = field && field.$wrapper
            ? field.$wrapper.find(".grid-body .grid-row:last input:visible").first()
            : null;
        if ($input && $input.length) $input.focus();
    }

    /**
     * Ô "thử với giá trị" ngay dưới lưới điều kiện — nhập rồi Enter/bấm nút,
     * ⛔ gọi API mỗi lần gõ. Kết quả hiện ngay dưới, kèm dòng điều kiện khớp.
     */
    function _al_rule_attach_try_panel(frm, table) {
        var field = frm && frm.fields_dict && frm.fields_dict[table];
        var $wrapper = field && field.$wrapper;
        if (!$wrapper || !$wrapper.length) return;

        var $panel = $wrapper.find(".al-rule-try");
        if (!$panel.length) {
            $panel = $('<div class="al-rule-try" style="margin:10px 0 6px;"></div>');
            $panel.append(
                '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">'
                + '<input type="text" class="form-control input-sm al-rule-try-input"'
                + ' style="max-width:220px;">'
                + '<button type="button" class="btn btn-xs btn-secondary al-rule-try-btn"></button>'
                + '<span class="al-rule-try-note small" style="color:' + MUTED_COLOR + ';"></span>'
                + "</div>"
                + '<div class="al-rule-try-result small" style="margin-top:6px;"></div>'
            );
            $panel.find(".al-rule-try-btn").text(_t("Thử ngay"));
            $panel.find(".al-rule-try-input").on("keydown.alrultry", function (event) {
                if (event && (event.which === 13 || event.key === "Enter")) {
                    if (event.preventDefault) event.preventDefault();
                    _al_rule_run_try(frm, table);
                }
            });
            $panel.find(".al-rule-try-btn").on("click.alrultry", function () {
                _al_rule_run_try(frm, table);
            });
            $wrapper.append($panel);
        }

        var doc = (frm && frm.doc) || {};
        var subject = _withUnit(
            ruleInputSentenceLabel(doc.input_label, doc.input_variable),
            doc.input_unit);
        $panel.find(".al-rule-try-input").attr("placeholder",
            subject ? _t("Thử với") + " " + subject : _t("Thử với một giá trị"));
        $panel.find(".al-rule-try-note").text(
            (typeof frm.is_dirty === "function" && frm.is_dirty())
                ? _t("Đang thử trên bản đã lưu — bấm Lưu trước để thử bản đang sửa.")
                : "");
    }

    function _al_rule_try_result(frm, table) {
        var field = frm && frm.fields_dict && frm.fields_dict[table];
        var $wrapper = field && field.$wrapper;
        return $wrapper ? $wrapper.find(".al-rule-try-result") : null;
    }

    function _al_rule_run_try(frm, table) {
        var field = frm && frm.fields_dict && frm.fields_dict[table];
        var $wrapper = field && field.$wrapper;
        if (!$wrapper || !$wrapper.length) return;
        var $panel = $wrapper.find(".al-rule-try");
        var $result = _al_rule_try_result(frm, table);
        var value = String($panel.find(".al-rule-try-input").val() || "").trim();

        if (frm.is_new && frm.is_new()) {
            $result.text(_t("Lưu quy tắc trước rồi thử."));
            return;
        }
        if (!value) {
            $result.text(_t("Nhập giá trị cần tra rồi bấm Thử ngay."));
            return;
        }
        var code = (frm.doc && (frm.doc.rule_code || frm.doc.name)) || "";
        $result.text(_t("Đang tra…"));
        _al_rule_call_preview(code, value).then(function (resp) {
            // Ô kết quả có thể đã bị dựng lại trong lúc chờ ⇒ tìm lại.
            var $fresh = _al_rule_try_result(frm, table);
            if ($fresh && $fresh.length) {
                _al_rule_show_try_result(frm, table, resp, $fresh);
            }
        });
    }

    function _al_rule_call_preview(code, value) {
        var helper = _al_rule_helper();
        if (helper && typeof helper.callPreviewRule === "function") {
            return Promise.resolve(helper.callPreviewRule(code, value));
        }
        return new Promise(function (resolve) {
            if (typeof frappe === "undefined" || typeof frappe.call !== "function") {
                return resolve(null);
            }
            frappe.call({
                method: "alumglass.api.preview_rule",
                args: { rule_code: code, input_value: value },
            }).then(function (r) {
                resolve((r && r.message && typeof r.message === "object")
                    ? r.message : null);
            }).catch(function (e) {
                resolve({ success: false, message: _al_rule_error_message(e) });
            });
        });
    }

    function _al_rule_error_message(error) {
        var raw = error && error._server_messages;
        if (raw) {
            try {
                var list = JSON.parse(raw);
                if (Array.isArray(list) && list.length) {
                    var first = list[0];
                    var parsed = (typeof first === "string") ? JSON.parse(first) : first;
                    if (parsed && parsed.message) return String(parsed.message);
                }
            } catch (e) {
                // để câu chung bên dưới
            }
        }
        return _t("Chưa tra được — kiểm tra lại giá trị và điều kiện.");
    }

    function _al_rule_show_try_result(frm, table, resp, $result) {
        if (!resp || typeof resp !== "object") {
            $result.text(_t("Chưa tra được — thử lại."));
            return;
        }
        var helper = _al_rule_helper();
        var text = (helper && typeof helper.resultText === "function")
            ? String(helper.resultText(resp) || "")
            : _al_rule_result_text(resp);
        var message = String(resp.message || "").trim();
        var html;

        if (resp.success === false || (!text && message)) {
            html = _esc(message || _t("Chưa tra được — thử lại."));
        } else if (text) {
            html = "<b>" + _esc(_t("Kết quả:")) + " " + _esc(text) + "</b>";
            var recap = _al_rule_matched_recap(frm, table, resp);
            if (recap) {
                html += " <span style='color:" + MUTED_COLOR + "'>"
                    + "· " + _esc(recap) + "</span>";
            }
        } else {
            html = _esc(message || _t("Không tra được — kiểm tra lại điều kiện."));
        }
        $result.html(html);
    }

    /** Dòng điều kiện khớp đọc thành câu, để đối chiếu với bảng ngay trên. */
    function _al_rule_matched_recap(frm, table, resp) {
        var matched = resp && resp.matched;
        if (!matched || typeof matched !== "object") return "";
        var rows = _al_rule_rows(frm, table);
        var found = null;
        rows.forEach(function (row) {
            if (found || !row) return;
            if (matched.key !== undefined && matched.key !== null) {
                if (String(row.key_field === null || row.key_field === undefined
                    ? "" : row.key_field).trim() === String(matched.key)) {
                    found = row;
                }
                return;
            }
            if (_toNumber(row.from_value) === _toNumber(matched.from)
                    && _toNumber(row.to_value) === _toNumber(matched.to)) {
                found = row;
            }
        });
        if (!found) return "";
        var doc = (frm && frm.doc) || {};
        var lines = conditionRecap([found], {
            unit: doc.input_unit,
            resultType: doc.result_type,
            resultLabel: doc.output_label,
        });
        return lines.length ? lines[0] : "";
    }

    function _al_rule_result_text(resp) {
        var result = resp && resp.result;
        if (!result || typeof result !== "object") return "";
        if (result.item_code) {
            return result.item_name
                ? String(result.item_code) + " (" + result.item_name + ")"
                : String(result.item_code);
        }
        if (result.value !== undefined && result.value !== null
                && result.value !== "") {
            return formatNumber(result.value);
        }
        return "";
    }

    /**
     * Vẽ lại toàn bộ phần phụ thuộc dữ liệu: nhãn cột lưới, cột kết quả,
     * ô cảnh báo, nút thêm nhanh, ô thử. Chỉ gọi khi thay đổi CẤU TRÚC
     * (không gọi mỗi lần sửa một ô trong lưới — tránh vẽ lại lưới liên tục).
     */
    function _al_rule_refresh_all(frm) {
        var doctype = (frm && (frm.doctype || (frm.doc && frm.doc.doctype))) || "";
        if (doctype !== "AL Rule") return;
        _al_rule_render_input_help(frm);
        _al_rule_sync_table_view(frm, THRESHOLD_TABLE);
        _al_rule_sync_table_view(frm, LOOKUP_TABLE);
        _al_rule_attach_quick_add(frm, THRESHOLD_TABLE);
        _al_rule_attach_quick_add(frm, LOOKUP_TABLE);
        _al_rule_attach_try_panel(frm, THRESHOLD_TABLE);
        _al_rule_attach_try_panel(frm, LOOKUP_TABLE);
    }

    // ── Nhãn TIẾNG VIỆT cho enum (`rule_type`, `result_type`) ─────────────
    // Giá trị LƯU trong DB vẫn là `CONSTANT`/`THRESHOLD`/`LOOKUP`,
    // `NUMBER`/`ITEM` — chỉ đổi NHÃN hiển thị. Frappe v14 Select nhận
    // `options` dạng mảng `{label, value}` (`parse_option` trong
    // controls/select.js) nên đặt thẳng được, ⛔ phải sinh field ảo.
    // Nhãn lấy từ `rule_helper.js` để DÙNG CHUNG với danh sách; thiếu helper
    // ⇒ bảng dự phòng dưới (cùng chuỗi, cùng thứ tự).
    var RULE_TYPE_OPTIONS_FALLBACK = [
        { value: "CONSTANT", label: "Hằng số" },
        { value: "THRESHOLD", label: "Tra theo dải" },
        { value: "LOOKUP", label: "Tra theo bảng" },
    ];
    var RESULT_TYPE_OPTIONS_FALLBACK = [
        { value: "NUMBER", label: "Số" },
        { value: "ITEM", label: "Mã vật tư" },
    ];

    function _al_rule_enum_options(fieldname) {
        var helper = _al_rule_helper();
        if (fieldname === "rule_type" && helper
                && typeof helper.ruleTypeOptions === "function") {
            return helper.ruleTypeOptions();
        }
        if (fieldname === "result_type" && helper
                && typeof helper.ruleResultTypeOptions === "function") {
            return helper.ruleResultTypeOptions();
        }
        var fallback = (fieldname === "rule_type")
            ? RULE_TYPE_OPTIONS_FALLBACK : RESULT_TYPE_OPTIONS_FALLBACK;
        return fallback.map(function (option) {
            return { value: option.value, label: _t(option.label) };
        });
    }

    /**
     * Đổi 2 ô Select của form sang nhãn tiếng Việt. Chạy trên `refresh`
     * (form đã có `fields_dict`); thiếu API / site cũ ⇒ giữ nguyên, ⛔ lỗi.
     */
    function _al_rule_localize_enums(frm) {
        if (!frm || typeof frm.set_df_property !== "function") return;
        ["rule_type", "result_type"].forEach(function (fieldname) {
            var field = frm.fields_dict && frm.fields_dict[fieldname];
            var df = field && field.df;
            if (!df || String(df.fieldtype || "") !== "Select") return;
            var options = _al_rule_enum_options(fieldname);
            // Đã đúng ⇒ ⛔ refresh lại mỗi lượt gõ phím ở ô khác.
            try {
                if (JSON.stringify(df.options) === JSON.stringify(options)) return;
            } catch (e) {
                // so sánh lỗi ⇒ cứ đặt lại
            }
            try {
                frm.set_df_property(fieldname, "options", options);
                if (typeof frm.refresh_field === "function") {
                    frm.refresh_field(fieldname);
                }
            } catch (e) {
                // Site cũ không nhận mảng options ⇒ giữ nhãn gốc.
            }
        });
    }

    // ── Ô "Tra theo": chỉ mời biến engine đọc được ở bước chọn mã ──────────
    // API `alumglass.api.get_rule_input_variables()` trả
    //   [{name, label, category, scope, resolvable}]
    // `resolvable = false` nghĩa là biến không có giá trị lúc chọn mã (vd `width`
    // của dòng phụ kiện) ⇒ chọn vào là quy tắc không bao giờ ra kết quả.
    // Gọi ĐÚNG MỘT lần cho mỗi form, giữ kết quả trên `frm` (kể cả khi lỗi).
    // Câu TRUNG TÍNH — ⛔ kể tên cụ thể ("Độ dày kính hoặc Loại kính"): biến
    // theo dòng không chỉ có 2 loại đó. Ô "Tra theo" chỉ mời dữ liệu engine
    // đọc được ở bước chọn mã nên người cấu hình chọn lại trong danh sách đó.
    // Vẽ bằng `.text()` ⇒ câu phải là chữ thuần, ⛔ thẻ HTML.
    var AL_RULE_INPUT_VARIABLE_WARNING =
        "Biến này chưa có giá trị ở bước chọn mã — chọn một dữ liệu khác trong ô Tra theo (danh sách chỉ mời dữ liệu hệ thống đọc được ở bước chọn mã).";

    /** Đọc danh sách biến 1 lần cho form; lỗi/không có API ⇒ `null` (danh sách đầy đủ). */
    function _al_rule_load_input_variables(frm) {
        if (frm.__al_rule_input_vars_loaded) {
            return Promise.resolve(frm.__al_rule_input_vars);
        }
        if (frm.__al_rule_input_vars_promise) return frm.__al_rule_input_vars_promise;

        frm.__al_rule_input_vars_promise = new Promise(function (resolve) {
            if (typeof frappe.call !== "function") {
                frm.__al_rule_input_vars = null;
                frm.__al_rule_input_vars_loaded = true;
                return resolve(null);
            }
            frappe.call({ method: "alumglass.api.get_rule_input_variables" })
                .then(function (r) {
                    var message = r && r.message;
                    var list = Array.isArray(message)
                        ? message
                        : (message && Array.isArray(message.variables) ? message.variables : null);
                    if (!Array.isArray(list)) {
                        console.warn("[AlumGlass] get_rule_input_variables trả dữ liệu lạ — "
                            + "giữ danh sách đầy đủ.", message);
                    }
                    frm.__al_rule_input_vars = Array.isArray(list) ? list : null;
                    frm.__al_rule_input_vars_loaded = true;
                    resolve(frm.__al_rule_input_vars);
                })
                .catch(function (e) {
                    // Lỗi hạ tầng/API chưa có ⇒ ⛔ chặn form, chỉ bỏ lọc.
                    console.warn("[AlumGlass] Không lọc được danh sách biến 'Tra theo' — "
                        + "giữ danh sách đầy đủ:", e);
                    frm.__al_rule_input_vars = null;
                    frm.__al_rule_input_vars_loaded = true;
                    resolve(null);
                });
        });
        return frm.__al_rule_input_vars_promise;
    }

    function _al_rule_setup_input_variable(frm) {
        if (!frm || !frm.fields_dict || !frm.fields_dict.input_variable) return;
        var helper = _al_rule_helper();
        if (!helper || typeof helper.ruleInputResolvableNames !== "function") {
            // Thiếu helper (app_include_js chưa nạp) ⇒ ⛔ lọc liều.
            _al_rule_warn_unresolvable_input(frm);
            return;
        }
        _al_rule_load_input_variables(frm).then(function (variables) {
            if (!Array.isArray(variables)) {
                _al_rule_warn_unresolvable_input(frm);
                return;
            }
            var names = helper.ruleInputResolvableNames(variables);
            if (!names.length) {
                // Không biến nào "resolvable" ⇒ lọc sẽ khoá ô chọn vô ích.
                console.warn("[AlumGlass] Không có biến nào dùng được ở bước chọn mã — "
                    + "giữ danh sách đầy đủ.");
                _al_rule_warn_unresolvable_input(frm);
                return;
            }
            frm.set_query("input_variable", function () {
                return { filters: { name: ["in", names] } };
            });
            _al_rule_warn_unresolvable_input(frm);
        });
    }

    /**
     * Bản ghi CŨ trỏ biến không dùng được ⇒ hiện 1 dòng cảnh báo ngay dưới ô,
     * ⛔ tự đổi giá trị người dùng.
     *
     * Cố ý KHÔNG ghi vào `df.description`: `df` là object meta DÙNG CHUNG, ghi đè
     * rồi form khác mở ra sẽ đọc phải câu cảnh báo cũ làm "mô tả gốc" và kẹt lại.
     * Thay vào đó chèn một phần tử riêng dưới ô, mỗi lượt vẽ xoá và dựng lại.
     */
    function _al_rule_warn_unresolvable_input(frm) {
        if (!frm || !frm.fields_dict || !frm.fields_dict.input_variable) return;
        var field = frm.fields_dict.input_variable;
        var $wrapper = field && field.$wrapper;
        if (!$wrapper || !$wrapper.length) return;

        $wrapper.find(".al-rule-ivar-warning").remove();

        // Chưa có danh sách (đang tải / API lỗi) ⇒ ⛔ cảnh báo oan.
        if (!frm.__al_rule_input_vars_loaded || !Array.isArray(frm.__al_rule_input_vars)) {
            return;
        }
        var helper = _al_rule_helper();
        if (!helper || typeof helper.isRuleInputResolvable !== "function") return;

        var variable = String((frm.doc && frm.doc.input_variable) || "").trim();
        if (!variable || helper.isRuleInputResolvable(frm.__al_rule_input_vars, variable)) {
            return;
        }
        // Chèn ngay dưới "help box" của ô (hoặc dưới vùng nhập nếu ô chưa có mô tả).
        var $help = $wrapper.find(".help-box").first();
        var $anchor = $help.length ? $help : $wrapper.find(".control-input-wrapper").last();
        if (!$anchor.length) $anchor = $wrapper;
        $("<p class='al-rule-ivar-warning small'></p>")
            .attr("style", "color:" + WARN_COLOR + ";margin:4px 0 0;")
            .text(__(AL_RULE_INPUT_VARIABLE_WARNING))
            .insertAfter($anchor);
    }

    /**
     * Câu xem trước dưới tiêu đề — gộp mô tả nghiệp vụ + "tra theo cái gì"
     * (dùng headline sẵn có, ⛔ thêm field JSON).
     */
    function _al_rule_render_headline(frm) {
        if (!frm.dashboard || typeof frm.dashboard.set_headline !== "function") return;
        var doc = frm.doc || {};
        var description = String(doc.rule_description || "").trim();
        var unit = String(doc.input_unit || "").trim();
        // Biến đã khai mà chưa có nhãn ⇒ KHÔNG lấy tên biến (`total_thick_mm`)
        // làm nhãn: nói "dữ liệu quy tắc đọc" — người cấu hình hiểu ngay.
        var label = ruleInputSentenceLabel(doc.input_label, doc.input_variable);
        if (label && unit && label.indexOf("(") === -1) label += " (" + unit + ")";

        // ⚠ `layout.show_message` APPEND html vào vùng thông báo (không thay thế)
        // ⇒ phải XOÁ trước mỗi lần vẽ, nếu không mô tả cũ sẽ chồng/nằm lại khi
        // quản trị xoá trắng ô Mô tả.
        if (typeof frm.dashboard.clear_headline === "function") {
            frm.dashboard.clear_headline();
        } else {
            frm.dashboard.set_headline("");
        }
        if (!description && !label) return;

        var html = '<div style="font-size:12px;line-height:1.45;">';
        if (description) {
            html += frappe.utils.escape_html(description);
        }
        if (label) {
            if (description) html += "<br>";
            html += __("Quy tắc này tra theo") + " <b>"
                + frappe.utils.escape_html(label) + "</b>";
        }
        html += "</div>";
        frm.dashboard.set_headline(html);
    }

    /**
     * Chọn biến "tra theo" mà chưa có nhãn ⇒ điền từ `AL Variable Library.var_label`.
     * Chỉ điền khi nhãn đang TRỐNG hoặc vẫn là nhãn do chính hàm này điền ở lượt
     * trước (đổi biến khác thì cập nhật) — ⛔ ghi đè nhãn người dùng đã gõ tay.
     */
    function _al_rule_fill_input_label(frm) {
        var variable = String((frm.doc && frm.doc.input_variable) || "").trim();
        if (!variable) return;
        var current = String((frm.doc && frm.doc.input_label) || "").trim();
        var autoLabel = String(frm.__al_rule_auto_label || "").trim();
        if (current && current !== autoLabel) return;
        if (!frappe.db || typeof frappe.db.get_value !== "function") return;
        frappe.db.get_value("AL Variable Library", variable, "var_label").then(function (res) {
            var data = (res && res.message) ? res.message : (res || {});
            var label = String((data && data.var_label) || "").trim();
            if (!label) return;
            // Lượt đọc về muộn: người dùng đã đổi biến khác hoặc đã gõ nhãn.
            if (String((frm.doc && frm.doc.input_variable) || "").trim() !== variable) return;
            var now = String((frm.doc && frm.doc.input_label) || "").trim();
            if (now && now !== autoLabel) return;
            frm.__al_rule_auto_label = label;
            frm.set_value("input_label", label);
        }).catch(function () { /* để trống — người dùng tự nhập */ });
    }

    function _al_rule_add_preview_button(frm) {
        frm.add_custom_button(__("Thử tra"), function () {
            // Quy tắc mới chưa lưu ⇒ chưa có gì trong DB để tra.
            if (frm.is_new && frm.is_new()) {
                frappe.msgprint(__("Lưu quy tắc trước rồi bấm Thử tra."));
                return;
            }
            var helper = window.AlumGlassRuleHelper;
            if (!helper || typeof helper.openRulePreview !== "function") {
                frappe.msgprint(__("Chưa nạp được phần hỗ trợ tra cứu. Tải lại trang rồi thử lại."));
                return;
            }
            helper.openRulePreview({
                rule_code: frm.doc.rule_code || frm.doc.name,
                rule_name: frm.doc.rule_name || "",
                // Site chưa migrate ⇒ undefined, hộp thoại tự dùng nhãn chung.
                // ⛔ chuyển MÃ BIẾN sang hộp thoại làm nhãn — cùng quy tắc
                // "dữ liệu quy tắc đọc" như câu trên form.
                input_label: ruleInputSentenceLabel(
                    frm.doc.input_label, frm.doc.input_variable),
                input_unit: frm.doc.input_unit || "",
                // API đọc bản ĐÃ LƯU trong DB ⇒ nói rõ khi form đang có sửa đổi
                // chưa lưu, kẻo quản trị tưởng đang thử bản vừa sửa.
                draft_dirty: typeof frm.is_dirty === "function" ? !!frm.is_dirty() : false,
            });
        });
    }

    // ── Gắn handler Desk (chỉ khi đang chạy trong Frappe) ──────────────────
    function _al_rule_register(frappe) {
        frappe.ui.form.on("AL Rule", {
            refresh: function (frm) {
                // Nhãn enum tiếng Việt đặt TRƯỚC khi các khối khác đọc df.
                _al_rule_localize_enums(frm);
                _al_rule_render_headline(frm);
                _al_rule_add_preview_button(frm);
                _al_rule_setup_input_variable(frm);
                _al_rule_refresh_all(frm);
            },

            // Quản trị sửa mô tả/nhãn ⇒ cập nhật ngay, không phải tải lại form.
            rule_description: function (frm) {
                _al_rule_render_headline(frm);
            },
            input_label: function (frm) {
                _al_rule_render_headline(frm);
                _al_rule_refresh_all(frm);
            },
            input_unit: function (frm) {
                _al_rule_render_headline(frm);
                _al_rule_refresh_all(frm);
            },
            output_label: function (frm) {
                _al_rule_refresh_all(frm);
            },
            input_variable: function (frm) {
                _al_rule_fill_input_label(frm);
                _al_rule_render_headline(frm);
                // Cảnh báo "biến chưa dùng được" đi theo giá trị MỚI (danh sách đã
                // cache theo form ⇒ không gọi API lại).
                _al_rule_warn_unresolvable_input(frm);
                _al_rule_refresh_all(frm);
            },
            rule_type: function (frm) {
                _al_rule_refresh_all(frm);
            },
            result_type: function (frm) {
                _al_rule_refresh_all(frm);
            },
        });

        // Sửa một ô trong lưới ⇒ chỉ vẽ lại câu cảnh báo/thống kê, ⛔ vẽ lại lưới
        // (vẽ lại lưới giữa lúc đang gõ sẽ cướp con trỏ và đổi nhãn liên tục).
        // Riêng cột "Từ"/"Đến" + thêm/xoá dòng còn phải cập nhật KHOÁ nút
        // "Thêm ngưỡng" (dải cuối mở ⇒ khoá) — chỉ đổi trạng thái nút, ⛔ refresh lưới.
        frappe.ui.form.on("AL Rule Threshold Row", {
            from_value: _al_rule_on_threshold_range_change,
            to_value: _al_rule_on_threshold_range_change,
            result_value: _al_rule_render_input_help,
            result_item: _al_rule_render_input_help,
            threshold_rows_add: _al_rule_on_threshold_range_change,
            threshold_rows_remove: _al_rule_on_threshold_range_change,
        });

        frappe.ui.form.on("AL Rule Lookup Row", {
            key_field: _al_rule_render_input_help,
            result_value: _al_rule_render_input_help,
            result_item: _al_rule_render_input_help,
            lookup_rows_add: _al_rule_render_input_help,
            lookup_rows_remove: _al_rule_render_input_help,
        });
    }

    if (typeof frappe !== "undefined" && frappe.ui && frappe.ui.form
            && typeof frappe.ui.form.on === "function") {
        _al_rule_register(frappe);
    }
})();
