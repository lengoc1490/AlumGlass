"""B9/Đ2 — Tạo sản phẩm mới từ một BỘ MẪU.

Mục tiêu: nhân viên chọn 1 bộ đã có (thường là bộ chuẩn, vd CDMQ-2C), đặt mã +
tên mới, và nhận về **bộ mới độc lập** để chỉ sửa vài ô — thay vì gõ lại
14–24 dòng × 8 ô.

Nguyên tắc (theo thiết kế §4.3 Đ2):

  · Nhân bản bằng ``frappe.copy_doc`` — copy theo META của DocType, nên field
    thêm sau này tự đi theo. ⛔ map tay từng field: map tay là quên field mới
    ngay lập tức (đúng lớp lỗi D6/F4a của snapshot BOM).
  · Cả 4 doctype đều ``autoname = field:<mã>`` ⇒ phải đặt mã MỚI **trước khi
    insert**; mã trùng ⇒ ném lỗi rõ ràng, ⛔ tự thêm số (*-1, *-2) để người
    dùng khỏi nhận mã mình không chọn.
  · Ghi nguồn gốc ``cloned_from`` / ``cloned_at`` để về sau biết bộ nào là gốc
    ("clone trôi" là rủi ro đã nêu trong thiết kế).
  · Site chưa migrate (chưa có 2 cột) **vẫn phải tạo được**: bỏ 2 field đó +
    cảnh báo, ⛔ để lỗi cột thiếu làm hỏng luồng tạo sản phẩm.

Các bộ được nhân bản (nếu nguồn có trỏ tới):

  · ``AL Bom Set`` — luôn có (bộ mẫu chính).
  · ``AL Accessory Set`` — qua ``AL Bom Set.default_accessory_set``.
  · ``AL Variable Set`` — qua ``AL Bom Set.variable_set``.
  · ``AL Cost Template`` — qua ``AL BOM.default_cost_template`` của các AL BOM
    đang trỏ bộ mẫu (AL Bom Set không có ô này).

⚠ Bộ giá mới được tạo nhưng **liên kết tới nó nằm trên AL BOM** — hàm này
KHÔNG nhân bản AL BOM (ngoài phạm vi Đ2), nên kết quả trả về có cảnh báo nhắc
người dùng trỏ AL BOM của sản phẩm mới sang bộ giá mới.
"""
import json

import frappe

# ── Tên DocType (identifier tiếng Anh, đúng tên bảng) ────────────────────
BOM_SET = "AL Bom Set"
ACCESSORY_SET = "AL Accessory Set"
COST_TEMPLATE = "AL Cost Template"
VARIABLE_SET = "AL Variable Set"
BOM = "AL BOM"
BOM_VERSION = "AL BOM Version"

# ── Field nguồn gốc (2 field đọc-only thêm vào cả 4 doctype) ────────────
CLONED_FROM_FIELD = "cloned_from"
CLONED_AT_FIELD = "cloned_at"

# Field mã + field tên của từng doctype được nhân bản.
_KIND_META = {
    BOM_SET: ("set_code", "set_name"),
    ACCESSORY_SET: ("set_code", "set_name"),
    COST_TEMPLATE: ("template_code", "template_name"),
    VARIABLE_SET: ("set_code", "set_name"),
}

# Nhãn người-đọc cho câu lỗi — ⛔ phơi tên DocType trần ra người dùng.
_KIND_LABEL = {
    BOM_SET: "bộ BOM",
    ACCESSORY_SET: "bộ phụ kiện",
    COST_TEMPLATE: "bộ giá",
    VARIABLE_SET: "bộ biến",
}

# Field hệ thống của dòng con — không đem từ snapshot sang bộ mới.
_SYSTEM_ROW_FIELDS = frozenset({
    "name", "parent", "parentfield", "parenttype", "idx", "docstatus",
    "owner", "creation", "modified", "modified_by",
})

# Tuỳ chọn caller được phép truyền trong `options`.
_OPTION_KEYS = frozenset({"accessory_set", "variable_set", "cost_template"})


# ══════════════════════════════════════════════════════════════════════
# Tiện ích nhỏ
# ══════════════════════════════════════════════════════════════════════
def _abort(message):
    """Dừng bằng câu tiếng Việt — ⛔ để lỗi kỹ thuật lọt ra người dùng."""
    frappe.throw(message)


def _clean(value):
    """Chuỗi đã bỏ khoảng trắng; None/không phải chuỗi ⇒ ''."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def _has_column(doctype, column):
    """Cột đã có trên site chưa — dùng để chịu được site chưa migrate."""
    try:
        return bool(frappe.db.has_column(doctype, column))
    except Exception:
        return False


class _Warnings:
    """Danh sách cảnh báo, giữ thứ tự và bỏ trùng."""

    def __init__(self):
        self._items = []

    def add(self, message):
        message = _clean(message)
        if message and message not in self._items:
            self._items.append(message)

    def as_list(self):
        return list(self._items)


def _normalize_options(options):
    """`options` từ client có thể là JSON string ⇒ chuẩn hoá về dict."""
    if not options:
        return {}
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except Exception:
            _abort("Tuỳ chọn nhân bản không đọc được (không phải JSON hợp lệ). "
                   "Bỏ phần tuỳ chọn rồi thử lại.")
    if not isinstance(options, dict):
        _abort("Tuỳ chọn nhân bản phải là một đối tượng (mã bộ mới / bộ phụ "
               "kiện / bộ giá / bộ biến).")
    return dict(options)


def _warn_unknown_options(options, warnings):
    """Tuỳ chọn lạ (gõ nhầm khoá) ⇒ cảnh báo, ⛔ nuốt im lặng."""
    if not isinstance(options, dict):
        return
    unknown = sorted(set(options) - _OPTION_KEYS)
    if unknown:
        warnings.add(
            "Bỏ qua tuỳ chọn không dùng được: %s. Chỉ nhận accessory_set, "
            "variable_set, cost_template." % ", ".join(unknown))


# ══════════════════════════════════════════════════════════════════════
# Nguồn gốc (cloned_from / cloned_at)
# ══════════════════════════════════════════════════════════════════════
def _apply_provenance(doc, provenance, warnings):
    """Ghi "tạo từ <mã bộ gốc> lúc <giờ>" — bỏ qua khi site chưa migrate.

    `provenance` là **mã/tên bộ gốc** (người đọc được), ⛔ "DocType:tên":
    người dùng thấy chuỗi này ngay trên form nên không được có tên bảng kỹ thuật.

    Trả True nếu đã ghi được. Khi thiếu cột ⇒ cảnh báo MỘT lần cho mỗi doctype
    (site chưa chạy `bench migrate`) và ⛔ ném lỗi: migrate là việc của quản
    trị, không phải lý do chặn nhân viên tạo sản phẩm.
    """
    doctype = doc.doctype
    missing = [field for field in (CLONED_FROM_FIELD, CLONED_AT_FIELD)
               if not _has_column(doctype, field)]
    if missing:
        # Chi tiết kỹ thuật (tên cột, tên DocType) vào Error Log; người dùng
        # chỉ cần biết việc gì chưa có và nhờ ai.
        frappe.log_error(
            "product_clone: thiếu cột nguồn gốc trên %s: %s"
            % (doctype, ", ".join(missing)),
            "AlumGlass B9: thiếu cột nguồn gốc")
        warnings.add(
            "Bộ mới đã tạo nhưng chưa lưu được dấu vết \"tạo từ bộ nào, lúc "
            "nào\". Nhờ quản trị bật phần này rồi tạo lại nếu cần dấu vết.")
        return False
    doc.set(CLONED_FROM_FIELD, provenance)
    doc.set(CLONED_AT_FIELD, frappe.utils.now())
    return True


# ══════════════════════════════════════════════════════════════════════
# Lập kế hoạch (dùng chung cho dry-run và tạo thật)
# ══════════════════════════════════════════════════════════════════════
def _plan_row(doctype, source, code, name, rows, extra=None):
    row = {
        "doctype": doctype,
        "source": source,
        "code": code,
        "name": name,
        "rows": int(rows or 0),
    }
    if extra:
        row["extra"] = extra
    return row


def _source_payload(doctype, name, code, display_name, extra=None):
    payload = {
        "doctype": doctype,
        "name": name,
        "set_code": code,
        "set_name": display_name,
    }
    if extra:
        payload.update(extra)
    return payload


def _cost_template_sources(source_set_code, warnings):
    """Các `AL Cost Template` mà bộ mẫu đang dùng (qua AL BOM).

    AL Bom Set không có ô trỏ Cost Template — liên kết nằm trên AL BOM. Lấy
    danh sách KHÁC NHAU, sắp xếp cho ổn định (thứ tự chạy lại không đổi mã).
    """
    try:
        rows = frappe.get_all(
            BOM,
            filters={"bom_set": source_set_code},
            fields=["default_cost_template"],
            limit_page_length=0,
        ) or []
    except Exception:
        warnings.add(
            "Không đọc được danh sách AL BOM của bộ mẫu nên bỏ qua phần bộ giá "
            "— bộ mới sẽ dùng lại bộ giá cũ nếu có. Kiểm tra lại AL BOM của "
            "bộ mẫu rồi tạo lại nếu cần tách bộ giá.")
        return []
    names = set()
    for row in rows:
        name = _clean(row.get("default_cost_template")
                      if hasattr(row, "get") else None)
        if name:
            names.add(name)
    return sorted(names)


def _cost_template_codes(new_code, override, count, warnings):
    """Mã cho các bộ giá mới: `<mã>-CT`, `<mã>-CT2`, ... (đổi được qua options)."""
    if count <= 0:
        return []
    defaults = [new_code + "-CT"]
    defaults.extend("%s-CT%d" % (new_code, index)
                    for index in range(2, count + 1))
    if not override:
        return defaults
    if isinstance(override, (list, tuple)):
        given = [_clean(item) for item in override]
        given = [item for item in given if item]
    else:
        given = [_clean(override)]
    if len(given) > count:
        warnings.add(
            "Có %d mã bộ giá được truyền nhưng bộ mẫu chỉ dùng %d bộ giá — "
            "bỏ qua mã thừa." % (len(given), count))
        given = given[:count]
    return given + defaults[len(given):]


def _build_plan(source, new_code, new_name, options, warnings):
    """Danh sách việc cần làm: bộ nào, mã nào, tên nào, bao nhiêu dòng."""
    source_name = getattr(source, "name", None) or _clean(source.get("set_code"))
    base_name = (_clean(new_name) or _clean(source.get("set_name"))
                 or new_code)
    plan = [_plan_row(BOM_SET, source_name, new_code, base_name,
                      len(source.get("items") or []))]

    # Bộ biến TRƯỚC bộ phụ kiện: AL Accessory Set có ô Link `variable_set`, nên
    # bộ biến mới phải tồn tại trước khi insert bộ phụ kiện (Frappe kiểm Link).
    variable_source = _clean(source.get("variable_set"))
    variable_code = None
    if variable_source:
        if frappe.db.exists(VARIABLE_SET, variable_source):
            variable_code = (_clean(options.get("variable_set"))
                             or new_code + "-VS")
            plan.append(_plan_row(
                VARIABLE_SET, variable_source, variable_code,
                base_name + " — Bộ biến",
                len(frappe.get_doc(VARIABLE_SET, variable_source)
                    .get("items") or [])))
        else:
            warnings.add(
                "Bộ mẫu đang trỏ tới bộ biến “%s” nhưng bộ này không còn tồn "
                "tại — bộ mới sẽ không có bộ biến. Kiểm tra lại bộ mẫu."
                % variable_source)

    accessory_source = _clean(source.get("default_accessory_set"))
    if accessory_source:
        if frappe.db.exists(ACCESSORY_SET, accessory_source):
            accessory_code = (_clean(options.get("accessory_set"))
                              or new_code + "-ACC")
            accessory_doc = frappe.get_doc(ACCESSORY_SET, accessory_source)
            # Bộ phụ kiện cũng trỏ tới 1 bộ biến ⇒ phải trỏ sang bộ biến MỚI
            # cùng lúc, nếu không bộ mới vẫn dùng chung biến với bộ mẫu.
            repoint = {}
            accessory_variable = _clean(accessory_doc.get("variable_set"))
            if accessory_variable:
                if accessory_variable == variable_source:
                    repoint["variable_set"] = variable_code
                else:
                    warnings.add(
                        "Bộ phụ kiện mẫu “%s” đang trỏ tới bộ biến “%s” (khác "
                        "bộ biến của bộ mẫu) — bộ phụ kiện mới vẫn giữ liên "
                        "kết đó. Kiểm tra lại nếu cần tách hẳn."
                        % (accessory_source, accessory_variable))
            plan.append(_plan_row(
                ACCESSORY_SET, accessory_source, accessory_code,
                base_name + " — Phụ kiện",
                len(accessory_doc.get("items") or []),
                extra={"repoint": repoint}))
        else:
            warnings.add(
                "Bộ mẫu đang trỏ tới bộ phụ kiện “%s” nhưng bộ này không còn "
                "tồn tại — bộ mới sẽ không có bộ phụ kiện. Kiểm tra lại bộ mẫu."
                % accessory_source)

    cost_sources = _cost_template_sources(source_name, warnings)
    cost_codes = _cost_template_codes(
        new_code, options.get("cost_template"), len(cost_sources), warnings)
    for index, cost_source in enumerate(cost_sources):
        if not frappe.db.exists(COST_TEMPLATE, cost_source):
            warnings.add(
                "Bộ mẫu có trỏ tới bộ giá “%s” nhưng bộ giá này không còn — "
                "bỏ qua, bộ mới sẽ chưa có mẫu tính giá." % cost_source)
            continue
        suffix = (" — Bộ giá" if len(cost_sources) == 1
                  else " — Bộ giá %d" % (index + 1))
        plan.append(_plan_row(
            COST_TEMPLATE, cost_source, cost_codes[index],
            base_name + suffix,
            len(frappe.get_doc(COST_TEMPLATE, cost_source).get("items") or [])))

    if cost_sources:
        warnings.add(
            "Bộ giá mới chưa nối vào sản phẩm nào. Tạo (hoặc mở) sản phẩm cho "
            "bộ mới rồi chọn Bộ BOM mới và Mẫu tính giá mới ở đó.")
    else:
        warnings.add(
            "Bộ mẫu chưa gắn mẫu tính giá nên bộ mới cũng chưa có — nhớ chọn "
            "mẫu tính giá cho sản phẩm mới trước khi tính giá.")

    item_code = _clean(source.get("item_code"))
    if item_code:
        warnings.add(
            "Bộ mới đang giữ nguyên Mã sản phẩm “%s” của bộ mẫu. Nếu đây là "
            "sản phẩm khác, mở bộ mới và chọn Mã sản phẩm mới — hai bộ cùng "
            "một sản phẩm sẽ gây nhầm khi tính giá." % item_code)
    return plan


def _assert_codes_free(plan):
    """Mã trùng ⇒ dừng trước khi tạo BẤT KỲ bộ nào (⛔ tạo nửa vời)."""
    used = {}
    for item in plan:
        doctype, code = item["doctype"], item["code"]
        if not code:
            _abort("Có bộ chưa có mã mới. Nhập mã cho tất cả các bộ rồi thử lại.")
        if (doctype, code) in used:
            _abort("Mã %s “%s” vừa dùng cho hai bộ trong cùng lần tạo — chọn "
                   "mã khác cho mỗi bộ." % (_KIND_LABEL[doctype], code))
        used[(doctype, code)] = True
        if frappe.db.exists(doctype, code):
            _abort("Mã %s “%s” đã có. Chọn mã khác."
                   % (_KIND_LABEL[doctype], code))


def _dry_run_result(plan, source_payload, warnings):
    """Kế hoạch — ⛔ insert gì. `name` dự phòng = mã mới (autoname theo mã)."""
    created = [{
        "doctype": item["doctype"],
        "name": item["code"],
        "code": item["code"],
        "rows": item["rows"],
    } for item in plan]
    return {
        "ok": True,
        "dry_run": True,
        "created": created,
        "source": source_payload,
        "warnings": warnings.as_list(),
    }


# ══════════════════════════════════════════════════════════════════════
# Thực thi
# ══════════════════════════════════════════════════════════════════════
def _created_row(doc, plan_row):
    return {
        "doctype": doc.doctype,
        "name": doc.name,
        "code": plan_row["code"],
        "rows": len(doc.get("items") or []),
    }


def _clone_document(doctype, source_name, code, new_name, provenance, warnings,
                    extra=None):
    """Nhân bản 1 chứng từ (copy_doc theo meta) rồi đặt mã mới trước insert."""
    source = frappe.get_doc(doctype, source_name)
    return _insert_clone(source, code, new_name, provenance, warnings, extra)


def _insert_clone(source, code, new_name, provenance, warnings, extra=None):
    code_field, name_field = _KIND_META[source.doctype]
    doc = frappe.copy_doc(source)
    doc.name = None
    doc.set(code_field, code)
    if name_field:
        doc.set(name_field, new_name)
    for fieldname, value in (extra or {}).items():
        doc.set(fieldname, value)
    _apply_provenance(doc, provenance, warnings)
    doc.insert()
    return doc


def _repoint_links(bom_doc, plan):
    """Bộ BOM mới phải trỏ sang bộ con MỚI, ⛔ dùng chung bộ của bộ mẫu.

    Bộ con không được nhân bản (nguồn trỏ tới bộ đã bị xoá) ⇒ **xoá liên kết**
    chứ ⛔ giữ Link trỏ tới bản ghi không tồn tại: giữ lại là insert hỏng, còn
    bỏ trống thì bộ vẫn dùng được và người dùng chọn lại sau.
    """
    planned = {item["doctype"]: item["code"] for item in plan}
    bom_doc.set("default_accessory_set", planned.get(ACCESSORY_SET))
    bom_doc.set("variable_set", planned.get(VARIABLE_SET))


def _execute_plan(plan, source_set_code, warnings):
    bom_plan = plan[0]
    created = []
    try:
        for item in plan[1:]:
            doc = _clone_document(
                item["doctype"], item["source"], item["code"], item["name"],
                item["source"], warnings,
                extra=(item.get("extra") or {}).get("repoint"))
            created.append(_created_row(doc, item))

        # Bộ BOM tạo SAU CÙNG: các Link `default_accessory_set` / `variable_set`
        # chỉ hợp lệ khi bộ con đã tồn tại.
        source = frappe.get_doc(BOM_SET, source_set_code)
        bom_doc = frappe.copy_doc(source)
        bom_doc.name = None
        bom_doc.set("set_code", bom_plan["code"])
        bom_doc.set("set_name", bom_plan["name"])
        _repoint_links(bom_doc, plan)
        _apply_provenance(
            bom_doc, source_set_code, warnings)
        bom_doc.insert()
        created.insert(0, _created_row(bom_doc, bom_plan))
    except Exception:
        if not created:
            raise
        done = ", ".join("%s “%s”" % (_KIND_LABEL[row["doctype"]], row["code"])
                         for row in created)
        # Chi tiết kỹ thuật (có thể là "Duplicate entry ...") chỉ vào log.
        frappe.log_error(
            frappe.get_traceback(),
            "AlumGlass B9: tạo bộ BOM thất bại sau khi đã tạo bộ con")
        frappe.throw(
            "Không tạo xong bộ mới. Đã tạo trước đó: %s. Xoá các bộ này rồi "
            "thử lại (chi tiết đã ghi vào nhật ký lỗi)." % done)

    source_payload = _source_payload(
        BOM_SET, source_set_code, source_set_code,
        _clean(source.get("set_name")))
    return {
        "ok": True,
        "dry_run": False,
        "created": created,
        "source": source_payload,
        "warnings": warnings.as_list(),
    }


# ══════════════════════════════════════════════════════════════════════
# API nội bộ (dùng bởi alumglass/api/product_clone.py)
# ══════════════════════════════════════════════════════════════════════
def clone_product(source_set_code, new_code, new_name=None, options=None,
                  dry_run=False):
    """Nhân bản 1 bộ mẫu thành bộ mới độc lập (Bom Set + bộ con nếu có).

    Tham số:
      · ``source_set_code`` — mã `AL Bom Set` nguồn.
      · ``new_code`` — mã bộ BOM mới (autoname). Trùng ⇒ ném lỗi, ⛔ tự thêm số.
      · ``new_name`` — tên bộ mới; rỗng ⇒ giữ tên bộ nguồn.
      · ``options`` — dict (hoặc JSON string) cho phép đổi mã từng bộ con:
        ``accessory_set``, ``variable_set``, ``cost_template``
        (chuỗi hoặc danh sách chuỗi, theo thứ tự bộ giá phát hiện được).
      · ``dry_run`` — True ⇒ chỉ trả kế hoạch, ⛔ insert gì.

    Trả dict: ``{ok, dry_run, created: [{doctype, name, code, rows}],
    source: {...}, warnings: [...]}``.
    """
    source_set_code = _clean(source_set_code)
    new_code = _clean(new_code)
    if not source_set_code:
        _abort("Chưa chọn bộ mẫu cần nhân bản.")
    if not new_code:
        _abort("Chưa nhập mã cho bộ mới. Đây là mã bộ BOM và không được trùng "
               "với bộ đang có.")
    if not frappe.db.exists(BOM_SET, source_set_code):
        _abort("Không tìm thấy bộ mẫu “%s”." % source_set_code)

    raw_options = options
    options = _normalize_options(options)
    warnings = _Warnings()
    _warn_unknown_options(raw_options, warnings)
    source = frappe.get_doc(BOM_SET, source_set_code)
    plan = _build_plan(source, new_code, new_name, options, warnings)
    _assert_codes_free(plan)

    if dry_run:
        return _dry_run_result(
            plan,
            _source_payload(BOM_SET, source_set_code, source_set_code,
                            _clean(source.get("set_name"))),
            warnings)
    return _execute_plan(plan, source_set_code, warnings)


# ══════════════════════════════════════════════════════════════════════
# Nhân bản từ snapshot của AL BOM Version
# ══════════════════════════════════════════════════════════════════════
def _filter_row_for_meta(doctype, row):
    """Bỏ field hệ thống + field không còn trên DocType; trả (row, số bỏ)."""
    data = {key: value for key, value in dict(row).items()
            if key not in _SYSTEM_ROW_FIELDS}
    try:
        meta = frappe.get_meta(doctype)
        allowed = {field.get("fieldname")
                   for field in (meta.get("fields") or [])}
    except Exception:
        allowed = set()
    if not allowed:
        return data, 0
    filtered = {key: value for key, value in data.items() if key in allowed}
    return filtered, len(data) - len(filtered)


def _read_snapshot(version, version_name):
    """Đọc + kiểm `bom_set_snapshot`. Snapshot hỏng ⇒ NÉM LỖI, ⛔ dùng bộ sống."""
    raw = version.get("bom_set_snapshot")
    if raw is None or raw == "" or raw == {} or raw == []:
        _abort(
            "Phiên bản “%s” không có dữ liệu bộ BOM (bom_set_snapshot trống) — "
            "không tạo được sản phẩm từ mẫu. Chọn phiên bản khác, hoặc dùng "
            "nút “Tạo sản phẩm từ bộ này” trên chính bộ BOM."
            % version_name)
    if isinstance(raw, (dict, list)):
        snapshot = raw
    else:
        try:
            snapshot = json.loads(raw)
        except Exception:
            _abort(
                "Dữ liệu bộ BOM trong phiên bản “%s” không đọc được. Không "
                "tạo gì — nhờ quản trị kiểm tra lại phiên bản này."
                % version_name)
    if not isinstance(snapshot, dict):
        _abort(
            "Dữ liệu bộ BOM trong phiên bản “%s” sai định dạng. Không tạo gì."
            % version_name)
    rows = snapshot.get("items") or []
    if not rows:
        _abort(
            "Phiên bản “%s” có dữ liệu bộ BOM nhưng không có dòng BOM nào — "
            "không tạo được sản phẩm từ mẫu." % version_name)
    return snapshot


def clone_from_version(version_name, new_code, new_name=None, options=None,
                       dry_run=False):
    """Tạo `AL Bom Set` mới từ snapshot của 1 `AL BOM Version`.

    Nguồn dòng là ``bom_set_snapshot`` (dữ liệu đã chốt lúc tạo version), ⛔
    đọc bộ đang sống: bộ sống có thể đã bị sửa sau khi version được chốt, và
    người dùng chọn version chính là để tái lập đúng số liệu lịch sử đó.

    Snapshot trống / hỏng ⇒ ném lỗi tiếng Việt rõ ràng, ⛔ rơi im lặng sang
    bộ đang sống.

    Kết quả cùng cấu trúc với `clone_product`.
    """
    version_name = _clean(version_name)
    new_code = _clean(new_code)
    if not version_name:
        _abort("Chưa chọn phiên bản BOM để tạo sản phẩm.")
    if not new_code:
        _abort("Chưa nhập mã cho bộ mới. Đây là mã bộ BOM và không được trùng "
               "với bộ đang có.")
    _normalize_options(options)
    if not frappe.db.exists(BOM_VERSION, version_name):
        _abort("Không tìm thấy phiên bản BOM “%s”." % version_name)

    version = frappe.get_doc(BOM_VERSION, version_name)
    snapshot = _read_snapshot(version, version_name)
    warnings = _Warnings()

    base_name = (_clean(new_name) or _clean(snapshot.get("set_name"))
                 or new_code)
    rows = snapshot.get("items") or []
    plan = [_plan_row(BOM_SET, version_name, new_code, base_name, len(rows))]
    _assert_codes_free(plan)

    source_payload = _source_payload(
        BOM_VERSION, version_name, _clean(snapshot.get("set_code")),
        _clean(snapshot.get("set_name")),
        {"snapshot_rows": len(rows)})

    warnings.add(
        "Bản snapshot không lưu liên kết bộ phụ kiện / bộ biến / bộ giá — bộ "
        "mới chỉ có bảng dòng BOM. Mở bộ mới để chọn lại nếu sản phẩm cần.")
    warnings.add(
        "Bản snapshot không lưu Mã sản phẩm (item_code) — bộ mới để trống ô "
        "này. Mở bộ mới để chọn sản phẩm tương ứng.")

    if dry_run:
        return _dry_run_result(plan, source_payload, warnings)

    doc = frappe.new_doc(BOM_SET)
    doc.set("set_code", new_code)
    doc.set("set_name", base_name)
    for fieldname in ("product_type", "profile_system"):
        value = snapshot.get(fieldname)
        if value:
            doc.set(fieldname, value)

    dropped = 0
    for row in rows:
        filtered, dropped_here = _filter_row_for_meta("AL Bom Item", row)
        dropped += dropped_here
        # Tạo Document con tường minh rồi append — ⛔ đưa dict thô vào bảng con
        # (dict thô chỉ đúng khi Frappe tự ép; làm rõ ở đây cho chắc).
        row_data = {"doctype": "AL Bom Item"}
        row_data.update(filtered)
        doc.append("items", frappe.get_doc(row_data))
    if dropped:
        warnings.add(
            "Bỏ qua %d ô trong snapshot không còn tồn tại trên bộ BOM hiện "
            "tại (field đã bị gỡ khỏi hệ thống)." % dropped)

    # Nguồn gốc người-đọc-được: tên phiên bản, ⛔ "DocType:tên".
    _apply_provenance(doc, version_name, warnings)
    try:
        doc.insert()
    except Exception:
        # Chi tiết kỹ thuật vào log; người dùng chỉ thấy câu hành động được.
        frappe.log_error(
            frappe.get_traceback(),
            "AlumGlass B9: tạo từ phiên bản %s thất bại" % version_name)
        _abort("Không tạo được bộ mới từ phiên bản “%s”. Thử lại; nếu vẫn "
               "lỗi, báo quản trị (chi tiết đã ghi vào nhật ký lỗi)."
               % version_name)

    return {
        "ok": True,
        "dry_run": False,
        "created": [_created_row(doc, plan[0])],
        "source": source_payload,
        "warnings": warnings.as_list(),
    }
