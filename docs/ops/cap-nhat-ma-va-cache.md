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

### Đợt 2026-11-27 — gộp nơi cấu hình (B1 + B3b), chưa commit

| Mục | Giá trị | Ghi chú |
|---|---|---|
| B1 | engine đọc `AL Formula Field` thay `AL Bom Set.formula_fieldnames` | `bench migrate` (JSON đổi mô tả), không đổi asset |
| B3b | patch mới `v1_0.user_vars_in_default_profiles` + `CONSTANT_PERMISSIONS` | **bắt buộc `bench migrate`** — patch thêm rule hồ sơ + Custom DocPerm |
| Kiểm sau migrate | xem log migrate có `Profile … +Include · variable_library_user`; cần kiểm lại thì chạy `bench --site <site> execute alumglass.patches.v1_0.user_vars_in_default_profiles.execute` — **idempotent**, lần 2 in `đã khai … bỏ qua` | ⛔ đừng chạy để "sửa" profile admin đã cố ý Exclude: patch tự bỏ qua |
| Quyền | `Formula Global Variable` · `AL BOM Manager` = đọc/ghi/tạo/xoá | kiểm ở Role Permission Manager; ⛔ cần System Manager sửa tay |

### Đợt 2026-11-27 — một nhóm DUY NHẤT cho biến (`category` → `group_label`)

| Mục | Giá trị | Ghi chú |
|---|---|---|
| Schema | `AL Variable Library` BỎ ô **Category**; ô **Nhóm hiển thị** thành **Select** (Kích thước · Cấu hình · Màu sắc · Xuất xứ · Kỹ thuật · Thi công · Thông số nhập · System · Row Literals). Cùng đợt: `AL Slug Library.group_tag` thành **Select** (KHUNG · CANH · GLASS · NEP · KEO · GIOANG · VIT · PK) | **bắt buộc `bench migrate`** (form meta đổi) |
| Vì sao | Hai ô cùng nghĩa ⇒ hai nguồn sự thật: sửa một ô, ô kia cũ hơn, danh sách gợi ý hiện sai nhóm | quyết định của Owner 2026-11-27 |
| Patch | `v1_0.unify_variable_group` | lấy `category` → `group_label` khi nhóm rỗng; đổi nhóm cũ `BOM Input Variables` → `Thông số nhập`; dòng `Row Literals` / `Từng dòng` → nhóm `Row Literals`; `update_modified=False` |
| Kiểm sau migrate | log migrate có `Lấy từ category: N · Đổi tên nhóm cũ: N · Điền nhóm nhập: N · Row Literals: N` | mở `AL Variable Library` — ô **Nhóm hiển thị** là danh sách chọn, ⛔ còn ô Category |
| Cột DB | `tabAL Variable Library.category` **vẫn còn** (không DROP) — mã đã bỏ mọi chỗ đọc | dọn cột là việc riêng, phải đo trước |
| Mã đã đổi | `catalog_rows`, `adapters`, `api.get_rule_input_variables`, `rule_input.variable_meta`, `al_rule._sync_input_variable`, `engine/bom_orchestrator` (lọc Row Literals), patch `infer_rule_input_variable`, seed | đọc `group_label`; nhóm mặc định của biến nhập đổi thành `Thông số nhập` |
| Hằng số trùng tên | Lưu một biến hệ KHÔNG có nguồn mà trùng tên `Formula Global Variable` ⇒ form hiện cảnh báo "giá đang dùng lấy từ Formula Global Variable" | sửa ở **Formula Global Variable**, ⛔ ở ô Default Value của Thư viện biến |
| Test không cần site | `test_unify_variable_group.py` **8/8** · `test_catalog_rows.py` **9/9** · `test_b3c_usage.py` **10/10** | lệnh chạy ở §5 |

### Đợt 2026-11-27 — xoá hẳn bảng `AL Variable Settings`

| Mục | Giá trị | Ghi chú |
|---|---|---|
| Patch | `v1_0.drop_variable_settings_tables` | chạy **sau** `merge_variable_settings_into_library` |
| Làm gì | 1) chạy lại patch gộp (idempotent) · 2) **cổng chặn**: mọi `var_name` còn ở 2 bảng con phải có trong `AL Variable Library`, và nếu `default_profile` có giá trị thì phải có hồ sơ `is_default=1` · 3) xuất JSON sang `sites/<site>/private/backups/al_variable_settings_<giờ>.json` · 4) xoá DocType record + dòng `tabSingles`, **DROP** `tabAL Common Variable`, `tabAL Row Literal`, `tabAL Variable Settings` | thiếu dữ liệu ⇒ patch **dừng** kèm danh sách tên, ⛔ xoá gì |
| Backup | **bắt buộc chạy trước**: `bench --site <site> backup --with-files` | bảng đã DROP thì đường lùi duy nhất là restore backup |
| Kiểm sau migrate | log migrate có `Không xoá được` = chưa chạy; kiểm nhanh: `bench --site <site> mariadb -e "show tables like 'tabAL%Variable%'"` phải **rỗng** | còn bảng ⇒ patch chưa chạy hoặc đã throw — đọc log migrate |
| Site mới | `v28_14.seed_variable_catalog` nay seed **thẳng vào Library** (bảng Settings không còn) | log in `AL Variable Library: +N mới · M điền chỗ trống` |
| Code đã dọn | bỏ `_rows_from_settings` / `is_library_migrated` / tuple `_LEGACY_*` / nhánh `default_profile` của Single / nhánh `preview_doctype` trong JS | đọc vào bảng không tồn tại chỉ tạo lỗi SQL |

### Đợt 2026-11-27 — B2/R3 gộp `AL Variable Settings` vào Library

| Mục | Giá trị | Ghi chú |
|---|---|---|
| Schema | `AL Variable Library` +4 field (`is_input`, `group_label`, `sort_order`, `is_active`); `AL Variable Profile` +2 field (`is_default`, `preview_doctype`) | **bắt buộc `bench migrate`** |
| Patch | `v1_0.merge_variable_settings_into_library` | chép mọi dòng `common_variables` + `row_literals`; điền chỗ trống, ⛔ đè dữ liệu admin; xung đột tên với biến hệ thống ⇒ log + in cảnh báo |
| Kiểm sau migrate | log migrate có `Tạo mới: … · Điền chỗ trống: … · Xung đột: …` | xung đột > 0 ⇒ in danh sách tên, xử lý tay trước khi tin autocomplete |
| Đối chiếu bắt buộc | So **tập tên biến** ô công thức `AL Bom Set` / `AL Cost Template` trước và sau migrate; 2 mốc giá chuẩn phải khớp | chưa đo được trên máy này — cần site test |
| Màn cũ | `AL Variable Settings` đã bị **XOÁ HẲN** cùng 2 bảng con — xem đợt "xoá hẳn bảng Settings" bên dưới | ⛔ đừng khai biến ở đó nữa; DocType không còn |
| JS | `al_variable_profile.js` đổi sang đọc `preview_doctype` trên hồ sơ | Frappe tự nạp JS doctype ⇒ chỉ cần migrate/clear-cache, không `bench build` |
| B3c | `AL Variable Library` +1 field `usage` ("Dùng ở"); patch `v1_0.backfill_variable_usage` | **bắt buộc migrate** — patch điền nhãn cho biến cũ |
| B3a | `engine/row_literal_loader.py`; cảnh báo `bien_chua_co_o_buoc:<tên>:b2` | thêm biến dòng khai Library có nguồn ⇒ engine tự dùng, không sửa mã |
| B6 | Gỡ 6 ô chết khỏi JSON (`AL Bom Item` 5, `AL Color Standard` 1); `al_bom_set.js` bỏ `set_query` chết | **migrate** (form meta đổi); cột DB **KHÔNG** bị xoá |
| B6 kiểm | log migrate có `Tổng dòng có dữ liệu trong ô chết: N` (patch `count_dead_fields`) | N > 0 ⇒ dữ liệu vẫn trong cột; muốn xem lại: trả field vào JSON |
| B3c kiểm | mở `AL Variable Library` → ô **"Dùng ở"** = Toàn đơn / Từng dòng / Người dùng nhập | cờ `is_input` ẩn, tự suy; ⛔ sửa tay |

### Đợt 2026-11-27 — B7/Đ5 `calc_expr` + ô giá trị biến đúng kiểu

| Mục | Giá trị | Ghi chú |
|---|---|---|
| Schema | `AL Quantity Calc Method` +`calc_expr`; `AL Variable Set Item` +`fetch_from` cho `link_doctype`/`select_options` | **bắt buộc `bench migrate`** (form meta đổi) |
| Patch | `v1_0.backfill_calc_expr` | in `Điền mới · Giữ nguyên · Công thức riêng (bỏ qua) · Không có record`. **Công thức riêng = site tự sửa `calc_fn`** ⇒ phải chuyển tay sang ô "Công thức tính", ⛔ patch không đụng |
| Ưu tiên | engine đọc `calc_expr` trước, `calc_fn` sau | còn dùng `calc_fn` ⇒ **Error Log** ghi 1 lần/cách tính (tiêu đề `AL Quantity Calc Method còn dùng calc_fn`) — ⛔ không hiện cho người dùng |
| Asset mới | `public/js/al_variable_set_item.js?v=1.0.1` trong `app_include_js` | cần `bench build --app alumglass` + hard reload |
| Asset đổi | `al_master_data/doctype/al_variable_library/al_variable_library.js` (mới) | Frappe tự nạp doctype_js ⇒ migrate/clear-cache là đủ |
| Kiểm ô giá trị | mở `AL Variable Set` → dòng biến Select phải là **ô chọn** đúng danh sách; biến Link phải **chọn bản ghi** đúng doctype | chưa khai lựa chọn / chưa khai doctype ⇒ hệ thống giữ **ô chữ** (⛔ dựng ô rỗng khoá người dùng) |
| Test không cần site | `test_calc_expr_b7.py` **11/11** · `test_variable_set_widget.js` **20/20** | lệnh chạy ở §5 |

### Đợt 2026-11-27 — B4/B4b/B5 (một đường đọc biến, ⛔ lấy số bịa)

| Mục | Giá trị | Ghi chú |
|---|---|---|
| B4 | `variable_catalog` là đường **chính** kể cả record chưa gán hồ sơ (`all_sources`); legacy 8 nhóm chỉ chạy khi danh mục **lỗi** | log `AlumGlass get_variable_catalog failed` xuất hiện ⇒ **sự cố**, ⛔ trạng thái bình thường |
| B4 đồng bộ FVB | `fb_binding_sync.py` + API `alumglass.api.variable_catalog.sync_fb_bindings(dry_run=1)` | thêm hằng số / biến hệ xong chạy `dry_run=0` để FB resolve ngay, ⛔ đợi migrate |
| B4b | lớp resolve biến hệ **luôn** bỏ qua biến đã có giá trị | giá trị Formula Builder ⛔ bị ghi đè nữa; override `AL Profile System.system_variables` vẫn thắng |
| B5/R6 | ⛔ còn lấy số từ `AL Rule` CONSTANT khi biến hệ thiếu nguồn; cảnh báo `bien_he_chua_co_nguon:<tên>` | **đổi số ở đâu = chỗ trước đây ăn số bịa** — phải so 2 mốc giá (`22.717.289` / `47.430.808`) |
| Kiểm sau migrate | log migrate `D3 seed_fvb_from_variable_library (qua fb_binding_sync): created N, skipped M` | N tăng = có binding mới; M lớn = phần lớn đã có (bình thường) |
| Test không cần site | `test_fb_binding_sync.py` **5/5** · `test_b4_b5_one_path.py` **8/8** | kiểm cấu trúc "đường cũ ⛔ quay lại" |

### Đợt 2026-11-27 — B9/Đ2 tạo sản phẩm từ mẫu

| Mục | Giá trị | Ghi chú |
|---|---|---|
| Schema | `AL Bom Set` · `AL Accessory Set` · `AL Cost Template` · `AL Variable Set` +2 field `cloned_from` (Data) · `cloned_at` (Datetime), read-only | **bắt buộc `bench migrate`**; site chưa migrate vẫn tạo được, chỉ thiếu 2 ô nguồn gốc (có cảnh báo) |
| Nút | `AL Bom Set` → **"Tạo sản phẩm từ bộ này"** (chỉ hiện với bộ đã lưu) | `doctype_js` ⇒ cần migrate/clear-cache, ⛔ cần `bench build` |
| Hành vi | Hỏi tên mới (mã **có thể để trống** — máy tự đặt `…-MOI2`, `…-MOI3`) → **xem trước** (bộ nào, bao nhiêu dòng, cảnh báo) → xác nhận → hộp "Đã tạo" có nút **Mở bộ mới** (⛔ tự nhảy trang làm mất danh sách "Cần biết") | mã nhập tay bị trùng ⇒ báo, ⛔ tự thêm số; ⛔ tạo nửa vời; lỗi kỹ thuật (SQL/Duplicate) chỉ vào Error Log |
| Bộ giá | Nguồn là các `AL BOM` đang trỏ bộ mẫu (`AL Bom Set` không có ô bộ giá) | Bộ giá mới tạo nhưng liên kết nằm trên `AL BOM` — phải trỏ `AL BOM` của sản phẩm mới sang bộ giá mới |
| Kiểm | `test_product_clone.py` **30/30** | lệnh chạy ở §5 |

### Đợt 2026-11-27 — B8 trang "Cấu hình sản phẩm" + B10 quyền

| Mục | Giá trị | Ghi chú |
|---|---|---|
| Page mới | `al-product-config` (module AL Master Data), chỉ đọc | **bắt buộc `bench migrate`** để tạo Page; mở bằng `/app/al-product-config` |
| Lối vào | Nút **"Cấu hình sản phẩm"** trên form `AL BOM`; mục ở `workspace_sidebar/master_data.json` (chỉ có tác dụng với site còn dùng Workspace Sidebar) | ⚠ **v16 bỏ `Workspace Sidebar`** — muốn mục menu trên v16 phải export `Sidebar` từ site rồi thêm tay |
| API | `alumglass.api.product_config.get_product_config(doctype, docname)` | 7 khối; 1 khối lỗi ⛔ làm hỏng trang; mỗi khối có `state` = `ok` / `empty` (**chưa gắn** — nút "Mở sản phẩm để gắn") / `warning` (sản phẩm ngừng dùng) / `error` (nút "Tải lại"); `error` là câu tiếng Việt, ⛔ traceback; `read_at_display` dạng `27-11-2026 16:20` |
| Quyền (B10) | `AL Variable Profile` + `AL Formula Field`: AL Technical Admin đọc/ghi/tạo · AL BOM Manager **chỉ đọc** | một bảng `CONFIG_PERMISSIONS` trong `install_roles.py`; patch `v1_0.grant_config_permissions` cho site đã cài — **bắt buộc migrate** |
| Kiểm | `test_product_config.py` **22/22** · `test_product_config.js` **17/17** · `test_grant_config_permissions.py` **7/7** | lệnh chạy ở §5 |

### Đợt 2026-11-27 (tiếp) — mở danh sách `AL Variable Library` báo lỗi "không có quyền"

| Mục | Giá trị | Ghi chú |
|---|---|---|
| Triệu chứng | Mở `AL Variable Library` ⇒ `PermissionError: You do not have permission to access field: AL Variable Library.category` | **Không phải** người dùng thiếu quyền — Frappe v16 kiểm quyền trên đúng ô dùng để **sắp xếp**, thấy `category` đã bỏ thì báo như vậy |
| Nguyên nhân | Lựa chọn sắp xếp từng người lưu ở `__UserSettings` (`List.sort_by`) + bản trong Redis (`_user_settings`). `bench migrate` **không** dọn hai chỗ này | Ai từng bấm cột **Category** trước khi gộp sẽ dính; người chưa từng chạm thì không |
| Cách chữa | Patch `v1_0.repair_variable_library_list_sort` (đã khai trong `patches.txt`, chạy sau `unify_variable_group`) | Sửa `sort_by` về `group_label`, bỏ điều kiện lọc trỏ ô đã bỏ, dọn `DocType.sort_field` hỏng, xoá cache cũ; chạy lại không đổi gì |
| Chạy ngay | `bench --site <site> execute alumglass.patches.v1_0.repair_variable_library_list_sort.execute` | Không cần `bench restart`, không cần `bench build`; xong thì tải lại trang danh sách |
| Kiểm | `test_repair_variable_library_list_sort.py` **15/15** | lệnh chạy ở §5 |

### Đợt 2026-11-28 — tệp DocType con bị ghi đè: mở bảng tham số báo *"DocType … not found"*

| Mục | Giá trị | Ghi chú |
|---|---|---|
| Triệu chứng | Mở bảng tham số ở báo giá ⇒ `DocType AL Variable Set Item not found`; kèm hàng loạt `name 'OFFSET_FRAME' is not defined` và `Không tìm được dòng Item Price … 'KINH-0x'` | bộ biến không nạp được ⇒ không có tham số ⇒ giá tính thiếu, dòng kính giữ chỗ bị tra giá thật |
| Nguyên nhân | `al_variable_set_item/al_variable_set_item.json` bị **ghi đè bằng nguyên nội dung** của `al_variable_library.json` (commit `1c9874a`, 28/11 09:56) ⇒ app **không còn** DocType `AL Variable Set Item`; site migrate sau thời điểm đó không tạo được bảng con | tệp `.py` của doctype con **không** bị ảnh hưởng |
| Sửa | Khôi phục JSON đúng (9 field: `variable`, `var_label`, `column_info`, `var_type`, `link_doctype`, `select_options`, `default_value`, `sort_order`, `is_required`) | **bắt buộc `bench migrate`** trên mọi site đã migrate sau 28/11 09:56 — migrate tạo lại DocType + bảng `tabAL Variable Set Item` |
| Chặn tái diễn | `test_doctype_json_sanity.py` — `name` phải khớp tên thư mục, ⛔ trùng tên, field bảng con `AL …` phải tồn tại, `field_order` phải có trong `fields` | chạy thuần Python, ⛔ cần site |
| Câu báo lỗi công thức | `engine/formula_messages.py`: `name 'X' is not defined` → *"Chưa có giá trị cho biến …"*; tên không có trong Thư viện → *"…chưa có giá trị nào mang tên này"*; dòng kính chưa chọn kính → *"…chọn kính cho vị trí rồi tính lại"* | nguyên văn vẫn ghi vào log máy chủ để support đối chiếu |
| API dialog | `get_variable_set_for_bom` không còn để lỗi "DocType … not found" lọt ra người dùng — ghi Nhật ký lỗi + câu tiếng Việt nêu việc cần làm | ⛔ hiện bảng tham số rỗng rồi tính giá thiếu biến |
| Kiểm | `test_doctype_json_sanity.py` **7/7** · `test_formula_error_messages.py` **14/14** | lệnh chạy ở §5 |

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

# B7: 14 biểu thức calc_expr phải ra CÙNG số với 14 lambda seed + patch điền đúng chỗ
PYTHONPATH=~/myfrappe/apps/formula_builder python3 alumglass/tests/test_calc_expr_b7.py

# Ô giá trị biến hiện đúng kiểu (Select/Link/số/chữ), mỗi dòng độc lập
node alumglass/tests/js/test_variable_set_widget.js

# B4/B4b/B5: đường đọc cũ ⛔ quay lại; FVB sync idempotent
python3 alumglass/tests/test_fb_binding_sync.py
python3 alumglass/tests/test_b4_b5_one_path.py

# B9 tạo sản phẩm từ mẫu: mã mới, dòng con, nguồn gốc, dry-run, snapshot rỗng
PYTHONPATH=~/myfrappe/apps/formula_builder python3 alumglass/tests/test_product_clone.py

# B8 trang cấu hình sản phẩm + B10 quyền
PYTHONPATH=~/myfrappe/apps/formula_builder python3 alumglass/tests/test_product_config.py
python3 alumglass/tests/test_grant_config_permissions.py
node alumglass/tests/js/test_product_config.js

# Mở danh sách AL Variable Library báo "không có quyền ...category": dọn sắp xếp cũ
python3 alumglass/tests/test_repair_variable_library_list_sort.py

# DocType JSON hỏng (tên lệch thư mục, bảng con trỏ hư) + câu báo lỗi công thức
python3 alumglass/tests/test_doctype_json_sanity.py
python3 alumglass/tests/test_formula_error_messages.py
```
