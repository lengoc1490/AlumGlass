# CHANGELOG v28_14 — Variable Catalog / Variable Profile

> **Mốc code tài liệu này mô tả**
>
> | | |
> |---|---|
> | App | `alumglass` — nhánh `main`, HEAD `90892c1` (2026-11-12) **+ thay đổi v28_14 chưa commit** |
> | Repo liên quan | `formula_builder` — nhánh `develop`, thay đổi đi kèm **chưa commit** |
> | Phạm vi | Toàn bộ bản vá v28_14: data model, catalog engine, API, UI, engine, seed |
> | Đối tượng | DEV bảo trì, người triển khai, người review |
> | Ngày soạn | 2026-11-12 |
>
> **Mức kiểm chứng:** ⛔ **chưa chạy `bench migrate`, chưa chạy test Frappe/unittest trên site**
> (bench hiện không có site nào cài `alumglass`). Theo ghi nhận của DEV tại
> `../../nguon_bien_tham_chieu.md` §10A, đã chạy: `py_compile` toàn bộ Python sửa/mới,
> `json.load` toàn bộ JSON của `alumglass`, `node --check` 3 file JS,
> `ruff --select E9,F`, và test thuần:
>
> | Bộ test | Số ca | Kết quả |
> |---|---|---|
> | `alumglass/tests/test_variable_catalog_rules.py` | 41 | PASS |
> | `formula_builder/tests/test_dollar_normalize.py` | 15 | PASS |
> | `formula_builder/tests/test_live_context_dedupe.py` | 11 | PASS |
>
> Test thuần **không** chứng minh được hành vi UI, quyền, hay tích hợp DB. ⛔ Đừng đọc
> "41 PASS" thành "đã chạy được trên site".

---

## 1. Tóm tắt

v28_14 thêm một **lớp danh mục biến (catalog)** cho Formula Builder của AlumGlass:

- Mỗi doctype mẹ có **một** field `variable_profile`.
- Profile khai **rule Include/Exclude** theo nguồn, tiền tố, regex, category, kiểu,
  field đang sửa, và có giá trị hay không.
- Catalog chạy **adapter** cho từng nguồn, áp rule, dedup, gom nhóm, và trả
  `variables` + `groups` + `references` + `meta`.
- **Profile chỉ lọc gợi ý.** Validate dùng universe đầy đủ; runtime không đọc profile.

Đồng thời dẹp 3 danh sách từng nằm cứng: registry field công thức (JS), row literal và
common variable (Python).

---

## 2. Thay đổi theo nhóm

### 2.1 Mô hình dữ liệu — 7 DocType mới, module `AL Master Data`

| DocType | Loại | Vai trò |
|---|---|---|
| `AL Variable Profile` | Master (`autoname = field:profile_code`) | 1 profile = 1 bộ biến cho 1 ngữ cảnh; `default_action` `INCLUDE_ALL` / `EXCLUDE_ALL` |
| `AL Variable Profile Rule` | Child | Luật Include/Exclude (13 cột — xem [huong-dan-setting-bien.md](huong-dan-setting-bien.md) mục 2) |
| `AL Variable Cross Row` | Child của Profile | Khai bảng con + `id_field` + `label_field` + `fields` cho `items.<slug>.<field>` |
| `AL Variable Settings` | Single | `default_profile`, `preview_doctype`, `common_variables`, `row_literals` |
| `AL Common Variable` | Child của Settings | Biến người dùng nhập (thay danh sách cứng 8 tên) |
| `AL Row Literal` | Child của Settings | Biến engine inject theo dòng (thay danh sách cứng 9 tên) |
| `AL Formula Field` | Master (`autoname = hash`) | Sổ đăng ký field công thức (thay `FORMULA_DOCTYPE_REGISTRY` trong JS) |

**Field mới `variable_profile` (Link → `AL Variable Profile`) trên 4 doctype:**

| DocType | Áp cho |
|---|---|
| `AL Bom Set` | Field cha + mọi dòng `items` |
| `AL Cost Template` | Các dòng `items` (`calc_formula`) |
| `AL Accessory Set` | `qty_formula` + gợi ý chéo dòng |
| `AL Alert Config` | `trigger_condition` |

Chi tiết `AL Formula Field`: `target_doctype` (**⛔ không phải `doctype`** — từ khoá dành
riêng của Frappe), `child_table`, `fieldname`, `id_field`, `editor_opts` (JSON),
`sort_order`, `is_active`.

### 2.2 Catalog engine — package mới `alumglass/variable_sources/`

| Tệp | Vai trò |
|---|---|
| `registry.py` | Đăng ký adapter bằng decorator; `order` quyết định ưu tiên khi dedup hoà |
| `rules.py` | **Thuần Python, không import frappe**: Include/Exclude, prefix, regex, category, kiểu, `only_fields` (giao phạm vi), `require_value`, dedupe, gom nhóm |
| `context.py` | Nạp doc/meta/dòng con/Settings **một lần** mỗi lượt; chịu được doc chưa lưu, cột chưa migrate, thiếu app |
| `adapters.py` | 10 adapter + `build_references()` cho cross-row |

**10 adapter** (đăng ký trước → ưu tiên cao hơn khi dedup hoà):

| Order | `source_kind` | Nguồn |
|---|---|---|
| 10 | `fvb_scope` | Formula Variable Binding (scope cha + dòng con) |
| 20 | `cost_bucket` | `AL Cost Bucket` |
| 30 | `variable_library_system` | `AL Variable Library` (`is_system=1`) |
| 40 | `variable_library_user` | `AL Variable Library` (`is_system=0`) |
| 45 | `variable_set` | `AL Variable Set` |
| 50 | `cost_template_line` | `AL Cost Template.items.line_code` (chỉ dòng trước) |
| 55 | `formula_global` | `Formula Global Variable` |
| 60 | `row_literal` | `AL Variable Settings.row_literals` |
| 70 | `common_var` | `AL Variable Settings.common_variables` |
| 80 | `doctype_field` | Field vô hướng của doctype/dòng |

`slug_reference` là `source_kind` thứ 11 nhưng **không có adapter** — nó điều khiển phần
`references`.

**Cách thêm nguồn mới (không sửa engine):**

1. Viết 1 hàm trong `adapters.py`, gắn `@register_adapter("ten_nguon", label=..., order=...)`.
2. Thêm option `ten_nguon` vào `source_kind` của `AL Variable Profile Rule`.
3. Khai rule trong profile.

`rules.py` và `variable_catalog.py` không phải sửa.

### 2.3 API mới

| API | Vai trò |
|---|---|
| `get_variable_catalog` | Danh mục cho 1 field/ngữ cảnh |
| `preview_variable_catalog` | Admin xem trước 1 profile (kiểm quyền `AL Variable Profile`) |
| `explain_variable` | Vì sao thấy/không thấy 1 biến; nguồn nào thắng |
| `get_variable_profile` | Profile đang áp cho bản ghi |
| `get_row_literal_names` | Tên row literal đang bật (cho cảnh báo `rule_input_expr`) |
| `get_formula_fields` | Registry field công thức (thay danh sách cứng trong JS) |

Xem đầy đủ tham số/shape: [api-reference.md](api-reference.md).

### 2.4 UI

| Tệp | Thay đổi |
|---|---|
| `public/js/formula_setup.js` | Bỏ `FORMULA_DOCTYPE_REGISTRY` cứng; registry đọc từ `AL Formula Field` qua `get_formula_fields`; cache context **theo `doctype::docname::child_table`, TTL 5 phút**; gửi `fieldname`, `child_table`; lọc `only_fields`/`hide_all` ở client; nạp ở sự kiện `form-refresh` |
| `public/js/cost_template.js` | Bỏ lọc `source` cũ (làm mất bucket/system); cache **theo docname**; tách `fetchValidationContext()` dùng `include_all_sources=1` |
| `al_master_data/doctype/al_variable_profile/al_variable_profile.js` | Nút **Xem trước danh sách biến**, render theo nhóm + nguồn + cảnh báo trùng tên |
| `al_bom_engine/doctype/al_cost_template/al_cost_template.js` | Dùng context theo bản ghi; validate đúng universe |

`hooks.py` bump `formula_setup.js` và `cost_template.js` lên `v=1.2.0`.

### 2.5 Tích hợp engine / validate

| Tệp | Thay đổi |
|---|---|
| `api/__init__.py::get_formula_context` | Thêm `fieldname`, `child_table`, `row_index`, `include_all_sources`; 2 đường (catalog / legacy); dedup lấy giá trị từ entry sau nếu entry đầu rỗng + ghi `meta.duplicates`; `_settings_variable_entries` đọc Settings thay tuple cứng |
| `al_bom_engine/formula_validate.py` | `build_known_names` dùng `include_all_sources=True`; thêm `validate_rule_input_expr` (cảnh báo, ⛔ không chặn) |
| `al_bom_engine/doctype/al_bom_set/al_bom_set.py` | Cảnh báo cam cho `items.<slug>.<field>` sai trong `rule_input_expr` |
| `al_bom_engine/doctype/al_accessory_set/al_accessory_set.py` | Validate chấp nhận cross-row; field lấy từ meta `AL Accessory Item` |
| `engine/bom_orchestrator.py` | Hợp đồng ưu tiên B1 ghi rõ; `extra_vars` + top-level cùng lớp user; snapshot/áp lại user input sau 1.5c |
| `al_bom_engine/system_variable_resolver.py` | `source_link_field` khai tường minh; fallback auto-discover; chịu được cột chưa migrate |
| `formula_builder` (repo khác) | `$NAME` normalize về `NAME`; `get_live_context` trả `applies_to_field` + gộp scope field; `get_all_global_variables` lọc `is_active=1` |

### 2.6 Mười một lỗi đã vá

Nguồn: `../../nguon_bien_tham_chieu.md` §6.2. Cột "Sửa ở đâu" chỉ đường dẫn, ⛔ không chép mã.

| # | Vấn đề | Sửa ở đâu |
|---|---|---|
| 1 | `applies_to_field` không có tác dụng vì widget không gửi `fieldname` | `api/__init__.py`, `formula_setup.js`, `adapters.py` (gắn `only_fields`) |
| 2 | Dedup "first wins" che giá trị thật | `rules.dedupe_candidates`; `api/__init__.py` lấy giá trị entry sau + `meta.duplicates` |
| 3 | Cost Template thấy toàn bộ user var | Seed `P_COST_TEMPLATE_DEFAULT` (`EXCLUDE_ALL`) |
| 4 | `cost_template.js` lọc sai theo `v.source` | Bỏ lọc, inject toàn bộ `ctx.variables` |
| 5 | `FORMULA_DOCTYPE_REGISTRY` hardcode trong JS | `AL Formula Field` + `get_formula_fields` |
| 6 | Row literal / common var hardcode | `AL Variable Settings`; tuple cũ chỉ là fallback |
| 7 | Offset mapping hardcode 4 tên | Đọc `AL Variable Library.source_field` / `source_link_field` |
| 8 | `AL Accessory Set.variable_set` là field chết | Adapter `variable_set` đọc Link trực tiếp |
| 9 | 1.5c ghi đè biến user vừa sửa khi đổi profile | Snapshot + áp lại sau 1.5c |
| 10 | `extra_vars` bị Global Variable đè | `extra_vars` + top-level cùng lớp user |
| 11 | Global Variable tắt vẫn vào `inputs` | Lọc `is_active=1` |

Phụ chú: `panel_count_formula` / `qty_per_panel_formula` trên `AL Bom Item` **cố ý**
không đăng ký — không engine nào đọc.

### 2.7 Seed và migration

Patch `alumglass.patches.v28_14.seed_variable_catalog`, khai ở **`[post_model_sync]`**
(`alumglass/patches.txt`):

| Bước | Nội dung | Tính idempotent |
|---|---|---|
| Settings | Seed 8 `common_variables` + 10 `row_literals` (có `max_area_m2`) | `common_variables` chỉ seed khi bảng **rỗng**; `row_literals` bổ sung theo **tên** còn thiếu |
| Formula Field | Seed **11** record | Bỏ qua nếu bộ `(target_doctype, child_table, fieldname)` đã có |
| Profile | Seed `P_COST_TEMPLATE_DEFAULT`, `P_ACCESSORY_DEFAULT` | Bỏ qua nếu mã đã tồn tại; ⛔ không đè cấu hình admin đã sửa |
| Gán profile | Gán cho record **đang trống** `variable_profile` của `AL Cost Template` / `AL Accessory Set` | Chỉ gán khi cột tồn tại; `update_modified=False` |

⛔ Patch **không** set `AL Variable Settings.default_profile` — mọi doctype khác giữ legacy.

---

## 3. Các bước triển khai

### 3.1 Trước khi chạy

- [ ] Backup site (chuẩn trước mọi migrate).
- [ ] Xác nhận site có **cả** `alumglass` và `formula_builder`.
- [ ] Đọc `git status`: toàn bộ v28_14 đang ở working tree, **chưa commit** — chốt bản để
      triển khai trước khi chạy.
- [ ] Chọn **site dev**; ⛔ không chạy thử trên production.

### 3.2 Chạy

```bash
bench --site <dev> migrate
bench build --app alumglass
bench --site <dev> clear-cache
```

### 3.3 Kiểm sau khi chạy

| Kiểm | Kỳ vọng |
|---|---|
| `AL Variable Settings` | 8 common var, 10 row literal |
| `AL Formula Field` | 11 record `is_active=1` |
| `AL Variable Profile` | 2 profile mẫu |
| Patch Log | Có `alumglass.patches.v28_14.seed_variable_catalog` |
| `AL Cost Template` cũ | `variable_profile` đã gán nếu trước đó trống |
| Mở form, gõ thử | Autocomplete theo profile; ⛔ không trắng form |
| Lưu công thức dùng biến ngoài profile | **Phải lưu được** |

### 3.4 Nếu patch đã ghi sổ nhưng thiếu dữ liệu

Patch idempotent nên chạy lại được:

```bash
bench --site <dev> execute alumglass.patches.v28_14.seed_variable_catalog.execute
```

Nếu báo "chưa có doctype 'AL Variable Profile'": kiểm `alumglass/patches.txt` — patch phải
nằm trong khối `[post_model_sync]`, không phải `[pre_model_sync]`.

---

## 4. Tương thích ngược

| Trạng thái | Hành vi |
|---|---|
| Bản ghi **chưa** gán `variable_profile` | Đường legacy 8 nhóm — **giống hệt trước v28_14** |
| Profile `is_active=0` | Bị bỏ qua, rơi về legacy |
| Profile `INCLUDE_ALL`, không rule | Chạy tất cả adapter, không lọc — gần như hành vi cũ |
| Công thức cũ dùng biến ngoài profile | **Vẫn lưu được** (validate dùng `include_all_sources=True`) |
| Runtime tính giá | **Không đọc profile** — số tiền không đổi |
| `AL Accessory Set.variable_set` | Trước là field chết; nay adapter dùng. Không đổi dữ liệu |
| Code cũ gọi `get_formula_context(doctype, docname)` | Vẫn chạy; tham số mới đều optional |
| Site chưa migrate | Code có fallback: thiếu bảng ⇒ legacy/rỗng; thiếu cột ⇒ query cột cũ |

> 🔴 Tuyên bố trung tâm: **bật/tắt/sửa/xoá profile không làm đổi giá trị tính toán.**
> Nếu quan sát thấy số tiền đổi sau khi sửa profile, đó là **lỗi hồi quy** — báo DEV kèm
> bản ghi và profile, ⛔ đừng "sửa" bằng cách nới rule.

---

## 5. Giới hạn đã biết

| # | Giới hạn | Ảnh hưởng | Ghi chú |
|---|---|---|---|
| 1 | **Chưa chạy migrate / test trên site** | Chưa có bằng chứng UI + DB chạy đúng | Chỉ test thuần + kiểm tra tĩnh |
| 2 | Patch **gán profile hàng loạt** cho mọi record đang trống | Đổi danh sách gợi ý của dữ liệu cũ | Chỉ là gợi ý, không đổi tiền; nên xem trước 1 record thật trước khi chạy production |
| 3 | **Chưa có cache server** cho kết quả catalog | Mỗi lượt gọi chạy lại adapter; nhiều query | Client cache 5 phút; `get_cached_doc` chỉ cache document, ⛔ không cache catalog |
| 4 | Phân quyền 3 DocType cấu hình chỉ `System Manager` | BOM Manager không tự cấu hình được | Phải cấp quyền có chủ đích |
| 5 | `invalidate()` ở client **chưa có chỗ gọi** | Sửa profile phải chờ TTL 5 phút hoặc F5 | Xem `troubleshooting.md` 2.5 |
| 6 | `explain_variable` chạy **tất cả** adapter | Chậm hơn catalog | Chỉ dùng chẩn đoán |
| 7 | Autocomplete bulk không gửi `fieldname` lên server | Server không lọc rule theo field, nhưng vẫn trả `only_fields`/`hide_all` để **client lọc** theo field đang sửa | Cố ý; API có `fieldname` thì server lọc. Muốn mỗi field một danh sách: **tách biến giữa các rule**; nhiều rule cùng chọn một biến ⇒ lấy hợp |
| 8 | Cross-row chỉ đúng nếu field engine thật sự inject | Gợi ý sai ⇒ tính ra 0 | Accessory: ⛔ `qty_formula`; xem `huong-dan-setting-bien.md` mục 5 |
| 9 | `doctype_field` bỏ field text dài | Không gợi ý `width/height/qty` trên `AL Bom Item` | Vì chúng là **chuỗi công thức** |
| 10 | `AL Formula Field` chưa có kiểm tra field tồn tại trên doctype | Gõ sai `fieldname` ⇒ record hợp lệ nhưng vô dụng | Kiểm tay; xem `troubleshooting.md` 2.10 |
| 11 | Thay đổi `formula_builder` nằm ở repo khác, chưa commit | Triển khai phải chốt **cả hai** repo | 3 test (15 + 11) thuộc repo đó |
| 12 | `cost_template_line` chỉ lọc "dòng trước" khi API **có `row_index`** | Autocomplete bulk **không gửi `row_index`** ⇒ có thể thấy cả `line_code` dòng **sau**; tham chiếu dòng sau sẽ ra 0/vòng | Đúng khi preview/validate/gọi trực tiếp có `row_index`; xem `huong-dan-setting-bien.md` Ví dụ A |

---

## 6. Tệp đã tạo / sửa (working tree)

### 6.1 Tạo mới

```
alumglass/variable_sources/__init__.py
alumglass/variable_sources/registry.py
alumglass/variable_sources/rules.py
alumglass/variable_sources/context.py
alumglass/variable_sources/adapters.py
alumglass/api/variable_catalog.py
alumglass/api/formula_registry.py
alumglass/al_master_data/doctype/al_variable_profile/{__init__.py, .json, .py, .js}
alumglass/al_master_data/doctype/al_variable_profile_rule/{__init__.py, .json, .py}
alumglass/al_master_data/doctype/al_variable_cross_row/{__init__.py, .json, .py}
alumglass/al_master_data/doctype/al_variable_settings/{__init__.py, .json, .py}
alumglass/al_master_data/doctype/al_common_variable/{__init__.py, .json, .py}
alumglass/al_master_data/doctype/al_row_literal/{__init__.py, .json, .py}
alumglass/al_master_data/doctype/al_formula_field/{__init__.py, .json, .py}
alumglass/patches/v28_14/__init__.py
alumglass/patches/v28_14/seed_variable_catalog.py
alumglass/tests/test_variable_catalog_rules.py
```

### 6.2 Sửa

```
alumglass/api/__init__.py
alumglass/hooks.py
alumglass/patches.txt
alumglass/al_bom_engine/formula_validate.py
alumglass/al_bom_engine/system_variable_resolver.py
alumglass/engine/bom_orchestrator.py
alumglass/al_bom_engine/doctype/al_bom_set/al_bom_set.py
alumglass/al_bom_engine/doctype/al_bom_set/al_bom_set.json
alumglass/al_bom_engine/doctype/al_accessory_set/al_accessory_set.py
alumglass/al_bom_engine/doctype/al_accessory_set/al_accessory_set.json
alumglass/al_bom_engine/doctype/al_cost_template/al_cost_template.py
alumglass/al_bom_engine/doctype/al_cost_template/al_cost_template.json
alumglass/al_bom_engine/doctype/al_cost_template/al_cost_template.js
alumglass/al_ai_intelligence/doctype/al_alert_config/al_alert_config.json
alumglass/al_master_data/doctype/al_variable_library/al_variable_library.json
alumglass/public/js/formula_setup.js
alumglass/public/js/cost_template.js
nguon_bien_tham_chieu.md
docs/variable-catalog/*.md            (tài liệu này)
README.md                              (mục Variable Catalog)
```

> Danh sách lấy từ `git status` tại thời điểm soạn. Sau khi commit, đối chiếu lại —
> ⛔ đừng dùng danh sách này làm bằng chứng "đã commit".

---

## 7. Vận hành

| Việc | Cách làm |
|---|---|
| Thêm nguồn biến mới | 1 adapter + 1 option `source_kind` + rule trong profile |
| Thêm field công thức mới | 1 record `AL Formula Field` (không sửa JS) |
| Thêm common var / row literal | 1 dòng trong `AL Variable Settings` (không sửa Python) |
| Muốn danh sách gọn hơn | Tạo/sửa profile `EXCLUDE_ALL`, thêm rule Include tường minh |
| Muốn tắt tính năng cho 1 doctype | Để trống `variable_profile` và không đặt `default_profile` cho doctype đó |
| Muốn quay về hành vi cũ toàn bộ | `is_active=0` cho các profile đang dùng (không xoá dữ liệu) |

> ⛔ Chưa có kịch bản revert đã kiểm chứng (rollback patch / xoá 7 DocType). Nếu buộc phải
> revert, backup trước và gỡ theo thứ tự phụ thuộc — ⛔ đừng xoá DocType khi còn dữ liệu
> profile đang được tham chiếu.

---

## 8. Đọc tiếp

- Cách dùng và setting: [README.md](README.md) · [huong-dan-setting-bien.md](huong-dan-setting-bien.md)
- API: [api-reference.md](api-reference.md)
- Sự cố: [troubleshooting.md](troubleshooting.md)
- Bối cảnh và 11 lỗi gốc: [../../nguon_bien_tham_chieu.md](../../nguon_bien_tham_chieu.md) §6.2, §8, §10A
