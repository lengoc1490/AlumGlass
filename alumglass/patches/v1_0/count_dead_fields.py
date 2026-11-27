"""v1_0 — B6a/R5: ĐẾM dữ liệu trong 6 ô chết trước khi bỏ khỏi form.

Sáu ô không ai đọc (xem thiết kế §P4): 5 ô trên dòng BOM + `surcharge_rule`
của `AL Color Standard`. B6b đã gỡ chúng khỏi JSON DocType; **cột DB vẫn còn**
(⛔ không DROP), nên dữ liệu cũ vẫn đọc được bằng SQL và khôi phục được bằng
cách trả field vào JSON.

VÌ SAO CHỈ ĐẾM, ⛔ KHÔNG CHẶN MIGRATE
-------------------------------------
Bản chốt ghi "số đếm > 0 ⇒ dừng". Nếu patch này `throw`, một site có vài giá
trị cũ sẽ **chặn cả lần migrate** — trong khi việc gỡ field không làm mất dữ
liệu (cột còn nguyên). Vì vậy patch IN + GHI LOG rõ docname để người vận hành
quyết định, ⛔ không ném. Muốn khôi phục hiển thị: trả field vào JSON.

Idempotent, chỉ đọc. Chạy lại vô hại.
"""
import frappe

#: doctype → [(field, kiểu)] — `check` đếm giá trị 1; còn lại đếm chuỗi khác rỗng.
DEAD_FIELDS = {
    "AL Bom Item": [
        ("price_rule", "link"),
        ("formula_set", "link"),
        ("panel_count_formula", "text"),
        ("qty_per_panel_formula", "text"),
        ("panel_glass_override_allowed", "check"),
    ],
    "AL Color Standard": [
        ("surcharge_rule", "link"),
    ],
}

_MAX_NAMES = 20


def _where(field, kind):
    if kind == "check":
        return "ifnull(`%s`, 0) != 0" % field
    return "ifnull(`%s`, '') != ''" % field


def _count(doctype, field, kind):
    """`(số dòng, tối đa 20 docname)`; rỗng khi cột/doctype không có."""
    try:
        if not frappe.db.has_column(doctype, field):
            return None, []
        rows = frappe.db.sql(
            "select name from `tab{dt}` where {where} limit {limit}".format(
                dt=doctype, where=_where(field, kind), limit=_MAX_NAMES),
            as_dict=False,
        ) or []
        total = frappe.db.sql(
            "select count(*) from `tab{dt}` where {where}".format(
                dt=doctype, where=_where(field, kind)),
        )[0][0]
        return int(total or 0), [row[0] for row in rows]
    except Exception:
        # Lỗi hạ tầng ở bước ĐẾM không được làm hỏng migrate — ghi log, bỏ qua.
        frappe.log_error(
            "count_dead_fields: không đếm được %s.%s\n%s"
            % (doctype, field, frappe.get_traceback()),
            "AlumGlass B6a",
        )
        return None, []


def execute():
    print("v1_0 — B6a: đếm dữ liệu trong 6 ô chết (chỉ đọc)")
    total_found = 0
    for doctype, fields in DEAD_FIELDS.items():
        if not frappe.db.exists("DocType", doctype):
            print("  · %s: chưa có doctype, bỏ qua" % doctype)
            continue
        for field, kind in fields:
            count, names = _count(doctype, field, kind)
            if count is None:
                print("  · %s.%s: chưa có cột (đã DROP?) — bỏ qua"
                      % (doctype, field))
                continue
            if not count:
                print("  · %s.%s: 0 dòng có dữ liệu" % (doctype, field))
                continue
            total_found += count
            msg = ("%s.%s: %d dòng CÓ dữ liệu — ví dụ: %s"
                   % (doctype, field, count, ", ".join(names)))
            print("  ⚠ " + msg)
            # ⛔ im lặng: người vận hành phải biết dữ liệu cũ còn trong cột
            # (không hiện trên form nữa) để khôi phục nếu thật sự cần.
            frappe.log_error(msg, "AlumGlass B6a — ô chết còn dữ liệu")

    print("  · Tổng dòng có dữ liệu trong ô chết: %d" % total_found)
    print("  · Cột DB vẫn còn; muốn xem lại: trả field vào JSON DocType.")
    print("v1_0 — xong B6a")
