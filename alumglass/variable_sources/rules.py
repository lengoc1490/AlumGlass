# -*- coding: utf-8 -*-
"""Bộ luật lọc biến của Variable Catalog — THUẦN PYTHON, không import frappe.

Vì sao tách riêng khỏi phần ORM:
- Test được bằng `python3 -I` trên máy không có site
  (xem `alumglass/tests/test_variable_catalog_rules.py`).
- Catalog core không phụ thuộc ORM ⇒ thêm nguồn biến mới chỉ là thêm adapter
  + khai rule, KHÔNG sửa file này.

Một rule là dict (hoặc Document đọc qua `_get`) gồm các khoá:
    action, source_kind, source_ref, name_prefix, name_regex, category_tag,
    var_type, source_type, group_label, sort_order, only_fields,
    require_value, is_active

Phạm vi field trên candidate (client lọc theo field đang sửa):
    only_fields=[]   → KHÔNG giới hạn
    only_fields=[..] → chỉ hiện ở các field đó
    hide_all=True    → ẨN Ở MỌI FIELD (giao phạm vi nguồn × rule rỗng) —
                       khác hoàn toàn với "không giới hạn".
"""
import json
import re

INCLUDE_ALL = "INCLUDE_ALL"
EXCLUDE_ALL = "EXCLUDE_ALL"

# Giá trị "không có giá trị" theo quy ước cũ của AlumGlass (xem
# api/__init__.py — autocomplete hiển thị "—" khi chưa resolve được).
_EMPTY_DISPLAY = "—"


def _get(obj, key, default=None):
    """Đọc 1 khoá từ dict hoặc Document (child row của Frappe)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_bool(value, default=False):
    """Ép cờ về bool — LƯU Ý `bool("0")` là True nên phải xét chuỗi."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "none")
    return bool(value)


def to_int(value, default=100):
    """Ép Int an toàn (rule lưu từ DB có thể là None/chuỗi rỗng)."""
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def split_pipe(value):
    """Tách danh sách ngăn bởi `|` — giữ nguyên thứ tự, bỏ phần tử rỗng."""
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        raw = value
    else:
        raw = str(value).split("|")
    return [str(v).strip() for v in raw if str(v).strip()]


def parse_json_list(value):
    """Đọc `Small Text` chứa JSON list. Trả None nếu rỗng/không hợp lệ.

    Không ném lỗi: dữ liệu cấu hình sai KHÔNG được làm sập autocomplete —
    caller coi như "không khai" (an toàn ngược).
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, list):
        return None
    return [str(v).strip() for v in parsed if str(v).strip()]


def is_empty_value(value):
    """True khi biến không có giá trị thật (None / rỗng / nhãn "—")."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in ("", _EMPTY_DISPLAY)
    return False


def candidate_has_value(candidate):
    """Ưu tiên cờ `has_value` do adapter tính; thiếu thì suy từ `value`."""
    flag = _get(candidate, "has_value")
    if flag is not None:
        return _as_bool(flag)
    return not is_empty_value(_get(candidate, "value"))


def is_active_rule(rule):
    return _as_bool(_get(rule, "is_active"), True)


def is_exclude_action(rule):
    return (_get(rule, "action") or "").strip().lower() == "exclude"


def _matches(rule, candidate, fieldname=None, ignore_require_value=False):
    """Khớp 1 rule với 1 candidate (không xét default_action)."""
    if not is_active_rule(rule):
        return False

    name = str(_get(candidate, "name") or "")

    # 1. Nguồn biến — rỗng = mọi nguồn.
    kind = (_get(rule, "source_kind") or "").strip()
    if kind and kind != (_get(candidate, "source_kind") or ""):
        return False

    # 2. Tham chiếu nguồn: `*`/rỗng/AUTO = mọi bản ghi của nguồn đó.
    ref = (_get(rule, "source_ref") or "").strip()
    if ref and ref not in ("*", "AUTO"):
        allowed = {r.lower() for r in split_pipe(ref)}
        cand_ref = str(_get(candidate, "source_ref") or "").strip().lower()
        if cand_ref not in allowed:
            return False

    # 3. Tiền tố tên (pipe list, phân biệt hoa thường như spec).
    prefixes = split_pipe(_get(rule, "name_prefix"))
    if prefixes and not any(name.startswith(p) for p in prefixes):
        return False

    # 4. Regex tên — regex hỏng ⇒ coi như không khớp (không ném ra UI).
    pattern = (_get(rule, "name_regex") or "").strip()
    if pattern:
        try:
            if not re.search(pattern, name):
                return False
        except re.error:
            return False

    # 5. Category / nhóm — không phân biệt hoa thường.
    cats = [c.lower() for c in split_pipe(_get(rule, "category_tag"))]
    if cats:
        cand_cat = str(_get(candidate, "category") or "").lower()
        cand_group = str(_get(candidate, "group") or "").lower()
        if not any(c in (cand_cat, cand_group) for c in cats):
            return False

    # 6. Kiểu biến / source_type (FVB) — so khớp chính xác.
    var_type = (_get(rule, "var_type") or "").strip()
    if var_type and var_type != (_get(candidate, "type") or ""):
        return False

    source_type = (_get(rule, "source_type") or "").strip()
    if source_type and source_type != (_get(candidate, "source_type") or ""):
        return False

    # 7. only_fields: client không gửi fieldname ⇒ BỎ QUA điều kiện (không
    #    chặn oan khi widget cũ chưa truyền field).
    only_fields = parse_json_list(_get(rule, "only_fields"))
    if only_fields and fieldname and fieldname not in only_fields:
        return False

    # 8. require_value: chỉ hiện khi biến có giá trị thật.
    if not ignore_require_value and _as_bool(_get(rule, "require_value"), False):
        if not candidate_has_value(candidate):
            return False

    return True


def rule_matches(rule, candidate, fieldname=None):
    """Public: rule có khớp candidate này không (đã xét mọi điều kiện)."""
    return _matches(rule, candidate, fieldname)


def _rule_sort_key(item):
    """Ưu tiên rule khai trước khi cùng sort_order."""
    index, rule = item
    return (to_int(_get(rule, "sort_order"), 100), index)


def combine_only_fields(base, rule_scope):
    """GIAO phạm vi field của nguồn (adapter) và của profile rule.

    Rỗng ở một phía = phía đó KHÔNG giới hạn. Biến chỉ hiện khi CẢ nguồn lẫn
    rule đều cho phép field đang sửa.

    ⚠️ Hàm này chỉ trả LIST nên KHÔNG biểu diễn được "ẩn ở mọi field"
    (giao rỗng). Logic catalog dùng `_combine_field_scopes` — hàm này giữ lại
    cho caller cũ/test cũ.
    """
    scope, _hide_all = _combine_field_scopes(base, rule_scope)
    return scope


def _combine_field_scopes(base, rule_scope):
    """Trả `(only_fields, hide_all)` — giao phạm vi nguồn × phạm vi rule.

    - Một phía rỗng (không giới hạn) ⇒ lấy phía còn lại, `hide_all=False`.
    - Cả hai cùng có giới hạn và giao KHÁC rỗng ⇒ list giao, `hide_all=False`.
    - Cả hai cùng có giới hạn nhưng giao RỖNG ⇒ `only_fields=[]`,
      `hide_all=True` (biến không hiện ở field nào — KHÔNG được hiểu là
      "không giới hạn").
    """
    base = list(base or [])
    rule_scope = list(rule_scope or [])
    if not base:
        return rule_scope, False
    if not rule_scope:
        return base, False
    intersection = [field for field in base if field in rule_scope]
    if not intersection:
        return [], True
    return intersection, False


def _merge_only_fields(matched_rules):
    """Hợp `only_fields` của TẤT CẢ rule Include cùng khớp.

    Vì sao không lấy rule có sort_order nhỏ nhất: rule A khai
    `only_fields=["qty"]`, rule B không khai (cho phép mọi field) — nếu lấy A
    thì biến bị ẩn oan ở `width` dù B đã cho phép. Luật chốt: **một rule
    không giới hạn ⇒ không giới hạn**; ngược lại lấy hợp theo thứ tự khai.
    """
    merged = []
    for _index, rule in matched_rules:
        values = parse_json_list(_get(rule, "only_fields"))
        if not values:
            return []
        for value in values:
            if value not in merged:
                merged.append(value)
    return merged


def active_source_kinds(rules, default_action=INCLUDE_ALL, all_kinds=()):
    """Tập source_kind cần chạy adapter — tránh query thừa.

    - default_action=EXCLUDE_ALL: chỉ chạy nguồn có rule Include.
    - default_action=INCLUDE_ALL:
        * CÓ rule Include ⇒ chỉ chạy các nguồn đó (đúng hợp đồng "candidates =
          union(adapters được rule Include chạm tới)").
        * KHÔNG có rule Include ⇒ chạy TẤT CẢ adapter đã đăng ký (tương thích
          ngược: profile rỗng không được làm mất biến nào).
    `slug_reference` không phải adapter biến — references xử lý riêng.
    """
    included = set()
    for rule in rules or []:
        if not is_active_rule(rule) or is_exclude_action(rule):
            continue
        kind = (_get(rule, "source_kind") or "").strip()
        if kind and kind != "slug_reference":
            included.add(kind)

    if included:
        return included
    if (default_action or INCLUDE_ALL) == EXCLUDE_ALL:
        return set()
    return {k for k in (all_kinds or []) if k != "slug_reference"}


def select_candidates(candidates, rules, fieldname=None,
                      default_action=INCLUDE_ALL):
    """Áp toàn bộ rule lên danh sách candidate.

    Thứ tự (theo spec §4):
      1. Rule Exclude khớp ⇒ loại (Exclude thắng Include).
      2. default_action=EXCLUDE_ALL ⇒ chỉ giữ candidate có rule Include khớp.
      3. Rule Include khớp ⇒ gắn nhóm (`group_label`) + `sort_order` của rule.

    Trả `(selected, stats)`; `stats["excluded_by_rules"]` để caller báo cho
    người dùng biết đã lọc bao nhiêu — KHÔNG bao giờ bỏ im lặng.
    """
    active = [r for r in (rules or []) if is_active_rule(r)]
    includes = [(i, r) for i, r in enumerate(active) if not is_exclude_action(r)]
    excludes = [r for r in active if is_exclude_action(r)]
    exclude_all = (default_action or INCLUDE_ALL) == EXCLUDE_ALL

    selected = []
    excluded_count = 0

    for candidate in candidates or []:
        if any(rule_matches(r, candidate, fieldname) for r in excludes):
            excluded_count += 1
            continue

        matched = [(i, r) for i, r in includes
                   if rule_matches(r, candidate, fieldname)]

        # require_value là cổng TOÀN CỤC: rule khớp điều kiện nguồn nhưng biến
        # rỗng ⇒ loại hẳn (không rơi về "hiện với nhóm mặc định").
        if not matched and _blocked_by_require_value(candidate, includes, fieldname):
            excluded_count += 1
            continue

        if exclude_all and not matched:
            excluded_count += 1
            continue

        out = dict(candidate) if isinstance(candidate, dict) else dict(candidate)
        # Mặc định [] + hide_all=False: client luôn có key để lọc.
        out.setdefault("only_fields", [])
        out["hide_all"] = False
        if matched:
            _idx, best = min(matched, key=_rule_sort_key)
            group_label = (_get(best, "group_label") or "").strip()
            if group_label:
                out["group"] = group_label
            out["sort_order"] = to_int(
                _get(best, "sort_order"), to_int(_get(out, "sort_order"), 100))
            # Phạm vi field = GIAO của phạm vi NGUỒN (adapter gắn, vd FVB
            # `applies_to_field`) và phạm vi RULE (hợp của mọi rule khớp).
            # Giao RỖNG ⇒ hide_all=True (không phải "không giới hạn").
            out["only_fields"], out["hide_all"] = _combine_field_scopes(
                out.get("only_fields"), _merge_only_fields(matched))
            out["matched_rule"] = {
                "action": _get(best, "action"),
                "source_kind": _get(best, "source_kind"),
                "group_label": group_label,
                "sort_order": _get(best, "sort_order"),
            }
        selected.append(out)

    return selected, {"excluded_by_rules": excluded_count}


def _blocked_by_require_value(candidate, includes, fieldname):
    """Có rule Include đòi giá trị mà candidate rỗng không?"""
    for _i, rule in includes:
        if not _as_bool(_get(rule, "require_value"), False):
            continue
        if _matches(rule, candidate, fieldname, ignore_require_value=True):
            return not candidate_has_value(candidate)
    return False


def dedupe_candidates(candidates):
    """Gộp candidate trùng `name` theo chính sách ưu tiên của spec §4.

    Ưu tiên: có giá trị (`has_value`) > sort_order nhỏ hơn > adapter đăng ký
    trước > thứ tự xuất hiện. Trả `(kept, duplicates)` — bản ghi bị loại phải
    được báo lại trong `meta.duplicates`, không bỏ im lặng.
    """
    buckets = {}
    order = []
    for index, candidate in enumerate(candidates or []):
        name = str(_get(candidate, "name") or "").strip()
        if not name:
            continue
        if name not in buckets:
            buckets[name] = []
            order.append(name)
        buckets[name].append((index, candidate))

    kept = []
    duplicates = []
    for name in order:
        entries = buckets[name]

        def rank(item):
            index, cand = item
            return (
                0 if candidate_has_value(cand) else 1,
                to_int(_get(cand, "sort_order"), 100),
                to_int(_get(cand, "adapter_order"), 1000),
                index,
            )

        ranked = sorted(entries, key=rank)
        # Copy trước khi chỉnh: KHÔNG sửa candidate gốc của nguồn.
        winner = dict(ranked[0][1])
        # Phạm vi field của tên biến = HỢP mọi nguồn (một nguồn cho phép thì
        # biến hiện ở field đó); nguồn không giới hạn ⇒ không giới hạn.
        winner["only_fields"], winner["hide_all"] = _merge_entry_field_scopes(
            entries)
        kept.append(winner)
        if len(ranked) > 1:
            duplicates.append({
                "name": name,
                "kept": _source_key(winner),
                "dropped": [_source_key(c) for _i, c in ranked[1:]],
            })
    return kept, duplicates


def _merge_entry_field_scopes(entries):
    """Hợp phạm vi field của mọi entry cùng tên → `(only_fields, hide_all)`.

    - Có entry KHÔNG giới hạn (`only_fields=[]`, `hide_all` falsy) ⇒ thắng:
      `([], False)`.
    - TẤT CẢ entry đều `hide_all=True` ⇒ `([], True)`.
    - Còn lại ⇒ union danh sách field, `hide_all=False`.
    """
    merged = []
    all_hide_all = True
    for _index, candidate in entries:
        hide_all = _as_bool(_get(candidate, "hide_all"), False)
        if hide_all:
            continue
        scope = parse_json_list(_get(candidate, "only_fields"))
        if not scope:
            # Không giới hạn ⇒ thắng ngay, không cần xét entry còn lại.
            return [], False
        all_hide_all = False
        for field in scope:
            if field not in merged:
                merged.append(field)
    if all_hide_all and entries:
        return [], True
    return merged, False


def _source_key(candidate):
    """Khoá nguồn dạng `source_kind:source_ref` để báo cáo dedup."""
    kind = _get(candidate, "source_kind") or ""
    ref = _get(candidate, "source_ref") or ""
    return f"{kind}:{ref}" if ref else str(kind)


def build_groups(candidates):
    """Gom candidate thành groups theo `group` + `sort_order` (đã lọc/dedup)."""
    groups = {}
    for candidate in candidates or []:
        label = str(_get(candidate, "group") or "Khác")
        sort_order = to_int(_get(candidate, "sort_order"), 100)
        group = groups.get(label)
        if group is None:
            group = {"key": label, "label": label,
                     "sort_order": sort_order, "variables": []}
            groups[label] = group
        group["sort_order"] = min(group["sort_order"], sort_order)
        group["variables"].append(candidate)

    result = []
    for group in groups.values():
        group["variables"].sort(
            key=lambda c: (to_int(_get(c, "sort_order"), 100),
                           str(_get(c, "name") or "")))
        result.append(group)
    result.sort(key=lambda g: (g["sort_order"], g["label"]))
    return result


# Alias công khai cho các module CÙNG package (adapter) — buộc dùng chung một
# cách đọc dict/Document và ép cờ, tránh 2 cách hiểu lệch nhau.
get_attr = _get
as_bool = _as_bool
