"""Bộ nạp CHUNG cho biến theo dòng (B3a).

Trước bản vá, muốn có một biến theo dòng mới phải sửa 6 danh sách cứng trong
`bom_orchestrator` (weight, price, glass, material…) — thêm biến là phải nhờ
DEV. Module này đọc định nghĩa từ `AL Variable Library`
(`group_label = Row Literals`) và lấy giá trị theo `source_doctype` +
`source_field`.

PHẠM VI AN TOÀN (quan trọng — đọc trước khi sửa):
  · Hàm ở đây chỉ **điền tên CÒN THIẾU** trong `lit`. Tên đã có (17 literal
    lõi do engine dựng) ⛔ bị ghi đè ⇒ số tiền hiện tại **không đổi**.
  · Nguồn không xác định/không có field ⇒ trả `None` + lý do; caller ⛔ gán 0
    (0 là giá trị thật, gán 0 che mất lỗi cấu hình).
  · Đây là lớp THUẦN (không DB): orchestrator tự dựng `sources` từ dữ liệu đã
    nạp, nhờ vậy test được bằng bộ nhớ.
"""


def collect_defs(rows):
    """Lọc định nghĩa dùng được từ dòng `AL Variable Library`.

    Trả list `{name, label, source_doctype, source_field}` — bỏ dòng thiếu
    tên hoặc thiếu nguồn (không đoán).
    """
    defs = []
    for row in rows or []:
        name = (row.get("var_name") or "").strip()
        doctype = (row.get("source_doctype") or "").strip()
        field = (row.get("source_field") or "").strip()
        if not name or not doctype or not field:
            continue
        defs.append({
            "name": name,
            "label": row.get("var_label") or name,
            "source_doctype": doctype,
            "source_field": field,
        })
    return defs


def resolve_value(def_row, sources):
    """`(giá trị, lý do_thiếu)` cho 1 định nghĩa; `(None, "")` khi đủ.

    `sources` = `{tên doctype: dict field → giá trị}` do caller dựng từ dữ
    liệu đã prefetch (không truy vấn DB ở đây).
    """
    doctype = def_row.get("source_doctype") or ""
    field = def_row.get("source_field") or ""
    src = sources.get(doctype)
    if src is None:
        return None, "khong_co_nguon:%s" % doctype
    if field not in src:
        return None, "thieu_field:%s.%s" % (doctype, field)
    return src.get(field), ""


def fill_literals(lit, defs, sources):
    """Điền biến thiếu vào `lit` (sửa tại chỗ). Trả `(lit, missing)`.

    `missing` = list `{name, label, reason}` — caller ghi cảnh báo
    `bien_chua_co_o_buoc:<tên>:<bước>`, ⛔ im lặng.
    """
    missing = []
    for def_row in defs or []:
        name = def_row["name"]
        if name in lit:
            # Tên lõi đã có giá trị từ engine — ⛔ ghi đè (giữ số tiền cũ).
            continue
        value, reason = resolve_value(def_row, sources)
        if reason:
            missing.append({
                "name": name,
                "label": def_row.get("label") or name,
                "reason": reason,
            })
            continue
        lit[name] = value
    return lit, missing
