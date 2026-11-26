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
alumglass.__build__       → phải ra "2026-11-23b"
```

> `console.info("AlumGlass quotation.js build", alumglass.__build__)` in đúng
> **1 dòng mỗi lần nạp trang** — dùng để biết trình duyệt đã nhận bản mới chưa.
> Sang đợt sửa `quotation.js` kế tiếp, nhớ **đổi ngày** trong
> `alumglass.__build__` ở đầu tệp.

---

## 3. Khi vẫn thấy mã cũ — kiểm theo thứ tự

0. **Trình duyệt có tự báo không?** Từ đợt 2026-11-23 có **đèn báo mã cũ**:
   `alumglass/public/js/build_beacon.js` (nạp qua `app_include_js`) so dấu
   `alumglass.__build__` của bản đang chạy với hằng
   `alumglass_build_expected` trong chính tệp đó. Lệch ⇒ toast **cam** một lần
   mỗi phiên: *"Giao diện báo giá chưa phải bản mới nhất. Báo quản trị cập nhật,
   rồi tải lại trang."* Chi tiết 2 dấu build nằm ở Console
   (`[alumglass] giao diện báo giá là bản CŨ`).
   - Có cảnh báo ⇒ làm mục 2 (cache form meta) + mục 4 (hard reload).
   - Sửa `quotation.js` đợt sau ⇒ **nâng `__build__` trong quotation.js VÀ
     `alumglass_build_expected` trong `build_beacon.js` cùng lúc**, rồi bump
     `?v=` của `build_beacon.js` trong `hooks.py`.

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

## 3.5 Phân biệt "dialog hiện version cũ" là do mã cũ hay do DÒNG cũ

Triệu chứng giống nhau, nguyên nhân khác hẳn nhau — đừng sửa mã khi thủ phạm là
dữ liệu. Mở báo giá, mở Console (F12), dán **một dòng**:

```js
(() => { const r = cur_frm.doc.items[0];
  return { build: window.alumglass && alumglass.__build__,
           dong: r.al_bom_version,
           locals: (frappe.get_doc("Quotation Item", r.name) || {}).al_bom_version,
           unsaved: !!cur_frm.doc.__unsaved }; })()
```

| Kết quả | Nghĩa | Việc phải làm |
|---|---|---|
| `build` **không phải** `2026-11-23b` | Site đang chạy JS cũ | mục 2 (migrate) + hard reload |
| `dong` **là** version mới | Dòng đã đúng ⇒ mở dialog phải hiện đúng | nếu dialog vẫn cũ ⇒ gửi Console có dòng `[alumglass] version vẫn lệch sau khi chốt` |
| `dong` **là** version cũ | Chưa hề ghi được xuống dòng | xem `unsaved` + Console `[alumglass] ghi version xong vẫn lệch` |
| `dong` mới nhưng `locals` cũ | Hai object lệch nhau | gửi Console cho DEV (lỗi thật, cần sửa) |
| `unsaved: false` mà bạn vừa sửa dialog | **Chưa Lưu báo giá** — F5 là mất, dòng về bản trong DB | bấm **Lưu** trên báo giá rồi mở lại dialog |

> Dialog chỉ ghi xuống **dòng trên form**; DB chỉ đổi khi bấm **Lưu** báo giá
> (quyết định Owner 2026-11-21). Tải lại trang mà chưa Lưu ⇒ dòng trở về bản cũ
> — đây là hành vi đúng, không phải lỗi.

---

## 4. Phiên bản & bump `?v=`

| Mục | Đợt 2026-11-23 | Ghi chú |
|---|---|---|
| `alumglass.__version__` | `0.0.2` → **`0.0.3`** | tăng mỗi đợt sửa |
| `alumglass.__build__` (đầu `quotation.js`) | **`2026-11-23b`** | dấu kiểm nhanh trên site |
| `alumglass_build_expected` (`build_beacon.js`) | **`2026-11-23b`** | phải khớp `__build__` |
| `app_include_js` | **bump `build_beacon.js?v=0.0.4`** | các asset khác giữ nguyên |
| `doctype_js` (`quotation.js`) | không có `?v=` | nội dung nhúng vào form meta ⇒ xoá cache qua `after_migrate` |

### Đợt 2026-11-25b — chặng 3 "quy tắc tự khai tra theo cái gì"

| Mục | Giá trị | Ghi chú |
|---|---|---|
| `alumglass.__version__` | giữ `0.0.3` | đợt này chỉ đổi asset JS, không đổi mã Python |
| `alumglass.__build__` (`quotation.js`) | **`2026-11-25b`** | |
| `alumglass_build_expected` (`build_beacon.js`) | **`2026-11-25b`** | phải khớp `__build__` |
| `app_include_js` | `rule_helper.js?v=1.1.0`, `al_bom_item.js?v=1.1.0`, `build_beacon.js?v=0.0.6` | 3 tệp đổi nội dung |
| `AL Bom Item` | thêm field `rule_input_row` | **phải `bench migrate`** trước khi dùng |
| `AL Rule` | thêm `input_variable` / `input_scope` (server) | cũng cần migrate |

### Đợt 2026-11-25d — vòng UX 2–3 + điều kiện tra cạnh khai báo

| Mục | Giá trị | Ghi chú |
|---|---|---|
| `alumglass.__build__` (`quotation.js`) | **`2026-11-25d`** | |
| `alumglass_build_expected` (`build_beacon.js`) | **`2026-11-25d`** | phải khớp `__build__` |
| `app_include_js` | `rule_helper.js?v=1.1.2`, `al_bom_item.js?v=1.1.2`, `al_accessory_item.js?v=1.0.1`, `build_beacon.js?v=0.0.8` | 4 tệp đổi nội dung |
| `AL Rule` | `input_help_html` + `section_*` mới; bố cục lại; nhãn field `item_rule` | **phải `bench migrate`** để form meta đổi |
| `AL Rule List` | tệp mới `al_rule_list.js` (formatter enum) | Frappe tự eval, vẫn cần migrate/clear-cache |
| `AL Rule Threshold Row` | `to_value` bỏ `reqd` (dải cuối mở = trở lên) | migrate metadata |
| `AL Variable Library` | `title_field = var_label` | Link "Tra theo" hiện nhãn |
| Python | `rule_engine.py`, `rule_input.py`, `bom_orchestrator.py`, `api/__init__.py`, `al_rule.py`, `al_bom_set.py` | restart + migrate, không chỉ build |

Lưu ý: `quotation.js` là `doctype_js` (không có `?v=`); nội dung nhúng trong form
meta ⇒ **bắt buộc `bench migrate`**, `bench build` và restart KHÔNG đủ.

### Đợt 2026-11-26 — giữ form dòng con khi đóng hộp thoại (Frappe v16)

| Mục | Giá trị | Ghi chú |
|---|---|---|
| Tệp mới | `public/js/dialog_keep_grid_form.js?v=1.0.0` | **đứng ĐẦU** `app_include_js` |
| Cơ chế | bọc `frappe.ui.Dialog`, mặc định `keep_grid_form_open: true` | v16 lõi tự đóng form dòng khi dialog ẩn, trừ cờ này; v14 bỏ qua an toàn |
| Tắt riêng | truyền `keep_grid_form_open: false` khi tạo dialog | ví dụ hộp cố ý muốn đóng dòng |
| Triển khai | `bench build --app alumglass` + restart + hard reload | không đổi DB, **không cần migrate** cho riêng đợt này |

⚠ Cờ chỉ chặn đường **đóng hộp**. Luồng bấm nút chính mà gọi
`frm.refresh_field`/`grid.refresh` có thể vẫn đóng form dòng — đó là refresh
lưới, không phải dialog.

Nguyên tắc: **chỉ bump `?v=` cho tệp thật sự đổi nội dung**. Bump tràn lan làm
mọi người tải lại asset không cần thiết.

---

## 5. Kiểm chứng bằng test (không cần site)

```bash
cd ~/myfrappe/apps/alumglass

# Logic chọn dòng của dialog + dấu phiên bản + chốt BOM Version (177 ca)
node alumglass/tests/js/test_quotation_glass_pick.js

# Đèn báo mã cũ: báo đúng 1 lần/phiên, không báo khi khớp, không đăng ký 2 lần
node alumglass/tests/js/test_build_beacon.js

# Hook after_migrate: xoá đúng 2 key form meta, idempotent, không ném khi cache trống
python3 standalone_tests/test_cache_bust.py
```
