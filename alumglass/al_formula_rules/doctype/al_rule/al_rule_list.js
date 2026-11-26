// AL Rule — Client Script (DANH SÁCH)
// Module: AL Formula Rules
//
// ═══════════════════════════════════════════════════════════════════════════
// VÌ SAO CÓ TỆP NÀY: enum `rule_type` / `result_type` lưu trong DB là tiếng
// Anh (`CONSTANT` / `THRESHOLD` / `LOOKUP`, `NUMBER` / `ITEM`). Frappe hiện
// nguyên giá trị ở danh sách ⇒ người dùng đọc mã kỹ thuật. Form đã đổi nhãn
// bằng `options` dạng `{label, value}` (al_rule.js); DANH SÁCH phải dùng
// `formatters` thì mới cùng nhãn.
//
// MỘT BẢN NHÃN: `rule_helper.js` (nạp toàn trang qua `app_include_js`) giữ
// `ruleTypeLabel` / `ruleResultTypeLabel`. Bảng dự phòng dưới đây chỉ dùng khi
// helper chưa nạp — giữ ĐỒNG BỘ chuỗi với `ruleTypeOptions` /
// `ruleResultTypeOptions` của helper.
//
// Frappe v14 tự eval `doctype/<dt>/<dt>_list.js` (desk/form/meta.py
// `_add_code`) và list view đọc `frappe.listview_settings[dt].formatters`
// (list_view.js) ⇒ ⛔ cần khai `doctype_list_js` trong hooks.py.
// ═══════════════════════════════════════════════════════════════════════════
(function () {
    "use strict";

    function _t(text) {
        return (typeof __ === "function") ? __(text) : String(text);
    }

    // Dự phòng — đồng bộ với rule_helper.js (RULE_TYPE_LABELS/RESULT_TYPE_LABELS).
    var RULE_TYPE_LABELS = {
        CONSTANT: "Hằng số",
        THRESHOLD: "Tra theo dải",
        LOOKUP: "Tra theo bảng",
    };
    var RESULT_TYPE_LABELS = {
        NUMBER: "Số",
        ITEM: "Mã vật tư",
    };

    function _localLabel(map, value) {
        var raw = String(value === null || value === undefined ? "" : value).trim();
        if (!raw) return "";
        var key = raw.toUpperCase();
        return map[key] ? _t(map[key]) : raw; // giá trị lạ ⇒ ⛔ ô trống câm lặng
    }

    function _helper() {
        return (typeof window !== "undefined" && window.AlumGlassRuleHelper) || null;
    }

    function ruleTypeCell(value) {
        var helper = _helper();
        if (helper && typeof helper.ruleTypeLabel === "function") {
            return helper.ruleTypeLabel(value);
        }
        return _localLabel(RULE_TYPE_LABELS, value);
    }

    function resultTypeCell(value) {
        var helper = _helper();
        if (helper && typeof helper.ruleResultTypeLabel === "function") {
            return helper.ruleResultTypeLabel(value);
        }
        return _localLabel(RESULT_TYPE_LABELS, value);
    }

    if (typeof frappe !== "undefined" && frappe && frappe.listview_settings) {
        frappe.listview_settings["AL Rule"] = Object.assign(
            frappe.listview_settings["AL Rule"] || {},
            {
                formatters: {
                    rule_type: function (value) { return ruleTypeCell(value); },
                    result_type: function (value) { return resultTypeCell(value); },
                },
            }
        );
    }
})();
