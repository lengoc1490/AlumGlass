"""v1_0 — B3c/Đ4: điền ô "Dùng ở" cho biến đã có, từ dữ liệu cũ.

Cột `usage` mới thêm có default "Toàn đơn" — SAI cho biến đang là biến theo
dòng (nhóm Row Literals) hoặc biến người dùng nhập (is_input=1). Patch này
suy lại cho MỌI dòng bằng đúng hàm form dùng
(`al_variable_library.derive_usage`) — ⛔ chép công thức ở hai nơi.

Vì cột vừa được thêm, mọi giá trị đang có đều là default (không phải admin
chọn tay), nên ghi đè là an toàn. Chạy lại lần 2 không đổi gì.

Ghi `update_modified=False`: đây là điền metadata kỹ thuật, không phải người
dùng sửa biến — tránh làm "modified" nhảy và nhiễu so sánh/đồng bộ.
"""
import frappe

LIBRARY = "AL Variable Library"


def execute():
    print("v1_0 — B3c: điền ô 'Dùng ở' cho AL Variable Library")
    if not frappe.db.has_column(LIBRARY, "usage"):
        print("  · %s: chưa có cột usage — bỏ qua" % LIBRARY)
        return

    from alumglass.al_master_data.doctype.al_variable_library.\
        al_variable_library import derive_usage

    fields = ["name", "usage", "is_system", "is_input", "group_label"]
    if not frappe.db.has_column(LIBRARY, "group_label"):
        fields[fields.index("group_label")] = "category"
    rows = frappe.get_all(LIBRARY, fields=fields, order_by="name asc") or []

    changed = 0
    for row in rows:
        usage = derive_usage(row.get("is_system"), row.get("is_input"),
                             row.get("group_label") or row.get("category"))
        if (row.get("usage") or "").strip() == usage:
            continue
        frappe.db.set_value(LIBRARY, row["name"], "usage", usage,
                            update_modified=False)
        changed += 1

    print("  · Đã điền: %d/%d dòng" % (changed, len(rows)))
    frappe.db.commit()
    print("v1_0 — xong B3c")
