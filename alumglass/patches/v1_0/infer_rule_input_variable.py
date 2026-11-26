# -*- coding: utf-8 -*-
"""CHẶNG 3 — điền `AL Rule.input_variable` cho quy tắc đã có dữ liệu RÕ RÀNG.

Thiết kế: `docs/design/tra-cuu-quy-tac-de-hieu.md` §7.4.

Mục tiêu: quy tắc cũ chưa khai "tra theo dữ liệu gì" thì vẫn chạy như trước
(engine đọc `rule_input_expr` / tham số trong công thức). Patch này CHỈ điền
khi dữ liệu hiện có nói CHẮC CHẮN biến đem tra, để form mới hiện đúng câu
"Quy tắc tra theo <nhãn>" mà ⛔ phải sửa tay từng quy tắc.

HAI NGUỒN SUY (chỉ điền khi ĐỒNG NHẤT):

1. **Rule ITEM** — quét `AL Bom Item` có `item_rule = <mã>`:
   - MỌI dòng dùng quy tắc phải có `rule_input_expr` dạng đúng
     `items.<slug>.<field>` (khớp TOÀN BỘ chuỗi, ⛔ đoán từ chuỗi lẫn tạp);
   - tất cả phải cùng MỘT `field`, và `field` phải có trong
     `AL Variable Library`;
   - thoả ⇒ điền `input_variable` (+ `input_scope` suy từ category) và điền
     `rule_input_row = <slug>` cho từng dòng đang trống.

2. **Rule NUMBER** — quét công thức ở:
   `AL Bom Item.qty`, `AL Accessory Item.qty_formula`,
   `AL Cost Template Item.calc_formula`, `AL Quantity Calc Method.calc_fn`,
   `Formula Global Variable.formula_expr`.
   MỌI lời gọi `lookup_rule('<mã>', <token>)` của cùng một mã phải dùng CÙNG
   MỘT token BIẾN đơn, và token đó phải có trong `AL Variable Library`.
   Lời gọi một tham số, token là số, biểu thức, hay nhiều token khác nhau ⇒
   ⛔ đoán, bỏ qua + ghi log.

NGUYÊN TẮC AN TOÀN
──────────────────
- CHỈ điền field ĐANG TRỐNG (`input_variable` trống), `input_label` chỉ điền
  khi trống; ⛔ ghi đè giá trị người dùng đã đặt.
- IDEMPOTENT: chạy lần 2 không sinh thêm lượt ghi nào.
- `dry_run()` chỉ ĐỌC, trả kế hoạch + số liệu để kiểm trước khi migrate.
- Bảng/cột chưa tồn tại (site chưa migrate, doctype chưa cài) ⇒ BỎ QUA nhánh
  đó, ⛔ làm chết `bench migrate`.
- ⛔ `frappe.db.commit()` — patch chạy trong transaction của `bench migrate`.
- ⛔ đổi số tiền/kết quả resolve: chỉ thêm metadata.
"""

import json
import re

import frappe

from alumglass.al_formula_rules import rule_input

RULE_DOCTYPE = "AL Rule"
ITEM_DOCTYPE = "AL Bom Item"
VARIABLE_DOCTYPE = rule_input.VARIABLE_DOCTYPE

#: `rule_input_expr` phải khớp TOÀN BỘ dạng `items.<slug>.<field>`.
_ITEM_EXPR_RE = re.compile(r"^items\.([A-Za-z_][\w-]*)\.([A-Za-z_]\w*)$")

#: Nguồn công thức cho Rule NUMBER — (doctype, field công thức).
FORMULA_SOURCES = (
    ("AL Bom Item", "qty"),
    ("AL Accessory Item", "qty_formula"),
    ("AL Cost Template Item", "calc_formula"),
    ("AL Quantity Calc Method", "calc_fn"),
    ("Formula Global Variable", "formula_expr"),
)

#: Cột cũ của `AL Rule` — lùi về khi site chưa migrate cột chặng 3.
_RULE_BASE_FIELDS = ("name", "rule_code", "rule_type", "result_type")
_RULE_NEW_FIELDS = ("input_variable", "input_scope", "input_label")


def _log(message):
    """Ghi log patch — ⛔ làm chết migrate vì lỗi logger."""
    try:
        frappe.logger("alumglass").info(
            "infer_rule_input_variable: %s" % message)
    except Exception:  # noqa: BLE001
        pass


def _get_rows(doctype, fields, filters=None):
    """`frappe.get_all` chịu lỗi — None khi KHÔNG đọc được (bảng/cột thiếu)."""
    try:
        return frappe.get_all(
            doctype, filters=filters, fields=list(fields)) or []
    except Exception:  # noqa: BLE001 — site chưa migrate ⇒ bỏ nhánh
        return None


def _load_variables():
    """`{var_name: row}` của `AL Variable Library`; rỗng khi không đọc được."""
    rows = _get_rows(VARIABLE_DOCTYPE, ("name", "category", "var_label"))
    if not rows:
        return {}
    return {row.get("name"): row for row in rows if row.get("name")}


def _load_rules():
    """Toàn bộ `AL Rule` (kèm cột chặng 3 nếu đã migrate)."""
    fields = list(_RULE_BASE_FIELDS) + list(_RULE_NEW_FIELDS)
    rows = _get_rows(RULE_DOCTYPE, fields)
    if rows is None:
        rows = _get_rows(RULE_DOCTYPE, _RULE_BASE_FIELDS)
        if rows is None:
            return []
        for row in rows:
            for field in _RULE_NEW_FIELDS:
                row.setdefault(field, "")
    return rows


def _scope_and_label(variable):
    """`(scope, label)` suy từ 1 dòng `AL Variable Library`."""
    row = variable or {}
    scope = (rule_input.ROW_SCOPE
             if (row.get("category") or "").strip()
             == rule_input.ROW_LITERAL_CATEGORY
             else rule_input.GLOBAL_SCOPE)
    label = (row.get("var_label") or "").strip()
    return scope, label


# ── Rule ITEM: suy từ `rule_input_expr` của AL Bom Item ─────────────
def _plan_item_rules(rules, variables):
    """Kế hoạch cho rule ITEM — `(rule_updates, row_updates, skipped)`."""
    targets = [
        rule for rule in rules
        if (rule.get("result_type") or "") == "ITEM"
        and not (rule.get("input_variable") or "").strip()
    ]
    if not targets:
        return [], [], []

    codes = [rule.get("name") for rule in targets if rule.get("name")]
    base_fields = ("name", "slug", "item_rule", "rule_input_expr")
    rows = _get_rows(
        ITEM_DOCTYPE, base_fields + ("rule_input_row",),
        {"item_rule": ("in", codes)})
    has_row_field = True
    if rows is None:
        # Cột `rule_input_row` chưa migrate ⇒ vẫn suy `input_variable` được,
        # chỉ bỏ phần điền slug.
        rows = _get_rows(
            ITEM_DOCTYPE, base_fields, {"item_rule": ("in", codes)})
        has_row_field = False
    if rows is None:
        _log("bỏ nhánh rule ITEM: không đọc được %s" % ITEM_DOCTYPE)
        return [], [], [{
            "rule": rule.get("name"),
            "reason": "không đọc được bảng %s" % ITEM_DOCTYPE,
        } for rule in targets]

    used_by_rule = {}
    for row in rows:
        used_by_rule.setdefault(row.get("item_rule"), []).append(row)

    rule_updates, row_updates, skipped = [], [], []
    for rule in targets:
        name = rule.get("name")
        used = used_by_rule.get(name) or []
        if not used:
            skipped.append({"rule": name,
                            "reason": "không dòng AL Bom Item nào dùng quy tắc"})
            continue

        fields = set()
        parsed = []
        bad_reason = ""
        for row in used:
            expr = str(row.get("rule_input_expr") or "").strip()
            match = _ITEM_EXPR_RE.match(expr)
            if not match:
                bad_reason = ("dòng %s có biểu thức không phải dạng "
                              "items.<dòng>.<cột>" % (row.get("name") or "?"))
                break
            fields.add(match.group(2))
            parsed.append((row, match.group(1)))
        if bad_reason:
            skipped.append({"rule": name, "reason": bad_reason})
            continue
        if len(fields) != 1:
            skipped.append({
                "rule": name,
                "reason": "các dòng dùng NHIỀU field khác nhau: %s"
                          % ", ".join(sorted(fields)),
            })
            continue

        field = fields.pop()
        # Alias độ dày kính: `glass_thick` là TÊN CŨ, `var_label` của nó là
        # "Độ dày kính (tên cũ)" — hiện lên câu người dùng thấy sẽ gây hiểu
        # nhầm là dữ liệu cũ. Có `total_thick_mm` (tên CHUẨN) trong danh mục
        # ⇒ ghi tên chuẩn; engine đã có alias 2 chiều nên kết quả tính ⛔ đổi.
        # Thiếu tên chuẩn ⇒ giữ `glass_thick` (đúng dữ liệu hiện có).
        if field == "glass_thick" and "total_thick_mm" in variables:
            field = "total_thick_mm"
        variable = variables.get(field)
        if variable is None:
            skipped.append({
                "rule": name,
                "reason": "field '%s' không có trong %s" % (
                    field, VARIABLE_DOCTYPE),
            })
            continue
        scope, label = _scope_and_label(variable)
        # CHỈ điền khi engine ĐỌC ĐƯỢC biến này ở bước chọn mã. Biến như
        # `width`/`qty`/`total_qty` có thể nằm trong AL Variable Library
        # nhưng engine KHÔNG nạp cho dòng ở bước chọn mã ⇒ điền vào là dòng
        # hàng ra 0 ÂM THẦM. Biến không thuộc nhóm dòng ⇒ scope GLOBAL cũng
        # ⛔ đúng nghĩa "lấy từ dòng".
        if (scope != rule_input.ROW_SCOPE
                or not rule_input.is_row_variable_resolvable(field)):
            skipped.append({
                "rule": name,
                "reason": "biến '%s' theo dòng nhưng engine không đọc được ở "
                          "bước chọn mã" % field,
            })
            continue
        rule_updates.append({
            "rule": name,
            "input_variable": field,
            "input_scope": scope,
            "input_label": "" if (rule.get("input_label") or "").strip()
            else label,
        })
        if not has_row_field:
            continue
        for row, slug in parsed:
            if str(row.get("rule_input_row") or "").strip():
                continue
            row_updates.append({
                "doctype": ITEM_DOCTYPE,
                "name": row.get("name"),
                "field": "rule_input_row",
                "value": slug,
            })
    return rule_updates, row_updates, skipped


# ── Rule NUMBER: suy từ token trong công thức ───────────────────────
def _plan_number_rules(rules, variables):
    """Kế hoạch cho rule NUMBER — `(rule_updates, skipped)`."""
    number_rules = {
        rule.get("name"): rule for rule in rules
        if (rule.get("result_type") or "") == "NUMBER"
        and not (rule.get("input_variable") or "").strip()
        and rule.get("name")
    }
    if not number_rules:
        return [], []

    usage = {}
    for doctype, field in FORMULA_SOURCES:
        rows = _get_rows(doctype, ("name", field))
        if rows is None:
            _log("bỏ nguồn công thức %s.%s (không đọc được)" % (doctype, field))
            continue
        for row in rows:
            expr = row.get(field)
            if not expr or not str(expr).strip():
                continue
            for call in rule_input.parse_lookup_rule_calls(str(expr)):
                code = call.get("code")
                if not code or code not in number_rules:
                    continue
                info = usage.setdefault(
                    code, {"tokens": set(), "certain": True})
                token = rule_input.simple_variable_arg(call.get("args") or [])
                if token is None:
                    info["certain"] = False
                else:
                    info["tokens"].add(token)

    rule_updates, skipped = [], []
    for code, info in usage.items():
        tokens = info["tokens"]
        if not info["certain"] or len(tokens) != 1:
            skipped.append({
                "rule": code,
                "reason": "lời gọi không đồng nhất về token biến đơn: %s"
                          % (", ".join(sorted(tokens)) or "có lời gọi phức tạp"),
            })
            continue
        token = next(iter(tokens))
        variable = variables.get(token)
        if variable is None:
            skipped.append({
                "rule": code,
                "reason": "token '%s' không có trong %s" % (
                    token, VARIABLE_DOCTYPE),
            })
            continue
        rule = number_rules.get(code) or {}
        scope, label = _scope_and_label(variable)
        # Công thức chỉ tự chèn được biến TOÀN CỤC (engine chèn trước khi
        # tính). Token là biến theo dòng ⇒ công thức phải tự truyền giá trị,
        # ⛔ suy ra "quy tắc tra theo biến dòng" từ đây.
        if scope != rule_input.GLOBAL_SCOPE:
            skipped.append({
                "rule": code,
                "reason": "token '%s' là biến theo dòng, không phải biến "
                          "toàn cục" % token,
            })
            continue
        rule_updates.append({
            "rule": code,
            "input_variable": token,
            "input_scope": scope,
            "input_label": "" if (rule.get("input_label") or "").strip()
            else label,
        })

    # Rule NUMBER không xuất hiện trong công thức nào ⇒ để trống (⛔ log rác).
    for code in number_rules:
        if code not in usage:
            skipped.append({"rule": code,
                            "reason": "không lời gọi lookup_rule nào trong "
                                      "các công thức đã quét"})
    return rule_updates, skipped


def build_plan():
    """Tính kế hoạch (KHÔNG ghi) — dùng cho cả `execute()` và `dry_run()`."""
    rules = _load_rules()
    variables = _load_variables()
    item_updates, row_updates, item_skipped = _plan_item_rules(rules, variables)
    number_updates, number_skipped = _plan_number_rules(rules, variables)
    return {
        "rule_updates": item_updates + number_updates,
        "row_updates": row_updates,
        "skipped": item_skipped + number_skipped,
    }


def _apply(plan):
    """Ghi kế hoạch; trả `(số rule đã ghi, số dòng đã ghi, lỗi)`. """
    written_rules, written_rows, errors = 0, 0, []
    for update in plan["rule_updates"]:
        payload = {
            "input_variable": update["input_variable"],
            "input_scope": update["input_scope"],
        }
        if update.get("input_label"):
            payload["input_label"] = update["input_label"]
        try:
            frappe.db.set_value(
                RULE_DOCTYPE, update["rule"], payload, update_modified=False)
            written_rules += 1
        except Exception as exc:  # noqa: BLE001 — 1 rule lỗi ⛔ chặn cả patch
            errors.append("rule %s: %s" % (update["rule"], exc))
    for update in plan["row_updates"]:
        try:
            frappe.db.set_value(
                update["doctype"], update["name"], update["field"],
                update["value"], update_modified=False)
            written_rows += 1
        except Exception as exc:  # noqa: BLE001 — cột chưa migrate ⇒ bỏ qua
            errors.append("dòng %s: %s" % (update["name"], exc))
            # Cột không ghi được ⇒ thôi phần slug, ⛔ lặp lỗi từng dòng.
            break
    return written_rules, written_rows, errors


def _summary(plan, written_rules=0, written_rows=0, errors=None):
    return {
        "rules_to_update": len(plan["rule_updates"]),
        "item_rows_to_update": len(plan["row_updates"]),
        "rules_written": written_rules,
        "item_rows_written": written_rows,
        "skipped": len(plan["skipped"]),
        "skipped_detail": plan["skipped"],
        "errors": list(errors or []),
    }


def execute():
    """Điền `AL Rule.input_variable` khi CHẮC CHẮN — chạy trong `bench migrate`."""
    plan = build_plan()
    written_rules, written_rows, errors = _apply(plan)
    summary = _summary(plan, written_rules, written_rows, errors)
    _log(json.dumps(summary, ensure_ascii=False, default=str))
    return summary


def dry_run():
    """Chỉ ĐỌC — trả kế hoạch chi tiết để kiểm TRƯỚC khi migrate."""
    plan = build_plan()
    summary = _summary(plan)
    summary["dry_run"] = True
    summary["planned"] = {
        "rules": [
            {
                "rule": update["rule"],
                "input_variable": update["input_variable"],
                "input_scope": update["input_scope"],
                "input_label": update.get("input_label") or "",
            }
            for update in plan["rule_updates"]
        ],
        "item_rows": list(plan["row_updates"]),
    }
    return summary
