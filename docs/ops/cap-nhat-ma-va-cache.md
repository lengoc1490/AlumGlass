# Cập nhật mã AlumGlass trên site — và vì sao phải xoá cache

> **Dành cho:** người triển khai (DEV/DEVOP) đưa mã mới lên site dev/production.
> **Ngày:** 2026-11-23 · **Phạm vi:** app `alumglass`
> **Tệp liên quan:** `alumglass/hooks.py`, `alumglass/setup/cache_bust.py`,
> `alumglass/doctype/overrides/quotation.js`

---

## 1. Vì sao `bench restart` một mình KHÔNG đủ

Frappe **nhúng nội dung** các tệp `doctype_js` (vd `quotation.js`,
`sales_order.js`) vào **form meta** của DocType, rồi **cache nguyên object meta**
ở Redis khi site **KHÔNG** bật developer mode:

```python
# frappe/desk/form/meta.py:36-49  — get_meta()
if cached and not frappe.conf.developer_mode:
    meta = frappe.cache().hget("doctype_form_meta", doctype)
    if not meta:
        meta = FormMeta(doctype)          # ← đọc tệp JS trên đĩa, nhúng vào __js
        frappe.cache().hset("doctype_form_meta", doctype, meta)
```

Hệ quả thực tế (Owner gặp 2026-11-23): kéo mã mới + `bench restart` **vẫn chạy
JS cũ**, vì:

- `bench restart` chỉ khởi động lại tiến trình web — **không đụng Redis**;
- Redis vẫn giữ meta cũ, trong đó có **nội dung `quotation.js` cũ**.

Triệu chứng điển hình: dòng báo giá đã đổi BOM Version, nhưng **mở lại dialog
"Tham số BOM" vẫn hiện version CŨ** — vì trình duyệt đang chạy bản JS cũ.

Cách chữa: **xoá cache form meta** để lượt tải form kế tiếp dựng lại meta từ tệp
trên đĩa. Từ 2026-11-23 việc này **tự chạy sau mỗi `bench migrate`** qua hook
`alumglass.setup.cache_bust.after_migrate` (khai trong `alumglass/hooks.py`).

---

## 2. Trình tự cập nhật chuẩn

```bash
# 1) Kéo mã mới (đường deploy của dự án)
cd ~/myfrappe
git -C apps/alumglass pull

# 2) Migrate — hook after_migrate tự xoá cache form meta (Quotation, Sales Order)
#    + cache assets_json. Đây là bước BẮT BUỘC, không thay bằng restart.
bench --site <site> migrate

# 3) Chỉ khi đợt này có đổi tệp trong public/ (js/css bundle):
bench build --app alumglass

# 4) Lưới an toàn — xoá toàn bộ cache của site
bench --site <site> clear-cache
```

Sau đó trên trình duyệt:

```text
Ctrl + Shift + R          (hard reload — bỏ JS cũ trong bộ nhớ trình duyệt)
# rồi mở Console, gõ:
alumglass.__build__       → phải ra "2026-11-23"
```

> `console.info("AlumGlass quotation.js build", alumglass.__build__)` in đúng
> **1 dòng mỗi lần nạp trang** — dùng để biết trình duyệt đã nhận bản mới chưa.
> Sang đợt sửa `quotation.js` kế tiếp, nhớ **đổi ngày** trong
> `alumglass.__build__` ở đầu tệp.

---

## 3. Khi vẫn thấy mã cũ — kiểm theo thứ tự

1. **Site có bật developer mode không?**

   ```bash
   bench --site <site> console
   >>> frappe.conf.developer_mode
   ```

   - `1` → meta **không** được cache; vấn đề nằm ở trình duyệt ⇒ Ctrl+Shift+R,
     kiểm lại `alumglass.__build__`.

2. **Cache form meta đã sạch chưa?**

   ```bash
   bench --site <site> console
   >>> frappe.cache().hget("doctype_form_meta", "Quotation")
   ```

   Phải là `None` (rỗng) ngay sau `bench migrate`. Nếu vẫn là object meta ⇒
   hook chưa chạy: kiểm `bench --site <site> migrate` có lỗi không, và
   `alumglass/hooks.py` còn dòng `after_migrate = [...]` với
   `"alumglass.setup.cache_bust.after_migrate"` không.

3. **`bench build` đã chạy chưa?** Chỉ ảnh hưởng tệp trong `public/`
   (`app_include_js`). `doctype_js` **không** đi qua bundle — nó nằm trong form
   meta, nên bước 2 là bước quyết định.

4. **Trình duyệt có cache riêng không?** Thử cửa sổ ẩn danh. Nếu ẩn danh đúng
   mà cửa sổ thường sai ⇒ cache trình duyệt (`?v=` của asset hoặc hard reload).

---

## 4. Phiên bản & bump `?v=`

| Mục | Đợt 2026-11-23 | Ghi chú |
|---|---|---|
| `alumglass.__version__` | `0.0.1` → **`0.0.2`** | tăng mỗi đợt sửa |
| `alumglass.__build__` (đầu `quotation.js`) | `2026-11-23` | dấu kiểm nhanh trên site |
| `app_include_js` | **không bump** | đợt này **không** sửa tệp nào trong `app_include_js`; bump vô ích sẽ xoá cache trình duyệt của người dùng |
| `doctype_js` (`quotation.js`) | không có `?v=` | nội dung nhúng vào form meta ⇒ xoá cache qua `after_migrate` |

Nguyên tắc: **chỉ bump `?v=` cho tệp thật sự đổi nội dung**. Bump tràn lan làm
mọi người tải lại asset không cần thiết.

---

## 5. Kiểm chứng bằng test (không cần site)

```bash
cd ~/myfrappe/apps/alumglass

# Logic chọn dòng của dialog + dấu phiên bản (146 ca)
node alumglass/tests/js/test_quotation_glass_pick.js

# Hook after_migrate: xoá đúng 2 key form meta, idempotent, không ném khi cache trống
python3 standalone_tests/test_cache_bust.py
```
