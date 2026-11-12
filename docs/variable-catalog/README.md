# Variable Catalog — bộ biến gợi ý cho công thức (v28_14)

> **Mốc code tài liệu này mô tả**
>
> | | |
> |---|---|
> | App | `alumglass` — nhánh `main`, HEAD `90892c1` (2026-11-12) **+ thay đổi v28_14 chưa commit** |
> | Phạm vi | Lớp **gợi ý / lọc** biến khi gõ công thức: DocType profile, catalog API, autocomplete, xem trước |
> | ⛔ Ngoài phạm vi | Cách engine tính ra tiền — dẫn sang [hướng dẫn tính giá full flow](../huong-dan-tinh-gia-full-flow.md), ⛔ không chép |
> | Đối tượng | BOM Manager / admin cấu hình; người lập công thức; DEV bảo trì API |
> | Ngày soạn | 2026-11-12 |
>
> **Mức kiểm chứng:** ⛔ **chưa chạy `bench migrate`, chưa chạy test trên site** (bench hiện
> không có site nào cài `alumglass`). Theo ghi nhận của DEV tại
> `../../nguon_bien_tham_chieu.md` §10A, đã chạy: `py_compile`, `json.load`, `node --check`,
> `ruff --select E9,F` và test thuần — `test_variable_catalog_rules.py` **41 ca PASS**,
> `test_dollar_normalize.py` **15 ca PASS**, `test_live_context_dedupe.py` **11 ca PASS**.
> Mọi mô tả UI/DB dưới đây đọc từ mã; **chưa quan sát trên màn hình thật**.

---

## 1. Tính năng này giải quyết việc gì

Trước v28_14, người lập công thức phải tự lọc bằng mắt giữa 9 nhóm biến chồng lấn.
Ba việc được sửa:

| Việc | Trước | Sau |
|---|---|---|
| **Quá nhiều biến** | Gõ `DO_` ở bảng giá thành thấy hàng chục biến không liên quan | Profile khai rule Include/Exclude, chỉ còn biến đúng ngữ cảnh |
| **Không rõ nguồn** | Cùng một tên có thể đến từ Library, Binding, Global… | Mỗi biến có `source_kind`, `provenance`, `group`; API `explain_variable` giải thích vì sao thấy/không thấy |
| **Thêm biến phải sửa code** | Row literal / common var / field công thức nằm cứng trong Python và JS | Thêm dòng trong `AL Variable Settings` hoặc 1 record `AL Formula Field` — không sửa code |

---

## 2. Ai dùng

| Vai | Việc làm | Tài liệu |
|---|---|---|
| **BOM Manager / admin** | Tạo/sửa `AL Variable Profile`, `AL Variable Settings`, `AL Formula Field`; gán profile cho chứng từ mẹ; bấm **Xem trước danh sách biến**. Lưu ý: 3 DocType cấu hình mặc định chỉ cấp `System Manager` | [huong-dan-setting-bien.md](huong-dan-setting-bien.md) |
| **Người lập công thức** | Mở form, gõ công thức; nhận danh sách biến đã lọc theo profile của bản ghi | Mục 4 dưới đây |
| **DEV bảo trì** | Gọi API, đọc shape trả về, thêm adapter nguồn mới | [api-reference.md](api-reference.md) · [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md) |

> ⚠️ **Phân quyền mặc định:** `AL Variable Profile`, `AL Variable Settings`,
> `AL Formula Field` hiện chỉ cấp cho **System Manager** (`permissions` trong JSON).
> Role `AL BOM Manager` **chưa** có quyền ghi 3 DocType này. Muốn giao cho BOM Manager
> ⇒ phải sửa phân quyền, ⛔ đừng giả định đã có.

---

## 3. Luồng hoạt động

```
Người dùng mở form AL Bom Set / AL Cost Template / AL Accessory Set / AL Alert Config
        │
        │  form-refresh  → alumglass/public/js/formula_setup.js
        ▼
1. Xác định profile đang áp
   · field `variable_profile` trên bản ghi mẹ
   · không có → AL Variable Settings.default_profile (CHỈ doctype đã khai field Link)
   · không có nữa → không có profile ⇒ đường legacy (8 nhóm cũ)
        │
        ▼
2. Chạy adapter của các nguồn được phép
   variable_sources/adapters.py
   fvb_scope · cost_bucket · variable_library_system/user · variable_set
   cost_template_line · formula_global · row_literal · common_var · doctype_field
        │
        ▼
3. Áp rule của profile
   variable_sources/rules.py
   Exclude thắng → EXCLUDE_ALL chỉ giữ biến khớp Include
   → lọc prefix / regex / category / kiểu / only_fields / require_value
        │
        ▼
4. Dedup + gom nhóm
   cùng tên: ưu tiên có giá trị → sort_order nhỏ → adapter đăng ký trước
   nhóm theo `group_label` của rule; ghi mọi ca trùng vào `meta.duplicates`
        │
        ▼
5. API trả về
   alumglass/api/variable_catalog.py::get_variable_catalog
   { profile, variables, groups, references, meta }
        │
        ├──────────────► autocomplete trong Monaco (chỉ GỢI Ý)
        │
        └──────────────► references: items.<slug>.<field>
                         dạng slug và dạng items[n].<field>
```

**Nhánh validate tách riêng:**

```
Lưu công thức → formula_validate.build_known_names()
                 └─ get_formula_context(..., include_all_sources=True)
                    ⇒ BỎ QUA profile, dùng universe legacy ĐẦY ĐỦ
```

> 🔴 **Ranh giới quan trọng nhất:** profile **chỉ lọc gợi ý**. Nó ⛔ không đổi giá trị
> tính toán, ⛔ không thu hẹp universe hợp lệ khi validate. Công thức cũ dùng biến
> ngoài profile vẫn lưu và vẫn chạy. Chi tiết: [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md) mục 4.

---

## 4. Năm phút bắt đầu

Điều kiện: site dev đã cài `alumglass` + `formula_builder`.

```bash
# 1) Nạp DocType mới + cột variable_profile + seed dữ liệu mẫu
bench --site <dev> migrate

# 2) Nạp lại asset JS (hooks.py đã bump formula_setup.js / cost_template.js lên v=1.2.0)
bench build --app alumglass
```

Trên màn hình:

1. **Mở `AL Variable Profile`** → thấy 2 profile mẫu do patch tạo:
   `P_COST_TEMPLATE_DEFAULT`, `P_ACCESSORY_DEFAULT`.
2. **Bấm `Xem trước danh sách biến`** trên profile → chọn DocType `AL Cost Template`
   (ô mặc định lấy từ `AL Variable Settings.preview_doctype`) → xem danh sách theo nhóm,
   cột Nguồn, và cảnh báo trùng tên nếu có.
3. **Mở `AL Cost Template`** → record cũ đã được gán `variable_profile` (patch chỉ gán
   record **đang trống**); record mới thì tự chọn profile ở field **Variable Profile**.
4. **Mở một dòng `items` → bấm vào `calc_formula`** → gõ `VL_` hoặc `TONG_`.
   Danh sách gợi ý phải đúng nhóm của profile, không còn toàn bộ Library.
5. **Lưu thử** một công thức dùng biến **ngoài** profile (ví dụ `W_mm`).
   Hệ thống **phải cho lưu** — nếu bị chặn là sai thiết kế.

> Chưa có site để chạy 5 bước trên? Đọc mục 6 trước, rồi dùng
> [troubleshooting.md](troubleshooting.md) để chẩn đoán từng triệu chứng.

---

## 5. Khái niệm

| Khái niệm | Là gì | Nằm ở đâu |
|---|---|---|
| **Variable Profile** | Một bộ biến cho một ngữ cảnh; chứa rule và cấu hình biến chéo dòng | `AL Variable Profile` |
| **Rule** | Một dòng Include/Exclude: nguồn nào, tham chiếu nào, lọc thêm gì | `AL Variable Profile Rule` (bảng con) |
| **Cross Row** | Khai bảng con + field định danh + field được tham chiếu chéo | `AL Variable Cross Row` (bảng con) |
| **Adapter** | Hàm sinh danh sách biến của **một nguồn** | `alumglass/variable_sources/adapters.py` |
| **Catalog** | Kết quả sau khi chạy adapter + rule + dedup + gom nhóm | `get_variable_catalog` |
| **Reference** | Gợi ý dạng `items.<slug>.<field>` hoặc `items[n].<field>` | Trường `references` trong kết quả API |
| **Source kind** | Tên nguồn biến (11 giá trị) | Field `source_kind` của Rule |
| **only_fields** | Field mà **rule** chỉ được áp (biến của rule chỉ hiện khi sửa các field đó); `[]` = không giới hạn. Muốn mỗi field một danh sách: **tách biến giữa các rule**; nhiều rule cùng biến ⇒ lấy hợp | Field `only_fields` của Rule |
| **Legacy** | Đường cũ 9 mục biến (mã gọi là "8 nhóm cũ"), dùng khi bản ghi chưa gán profile hoặc khi validate | `api/__init__.py::get_formula_context` nhánh B |

---

## 6. Mức kiểm chứng và giới hạn hiện tại

| Hạng mục | Trạng thái |
|---|---|
| `bench migrate` trên site có `alumglass` | ⛔ **chưa chạy** |
| Test Frappe/unittest trên site | ⛔ **chưa chạy** |
| Test thuần bộ luật catalog | ✅ 41 ca PASS (`alumglass/tests/test_variable_catalog_rules.py`) |
| Kiểm tra tĩnh | ✅ `py_compile` · `json.load` · `node --check` · `ruff` (theo báo cáo DEV) |
| Quan sát autocomplete trên trình duyệt | ⛔ **chưa làm** — cần `bench build --app alumglass` trước |
| Commit / push | ⛔ **chưa** — toàn bộ đang ở working tree |

Hệ quả cần nhớ khi đọc tiếp: mọi câu "thấy biến X", "bấm nút Y" là **hành vi đọc từ mã**,
chưa phải kết quả đo trên màn hình.

---

## 7. Đọc tiếp

| Tài liệu | Dành cho |
|---|---|
| [huong-dan-setting-bien.md](huong-dan-setting-bien.md) | Thao tác từng bước trên UI: tạo profile, rule, cross-row, gán, xem trước |
| [api-reference.md](api-reference.md) | Bảng API, tham số, shape trả về, quyền, ví dụ gọi |
| [troubleshooting.md](troubleshooting.md) | Triệu chứng → nguyên nhân → cách xử lý |
| [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md) | Thay đổi theo nhóm, migration, tương thích ngược, giới hạn |
| [../../nguon_bien_tham_chieu.md](../../nguon_bien_tham_chieu.md) | Toàn bộ 21 nguồn biến, kiến trúc, 11 lỗi đã vá (§6.2, §8, §9, §10A) |
| [../huong-dan-tinh-gia-full-flow.md](../huong-dan-tinh-gia-full-flow.md) | Luồng tính giá B0–B7 (quy ước tài liệu của repo) |
