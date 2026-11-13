# API Reference — Variable Catalog (v28_14)

> **Mốc code tài liệu này mô tả**
>
> | | |
> |---|---|
> | App | `alumglass` — nhánh `main`, HEAD `90892c1` (2026-11-12) **+ thay đổi v28_14 chưa commit** |
> | Phạm vi | Các endpoint whitelist của catalog + 2 endpoint tích hợp (`get_formula_context`, `get_formula_fields`) |
> | Đối tượng | DEV gọi API từ JS / console / tích hợp ngoài |
> | Ngày soạn | 2026-11-12 |
>
> **Mức kiểm chứng:** ⛔ **chưa gọi API trên site** — shape dưới đây đọc trực tiếp từ
> `alumglass/api/variable_catalog.py`, `alumglass/api/formula_registry.py` và
> `alumglass/api/__init__.py` của working tree. Sai khác khi chạy thật ⇒ ghi lại vào
> [troubleshooting.md](troubleshooting.md), ⛔ đừng sửa tài liệu theo phỏng đoán.

---

## 1. Quy ước chung

### 1.1 `doctype` là tham số do client gửi — luôn bị kiểm

Mọi API nhận `doctype` đều đi qua **cùng một guard**:

```python
# alumglass/api/variable_catalog.py:47-53
_assert_doctype_allowed(doctype)
  → alumglass.api._assert_formula_context_doctype(doctype)
```

Guard cho qua khi **đồng thời**:

1. `doctype` thuộc một trong:
   - module bắt đầu bằng `AL ` (mọi DocType của app AlumGlass), **hoặc**
   - module `Formula Builder`, **hoặc**
   - đúng tên `Quotation` / `Quotation Item`;
2. user có quyền **read** trên chính doctype đó.

`doctype` rỗng hoặc không tồn tại ⇒ **chặn**.

### 1.2 Tham số ngữ cảnh

| Tham số | Kiểu | Mặc định | Ý nghĩa |
|---|---|---|---|
| `doctype` | str | — | Doctype mẹ đang mở (`AL Bom Set`, `AL Cost Template`, …) |
| `docname` | str | `None` | Tên bản ghi; bỏ trống khi tạo mới hoặc chỉ muốn xem danh mục |
| `child_table` | str | `None` | Field bảng con đang sửa, ví dụ `items` |
| `row_index` | int/str | `None` | Chỉ số dòng **0-based** trong `child_table` |
| `fieldname` | str | `None` | Field công thức đang sửa — có thì **server lọc rule** theo `only_fields`; không có thì server trả `only_fields` để **client lọc** |

`row_index` nhận cả chuỗi từ query string; ép Int an toàn, sai ⇒ `None`.

### 1.3 Hai khái niệm dễ lẫn

| | `only_fields=[]` | `hide_all=true` |
|---|---|---|
| Nghĩa | **Không giới hạn** field | Ẩn ở **mọi** field |
| Do ai gắn | Nguồn hoặc rule | Server, khi giao phạm vi nguồn × rule **rỗng** |
| Có phải field cấu hình? | Có (`AL Variable Profile Rule.only_fields`) | ⛔ **Không** — chỉ có trong response |

### 1.4 Giá trị "chưa resolve"

- Biến chưa có giá trị: `value = "—"`, `has_value = false`.
- `include_values=False`: server đặt `value = "—"` cho **mọi** biến nhưng **giữ**
  `has_value` — client vẫn biết biến nào có dữ liệu.

---

## 2. Bảng API

| # | Hàm | Mục đích | Tham số chính | Quyền |
|---|---|---|---|---|
| 1 | `get_variable_catalog` | Danh mục biến cho 1 field/ngữ cảnh | `doctype`, `docname`, `child_table`, `row_index`, `fieldname`, `include_values`, `profile` | guard doctype + read |
| 2 | `get_variable_profile` | Profile đang áp cho bản ghi | `doctype`, `docname` | guard doctype + read |
| 3 | `preview_variable_catalog` | Admin xem trước 1 profile | `profile`, `doctype`, `docname`, `child_table`, `row_index`, `fieldname` | guard doctype + **read trên `AL Variable Profile`** |
| 4 | `explain_variable` | Vì sao thấy/không thấy 1 biến | `variable_name`, `doctype`, `docname`, `child_table`, `row_index`, `fieldname` | guard doctype + read |
| 5 | `get_row_literal_names` | Tên row literal đang bật | — | đăng nhập (whitelist) |
| 6 | `get_formula_fields` | Registry field công thức | `doctype` (rỗng = tất cả) | đăng nhập (whitelist) |
| 7 | `get_formula_context` | Context cho autocomplete/validate (2 đường) | `doctype`, `docname`, `fieldname`, `child_table`, `row_index`, `include_all_sources` | guard doctype + read |

> Mọi hàm đều `@frappe.whitelist()` — gọi được từ client đã đăng nhập. Riêng mục 5 và 6
> **không** có guard doctype (dữ liệu cấu hình, không phải chứng từ).

---

## 3. `get_variable_catalog`

`alumglass/api/variable_catalog.py:275`

```python
get_variable_catalog(doctype, docname=None, child_table=None,
                     row_index=None, fieldname=None,
                     include_values=True, profile=None)
```

### 3.1 Tham số

| Tham số | Kiểu | Mặc định | Ghi chú |
|---|---|---|---|
| `doctype` | str | — | Bắt buộc |
| `docname` | str | `None` | Có để resolve giá trị và đọc `variable_profile` |
| `child_table` | str | `None` | Để lấy binding scope dòng con + row literal của dòng |
| `row_index` | int | `None` | Cần cho row literal / `cost_template_line` |
| `fieldname` | str | `None` | Áp `only_fields`: **có** ⇒ server lọc rule theo field; **không** ⇒ server không lọc, vẫn trả `only_fields`/`hide_all` trên từng biến để client lọc |
| `include_values` | bool/str | `True` | `"false"`/`"0"` ⇒ ẩn giá trị |
| `profile` | str | `None` | Ép dùng 1 profile, bỏ qua field/default (dùng cho admin/preview) |

### 3.2 Kết quả khi **có** profile

```json
{
  "success": true,
  "profile": {"code": "P_COST_TEMPLATE_DEFAULT", "name": "Mặc định — AL Cost Template",
              "default_action": "EXCLUDE_ALL"},
  "variables": [
    {
      "name": "VL_NHOM",
      "label": "VL_NHOM — VL Nhôm",
      "type": "Float",
      "value": 0,
      "has_value": true,
      "source_kind": "cost_bucket",
      "source_ref": "VL_NHOM",
      "group": "01 · Vật liệu & chi phí",
      "sort_order": 10,
      "provenance": "AL Cost Bucket",
      "source": "local",
      "source_type": "cost_bucket",
      "value_source": "Tính tự động khi chạy BomOrchestrator B4-B5",
      "description": "Cost Bucket (...) · giá trị được tính khi engine chạy",
      "category": "",
      "is_required": false,
      "is_pricing_dimension": false,
      "only_fields": [],
      "hide_all": false,
      "adapter_order": 20,
      "matched_rule": {"action": "Include", "source_kind": "cost_bucket",
                       "group_label": "01 · Vật liệu & chi phí", "sort_order": 10}
    }
  ],
  "groups": [
    {"key": "01 · Vật liệu & chi phí", "label": "01 · Vật liệu & chi phí",
     "sort_order": 10,
     "variables": ["…cùng shape như trên…"]}
  ],
  "references": [
    {"name": "items.kinh_tren.width", "label": "Chiều rộng — kính trên",
     "insert": "items.kinh_tren.width", "table": "items",
     "slug": "kinh_tren", "field": "width"},
    {"name": "items[0].width", "label": "Chiều rộng — hàng 1",
     "insert": "items[0].width", "table": "items", "idx": 0, "field": "width"}
  ],
  "meta": {
    "total": 38,
    "excluded_by_rules": 112,
    "duplicates": [],
    "profile_code": "P_COST_TEMPLATE_DEFAULT",
    "fieldname": "calc_formula",
    "child_table": "items",
    "row_index": 0,
    "source_kinds": ["common_var", "cost_bucket", "cost_template_line",
                     "formula_global", "fvb_scope", "variable_library_system"]
  }
}
```

> Số `total` / `excluded_by_rules` là **ví dụ minh hoạ**, phụ thuộc dữ liệu site.

Các key bổ sung có thể có trên biến:

| Key | Khi nào | Nghĩa |
|---|---|---|
| `matched_rule` | Biến khớp rule Include | Rule đã quyết định nhóm/thứ tự |
| `scope_doctype` | Nguồn `fvb_scope` | Binding thuộc doctype nào |
| `source` | Luôn có | `local` hoặc `global` (binding global / global var) |

### 3.3 Kết quả khi **không** có profile

Đường này cố ý trả **rỗng** để caller tự chuyển sang legacy:

```json
{
  "success": true,
  "profile": null,
  "variables": [],
  "groups": [],
  "references": [],
  "meta": {
    "total": 0, "excluded_by_rules": 0, "duplicates": [],
    "profile_code": null, "fieldname": "calc_formula",
    "legacy_fallback": true
  }
}
```

Nghĩa là: **`profile === null` ⇒ gọi `get_formula_context` để lấy danh sách thật.**
`formula_setup.js` không gọi trực tiếp `get_variable_catalog`; nó gọi
`get_formula_context`, và server tự chọn đường.

### 3.4 Thứ tự áp luật (server, cố định)

```
1. Exclude khớp                    → loại
2. EXCLUDE_ALL và không khớp Include → loại
3. Include khớp                    → gắn group_label + sort_order
4. only_fields (server chỉ lọc khi CÓ fieldname;
   autocomplete bulk để client lọc)  → loại nếu field không nằm trong danh sách
5. require_value                   → loại nếu không có giá trị thật
6. dedupe theo name                → giữ 1; phần bỏ ghi vào meta.duplicates
7. sort: sort_order → group → name
```

Chi tiết mã: `alumglass/variable_sources/rules.py`
(`select_candidates` dòng 274, `dedupe_candidates` dòng 349).

---

## 4. `get_variable_profile`

`alumglass/api/variable_catalog.py:318`

```python
get_variable_profile(doctype, docname=None)
```

Trả `{code, name, default_action}` hoặc **`None`** (JSON `null`) khi:

- doctype không khai field Link tới `AL Variable Profile`, hoặc
- bản ghi để trống và `AL Variable Settings.default_profile` cũng trống, hoặc
- profile được trỏ tới đã bị tắt (`is_active = 0`) hoặc không tồn tại.

Thứ tự resolve: tham số `profile` → field trên bản ghi → `default_profile`.

---

## 5. `preview_variable_catalog`

`alumglass/api/variable_catalog.py:326`

```python
preview_variable_catalog(profile, doctype, docname=None, child_table=None,
                        row_index=None, fieldname=None)
```

- Dùng cho nút **Xem trước danh sách biến** trên form profile.
- Trả **cùng shape** với `get_variable_catalog`, nhưng luôn `include_values=True` và
  dùng `profile` truyền vào (không đọc field trên bản ghi).
- Quyền: ngoài guard doctype, còn cần **read** trên `AL Variable Profile`.
  Thiếu quyền ⇒ `frappe.PermissionError` với câu
  "Bạn không có quyền xem trước danh mục biến."

---

## 6. `explain_variable`

`alumglass/api/variable_catalog.py:340`

```python
explain_variable(variable_name, doctype, docname=None, child_table=None,
                 row_index=None, fieldname=None)
```

Trả **mọi nguồn** có cùng tên biến — kể cả nguồn bị rule loại:

```json
{
  "success": true,
  "variable": "TONG_M2",
  "profile": {"code": "P_BOM_CUA_DI", "name": "BOM cửa đi", "default_action": "EXCLUDE_ALL"},
  "sources": [
    {"name": "TONG_M2", "source_kind": "common_var", "source_ref": "TONG_M2",
     "provenance": "AL Variable Settings · Common Variables",
     "type": "Float", "value": "—", "has_value": false,
     "group": "06 · Thông số nhập", "selected": true, "kept": true}
  ],
  "kept": {"name": "TONG_M2", "source_kind": "common_var", "source_ref": "TONG_M2",
           "provenance": "AL Variable Settings · Common Variables",
           "type": "Float", "value": "—", "has_value": false,
           "group": "06 · Thông số nhập", "selected": true, "kept": true},
  "meta": {"total_sources": 1, "excluded_by_rules": 0, "legacy_fallback": false}
}
```

| Key | Nghĩa |
|---|---|
| `selected` | Nguồn này có vượt qua rule không |
| `kept` | Nguồn này có thắng dedupe không (chỉ **một** nguồn `kept=true`) |
| `kept` (top-level) | Bản ghi nguồn thắng, hoặc `null` |
| `meta.legacy_fallback` | `true` = bản ghi chưa có profile; `sources` là toàn bộ nguồn |

Lỗi: `variable_name` rỗng ⇒ "Thiếu tên biến cần giải thích."

> Hàm này chạy **tất cả** adapter (không chỉ nguồn được Include) — chi phí cao hơn
> `get_variable_catalog`. Dùng cho chẩn đoán, ⛔ đừng gọi theo từng lần gõ.

---

## 7. `get_row_literal_names`

`alumglass/api/variable_catalog.py:294`

```python
get_row_literal_names() -> list[str]
```

- Đọc `AL Variable Settings.row_literals`, chỉ dòng `is_active`.
- Site chưa migrate / chưa có Settings ⇒ `[]` (không ném lỗi).
- Dùng bởi `AL Bom Set._warn_rule_input_expr()` để biết field nào engine **thật sự**
  nạp cho một dòng.

---

## 8. `get_formula_fields`

`alumglass/api/formula_registry.py:102`

```python
get_formula_fields(doctype=None) -> list[dict]
```

Trả về (đã parse `editor_opts`):

```json
[
  {"doctype": "AL Bom Set", "child_table": "items", "fieldname": "width",
   "id_field": "slug", "editor_opts": {"height": "70px"}, "sort_order": 10}
]
```

| Đặc điểm | Chi tiết |
|---|---|
| Lọc | Chỉ `is_active = 1` |
| `doctype=None` | Trả toàn bộ registry |
| Cache | Theo **request** (`frappe.local`), không theo worker — sửa record thấy ngay ở request sau |
| Cột DB | `target_doctype` (vì `doctype` là từ khoá dành riêng của Frappe); API vẫn trả key `doctype` |
| `editor_opts` hỏng | Trả `{}`, ⛔ không làm mất autocomplete |
| Site chưa migrate | `[]` + ghi log |

---

## 9. `get_formula_context` (điểm vào thực tế của UI)

`alumglass/api/__init__.py:659`

```python
get_formula_context(doctype, docname=None, fieldname=None,
                    child_table=None, row_index=None,
                    include_all_sources=False)
```

### 9.1 Hai đường

| Điều kiện | Đường | Kết quả |
|---|---|---|
| `include_all_sources=False` **và** bản ghi có profile | **Catalog** | `variables` đã lọc + `groups` gián tiếp qua biến + `references` + `profile` + `meta` |
| `include_all_sources=True` | **Legacy** | 8 nhóm cũ, `profile = null` |
| Bản ghi **chưa** gán profile | **Legacy** | 8 nhóm cũ, `profile = null` |
| Catalog lỗi / chưa cài module | **Legacy** | 8 nhóm cũ; lỗi được ghi log |

### 9.2 `include_all_sources=True` — chỉ dành cho validate

Đây là **hợp đồng bắt buộc**:

- `build_known_names()` (`alumglass/al_bom_engine/formula_validate.py:73-76`) luôn truyền
  `include_all_sources=True`.
- `cost_template.js` có `fetchValidationContext()` riêng, gửi `include_all_sources: 1`
  (`alumglass/public/js/cost_template.js:224-243`).

⛔ **Không dùng `include_all_sources=True` cho autocomplete.** Nó bỏ qua toàn bộ profile,
nên danh sách sẽ quay về "quá nhiều biến" — đúng thứ tính năng này sinh ra để sửa.

### 9.3 Shape trả về

```json
{
  "doctype": "AL Cost Template",
  "docname": "CT-001",
  "variables": ["…cùng shape candidate, đã chuẩn hoá…"],
  "references": ["…"],
  "total_sources": 5,
  "total_variables": 38,
  "profile": {"code": "P_COST_TEMPLATE_DEFAULT", "name": "…", "default_action": "EXCLUDE_ALL"},
  "meta": {"total": 38, "excluded_by_rules": 112, "duplicates": [],
           "profile_code": "…", "fieldname": "calc_formula"}
}
```

Đường legacy thêm `meta.duplicates` (mọi ca trùng tên bị bỏ) và `profile: null`.

### 9.4 Chuẩn hoá biến trước khi trả client

`_normalize_catalog_variable()` bảo đảm luôn có đủ key mà JS đọc:
`label`, `value` (rỗng ⇒ `"—"`), `type`, `source`, `source_type`, `group`,
`value_source`, `description`, `is_pricing_dimension`, `only_fields` (luôn list),
`hide_all` (bool).
Hàm **không** đổi ngữ nghĩa dữ liệu catalog.

---

## 10. Ví dụ gọi

### 10.1 Từ JS (form script)

```javascript
frappe.call({
  method: "alumglass.api.variable_catalog.get_variable_catalog",
  args: {
    doctype: "AL Bom Set",
    docname: frm.docname,
    child_table: "items",
    row_index: 0,
    fieldname: "qty",
  },
  callback: function (r) {
    var res = r.message || {};
    if (!res.profile) {
      // Bản ghi chưa gán profile — dùng get_formula_context như cũ.
      return;
    }
    console.log(res.meta.total, "biến,", res.references.length, "tham chiếu");
  },
});
```

Xem trước (admin):

```javascript
frappe.call({
  method: "alumglass.api.variable_catalog.preview_variable_catalog",
  args: {profile: "P_COST_TEMPLATE_DEFAULT", doctype: "AL Cost Template",
         child_table: "items", fieldname: "calc_formula"},
});
```

Giải thích 1 biến:

```javascript
frappe.call({
  method: "alumglass.api.variable_catalog.explain_variable",
  args: {variable_name: "TONG_M2", doctype: "AL Bom Set", docname: frm.docname},
});
```

### 10.2 Từ console Python

```python
bench --site <dev> console

>>> from alumglass.api.variable_catalog import get_variable_catalog
>>> res = get_variable_catalog(
...     "AL Cost Template", "<tên record>",
...     child_table="items", row_index=0, fieldname="calc_formula")
>>> res["profile"], res["meta"]["total"], res["meta"]["excluded_by_rules"]
>>> [v["name"] for v in res["variables"]][:10]
```

Giải thích vì sao một biến không hiện:

```python
>>> from alumglass.api.variable_catalog import explain_variable
>>> explain_variable("TONG_M2", "AL Cost Template", "<tên record>")
```

### 10.3 Từ `bench execute`

```bash
bench --site <dev> execute alumglass.api.variable_catalog.get_variable_catalog \
  --kwargs '{"doctype": "AL Cost Template", "docname": "<tên record>", "child_table": "items", "fieldname": "calc_formula"}'

bench --site <dev> execute alumglass.api.variable_catalog.get_variable_profile \
  --kwargs '{"doctype": "AL Cost Template", "docname": "<tên record>"}'

bench --site <dev> execute alumglass.api.formula_registry.get_formula_fields \
  --kwargs '{"doctype": "AL Bom Set"}'
```

> `bench execute` chạy trong ngữ cảnh site, thường với user **Administrator**, nên
> **không phản ánh** quyền của người dùng thật. Kết quả dùng để kiểm dữ liệu,
> ⛔ không dùng để kết luận "user thường cũng gọi được".

---

## 11. Lỗi thường gặp

| Thông báo / hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| "Thiếu loại chứng từ cần lấy danh sách biến công thức." | `doctype` rỗng | Truyền đúng doctype đang mở |
| "Không lấy được danh sách biến công thức cho loại chứng từ X." | Doctype ngoài miền `AL ` / `Formula Builder` / `Quotation` | Chỉ dùng cho doctype trong miền; thêm miền phải sửa guard có chủ đích |
| "Bạn không có quyền xem X …" | User thiếu quyền read trên doctype | Cấp quyền read; ⛔ đừng gọi thay bằng Administrator rồi coi là đã sửa |
| "Bạn không có quyền xem trước danh mục biến." | Thiếu read trên `AL Variable Profile` | Cấp role phù hợp |
| "Thiếu tên biến cần giải thích." | `explain_variable` không có `variable_name` | Truyền tên biến |
| `profile: null`, `variables: []` | Bản ghi chưa gán profile (hành vi đúng) | Gán `variable_profile`, hoặc dùng `get_formula_context` |
| `variables: []` dù có profile | Rule lọc hết, `only_fields`, `require_value`, hoặc adapter lỗi | Gọi `explain_variable`, xem `meta.excluded_by_rules` |
| API trả 403 / 500 | Guard quyền hoặc site chưa migrate | Xem [troubleshooting.md](troubleshooting.md) |

---

## 12. Đọc tiếp

- Cách setting trên UI: [huong-dan-setting-bien.md](huong-dan-setting-bien.md)
- Triệu chứng và cách xử lý: [troubleshooting.md](troubleshooting.md)
- Bản đồ nguồn biến và 11 lỗi đã vá: [../../nguon_bien_tham_chieu.md](../../nguon_bien_tham_chieu.md) §3, §10.1
