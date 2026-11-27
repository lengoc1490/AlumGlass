# Variable Catalog — bộ biến gợi ý cho công thức (v28_14)
>
> 🔴 **Cập nhật 2026-11-27 (B2/R3):** `AL Variable Settings` **đã bị XOÁ** (bảng + 2 bảng con).
> Ba loại biến nay nằm
> trong **`AL Variable Library`**: biến người dùng nhập = bật **“Người dùng nhập”** (`is_input`);
> biến theo dòng = **Category = “Row Literals”**; còn lại = biến cấu hình. `default_profile` →
> **`AL Variable Profile.is_default`**; `preview_doctype` → **`AL Variable Profile.preview_doctype`**.
> 🔴 **Cập nhật 2026-11-27 (lần 2):** `AL Variable Library` chỉ còn **MỘT** nhóm — ô
> **Nhóm hiển thị** (Select); ô `category` cũ đã gộp vào đó. Mọi câu bên dưới nhắc `category`
> là **lịch sử**.
>
> Mọi câu bên dưới nhắc “mở `AL Variable Settings`” là **lịch sử đã xoá hẳn** — trạng thái hiện tại xem
> [thiết kế gộp cấu hình](../design/gop-noi-cau-hinh-bien-va-tinh-toan.md).


> **Mốc code tài liệu này mô tả**
>
> | | |
> |---|---|
> | App | `alumglass` — nhánh `main`, HEAD `566cdc2` (2026-11-12) **+ thay đổi v28_14 chưa commit** |
> | Phạm vi | Lớp **gợi ý / lọc** biến khi gõ công thức: DocType profile, catalog API, autocomplete, xem trước |
> | ⛔ Ngoài phạm vi | Cách engine tính ra tiền — dẫn sang [hướng dẫn tính giá full flow](../huong-dan-tinh-gia-full-flow.md), ⛔ không chép |
> | Đối tượng | BOM Manager / admin cấu hình; người lập công thức; DEV bảo trì API |
> | Ngày soạn | 2026-11-12 |
>
> **Mức kiểm chứng:** ⛔ **chưa chạy `bench migrate`, chưa chạy test trên site** (bench hiện
> không có site nào cài `alumglass`). Theo ghi nhận của DEV tại
> `../../nguon_bien_tham_chieu.md` §1, đã chạy: `py_compile`, `json.load`, `node --check`,
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
| **Tên biến / field công thức nằm cứng trong code** | Row literal / common var / danh sách field công thức viết cứng trong Python và JS | **Đăng ký tên** bằng dòng `AL Variable Library` (Category = Row Literals cho biến theo dòng) hoặc record `AL Formula Field`; ⚠️ giá trị vẫn phải có đường inject của engine — Library ⛔ không tự sinh giá trị |

> ⚠️ **Hai chỗ dễ nhầm:** dòng Library bật **Người dùng nhập** (`is_input`) **không** tự nuôi dialog "Tham số
> BOM" (dialog đọc `AL Variable Set` + system var của Library); dòng Library **Category = Row Literals**
> chỉ đăng ký **tên** cho gợi ý/validate, ⛔ không thêm giá trị engine inject. Chi tiết:
> [nguon-bien-theo-doctype.md](nguon-bien-theo-doctype.md) §3.2 · §3.4.

---

## 2. Ai dùng

| Vai | Việc làm | Tài liệu |
|---|---|---|
| **BOM Manager / admin** | Tạo/sửa `AL Variable Profile`, `AL Variable Library`, `AL Formula Field`; gán profile cho chứng từ mẹ; bấm **Xem trước danh sách biến**. Lưu ý: 3 DocType cấu hình mặc định chỉ cấp `System Manager`; `Formula Global Variable` đã cấp thêm cho `AL BOM Manager` (2026-11-27) | [huong-dan-setting-bien.md](huong-dan-setting-bien.md) |
| **Người lập công thức** | Mở form, gõ công thức; nhận danh sách biến đã lọc theo profile của bản ghi | Mục 4 dưới đây |
| **DEV bảo trì** | Gọi API, đọc shape trả về, thêm adapter nguồn mới | [api-reference.md](api-reference.md) · [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md) |

> ⚠️ **Phân quyền mặc định:** `AL Variable Profile`, `AL Variable Library`,
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
   · không có → AL Variable Profile.is_default (CHỈ doctype đã khai field Link);
     chưa migrate B2 → AL Variable Settings.default_profile
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

1. **Mở `AL Variable Profile`** → thấy 3 profile mẫu do patch tạo:
   `P_COST_TEMPLATE_DEFAULT`, `P_ACCESSORY_DEFAULT`, `P_BOM_DEFAULT`.
2. **Bấm `Xem trước danh sách biến`** trên profile → chọn DocType `AL Cost Template`
   (ô mặc định lấy từ `AL Variable Profile.preview_doctype`; trống → giá trị cũ ở Single) → xem danh sách theo nhóm,
   cột Nguồn, và cảnh báo trùng tên nếu có.
3. **Mở `AL Cost Template` / `AL Bom Set`** → record cũ đã được gán `variable_profile` (patch chỉ
   gán record **đang trống**); record tạo **sau** migrate phải **chọn tay** profile ở field
   **Variable Profile** (⛔ không tự gán).
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
| **Reference** | Gợi ý dạng `items.<slug>.<field>` hoặc `items[n].<field>` (dạng chỉ số chỉ để tra, ⛔ không dùng trong công thức) | Trường `references` trong kết quả API |
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
| [huong-dan-su-dung-tinh-nang.md](huong-dan-su-dung-tinh-nang.md) | **Bắt đầu ở đây nếu bạn là người dùng**: 11 tính năng mới, cách dùng từng cái, 5 tình huống thực tế, migrate/rollback |
| [al-variable-profile.md](al-variable-profile.md) | **Tra cứu đầy đủ `AL Variable Profile`**: mọi field, 11 `source_kind`, thuật toán áp rule, cross-row, 4 ví dụ hoàn chỉnh, 11 anti-pattern |
| [vi-du-setting-day-du.md](vi-du-setting-day-du.md) | **Ví dụ setting đầy đủ**: 13 cột của rule, 11 nguồn lấy từ đâu/hiện ra sao, 3 profile hoàn chỉnh, cách tắt và cách chỉ hiện một số biến |
| [vi-du-a-z.md](vi-du-a-z.md) | Một ví dụ xuyên suốt A→Z: dựng dữ liệu nền → profile → rule → cross-row → Settings → Formula Field → gán → xem trước → gõ thử → lưu → runtime |
| [tu-goi-y-den-runtime.md](tu-goi-y-den-runtime.md) | Đường đi của một biến từ lúc gõ trong autocomplete tới lúc engine ra giá trị, kèm chỗ đứt gãy và cách chẩn đoán |
| [nguon-bien-theo-doctype.md](nguon-bien-theo-doctype.md) | **Tra theo DocType**: setting ở đâu, lấy từ đâu, điều kiện gì, runtime B0–B7 đọc bảng nào; bảng "biến này từ đâu ra?" |
| [huong-dan-setting-bien.md](huong-dan-setting-bien.md) | Thao tác từng bước trên UI: tạo profile, rule, cross-row, gán, xem trước |
| [api-reference.md](api-reference.md) | Bảng API, tham số, shape trả về, quyền, ví dụ gọi |
| [troubleshooting.md](troubleshooting.md) | Triệu chứng → nguyên nhân → cách xử lý |
| [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md) | Thay đổi theo nhóm, migration, tương thích ngược, giới hạn |
| [../../nguon_bien_tham_chieu.md](../../nguon_bien_tham_chieu.md) | Toàn bộ nguồn biến của AlumGlass, kiến trúc, lỗi đã vá, giới hạn |
| [../../../formula_builder/docs/huong-dan-tinh-nang-moi.md](../../../formula_builder/docs/huong-dan-tinh-nang-moi.md) | Phía engine Formula Builder: `$NAME`, lọc binding theo field, gộp biến trùng tên, biến toàn cục đã tắt |
| [../huong-dan-tinh-gia-full-flow.md](../huong-dan-tinh-gia-full-flow.md) | Luồng tính giá B0–B7 (quy ước tài liệu của repo) |
