# Cấu hình `AL Cost Bucket.source_config` — giao việc gom bucket cho Formula Builder

Tài liệu này hướng dẫn **cấu hình từng tham số** để bước **B5 (gom cost bucket)** của engine
tính giá AlumGlass giao việc cộng nhóm cho Formula Builder thay vì cộng bằng Python.

- Đối tượng: người triển khai / admin cấu hình, không cần sửa code.
- Liên quan: [quotation-pricing-flow.md](quotation-pricing-flow.md) §B5, §11 ·
  [huong-dan-tinh-gia-full-flow.md](huong-dan-tinh-gia-full-flow.md) §B5.

---

## 1. Kiến trúc — tiền chảy qua đâu

```
AL Bom Item.cost_bucket            (mỗi dòng BOM mang 1 bucket)
AL Accessory Item.cost_bucket      (bỏ trống → engine gán VL_PK)
        │
        │  B4 tính từng dòng: line_total, unit_qty, total_qty…
        ▼
B5  gom line_total theo cost_bucket  →  {VL_NHOM: …, VL_KINH: …, VL_PK: …}
        │                               (chỉ bucket LEAF có mặt trong BOM)
        ▼
B6  chạy AL Cost Template (công thức) → TONG_VL, TONG_NC, GIA_THANH, GIA_BAN, GIA_VAT
```

Điểm cần nhớ:

| Loại bucket (`bucket_role`) | Ai tính | Có cấu hình `aggregate_from_items`? |
|---|---|---|
| **LEAF** — nhận `line_total` từ dòng BOM | **B5** (Python hoặc Formula Builder) | ✅ Có — đây là tài liệu này |
| **AGGREGATE** — tổng/hiệu của bucket khác (TONG_VL, GIA_THANH, GIA_VAT…) | **B6** (công thức trong `AL Cost Template`) | ⛔ **Không** — B5 không có dòng nào mang bucket AGGREGATE, cấu hình sẽ không bao giờ chạy |

`cost_bucket` lấy từ đâu:

- `AL Bom Item.cost_bucket` — Link tới `AL Cost Bucket`; engine dùng đúng giá trị người dùng chọn.
- `AL Accessory Item.cost_bucket` — phụ kiện được `_load_accessories` nạp thành dòng BOM;
  **bỏ trống = `VL_PK`** (`bom_orchestrator.py` §`_load_accessories`).

---

## 2. Hai đường của B5

`_resolve_cost_buckets_via_fb()` chỉ đọc `AL Cost Bucket` của **các bucket thực sự có mặt trong
`bom_result`** (bucket không xuất hiện → không query, không cảnh báo).

| Cấu hình bucket | B5 làm gì |
|---|---|
| `source_type ≠ "aggregate_from_items"` (kể cả `formula`, `doctype_query`…) | ⛔ Bỏ qua, cộng Python. Nếu `source_type` khác rỗng → ghi cảnh báo `bucket_source_type_chua_ho_tro:<code>` vào `al_bom_result.errors` |
| `source_type = "aggregate_from_items"` nhưng `source_config` **rỗng** | Cộng Python (đây là trạng thái seed hiện tại — golden số cũ) |
| `source_type = "aggregate_from_items"` + `source_config` **hợp lệ** | Giao Formula Builder: `resolve_all_bindings_batch` với `pre_resolved = inputs + rows` |

`rows` engine truyền cho FB chỉ gồm **2 field**:

```json
[{"cost_bucket": "VL_NHOM", "line_total": 1250000.0},
 {"cost_bucket": "VL_KINH", "line_total": 900000.0},
 {"cost_bucket": "VL_NHOM", "line_total": 50000.0}]
```

> ⚠️ Bucket nào đã resolve được qua FB thì **giá trị FB thay hoàn toàn** phần cộng Python của
> bucket đó (không cộng thêm). Vì vậy `filters`/`key_value` sai sẽ **hụt tiền**, không phải cộng
> dư.

---

## 3. Bảng tham số đầy đủ của `aggregate_from_items`

Chỉ những tham số đánh dấu ✅ mới có tác dụng ở B5.

| Tham số | Kiểu | Dùng ở B5? | Ý nghĩa |
|---|---|---|---|
| `rows_source` | enum: `resolved` \| `snapshot` \| `child_table` \| `doctype_query` | ✅ chỉ `resolved` | Nguồn các dòng để gom. B5 chỉ có `resolved` vì rows do engine truyền sẵn |
| `rows_var` | string, mặc định `rows` | ✅ | Tên biến chứa rows khi `rows_source=resolved`. **B5: phải là `rows`** (hoặc bỏ trống). ⛔ `bom_result` là SAI → không thấy rows → ra 0 **âm thầm** |
| `key_field` | string | ✅ | Field làm khoá lọc, ở B5 chỉ có `cost_bucket` |
| `key_value` | string | ✅ | Giá trị khoá (SUMIF). Literal (`VL_NHOM`) hoặc template `{{binding.variable_name}}`. ⛔ Để trống = gom **tất cả** rows (mọi bucket ra cùng một số) |
| `value_field` | string | ✅ | Field cộng. B5 chỉ có `line_total`. Thắng `sum_field` khi cả hai cùng có |
| `sum_field` | string | ✅ (bắt buộc để LƯU được) | Alias cũ của `value_field`. `AL Cost Bucket.validate` **bắt buộc** có `sum_field` khi `source_type=aggregate_from_items` (`al_cost_bucket.py:39-41`) ⇒ luôn khai `sum_field`, dù handler ưu tiên `value_field` |
| `aggregate` | enum | ✅ | `sum` \| `avg` \| `min` \| `max` \| `count` \| `first` \| `last` |
| `default_value` | number/string | ✅ | Trả về khi không lấy được rows / không dòng nào khớp. Mặc định `0` |
| `filters` | list `[[field, op, value], …]` | ✅ (chỉ trên 2 field) | Lọc bổ sung, AND với `key_field/key_value`. B5 chỉ lọc được `cost_bucket`, `line_total` |
| `snapshot_doctype` | string | ⛔ | Doctype chứa snapshot (dùng cho `rows_source=snapshot`) |
| `snapshot_name` | string | ⛔ | Tên record snapshot; hỗ trợ `{{doc.x}}`/`{{resolved.x}}` |
| `snapshot_field` | string, mặc định `snapshot` | ⛔ | Field JSON trên snapshot |
| `rows_path` | string, mặc định `items` | ⛔ | Đường dẫn tới list rows trong JSON snapshot |
| `child_table_field` | string | ⛔ | Field bảng con trên doc hiện tại (`rows_source=child_table`) |
| `doctype` | string | ⛔ | Doctype để query (`rows_source=doctype_query`) |
| `fields` | list string | ⛔ | Field lấy về cho `doctype_query` (mặc định `["name"]`) |
| `order_by` | string | ⛔ | Sắp xếp cho `doctype_query` |
| `limit` | int | ⛔ | Giới hạn số dòng `doctype_query` (0 = không giới hạn) |
| `transform` | object | ✅ | Hậu xử lý giá trị: `multiply`, `divide`, `add`, `formula`, `round`, `cast` |
| `type` | string | ✅ | Kiểu dữ liệu khi binding không khai `data_type` (mặc định `Float`) |

### 3.1 `rows_source` — vì sao B5 chỉ dùng `resolved`

| Giá trị | Lấy rows từ | Dùng được ở B5? |
|---|---|---|
| `resolved` | `resolved_so_far[rows_var]` — chính là `rows` engine truyền | ✅ Đường duy nhất |
| `snapshot` | Load `snapshot_doctype/snapshot_name` rồi đọc JSON → `rows_path` | ⛔ Context B5 **không có** `bom_version`; quan trọng hơn: snapshot BOM **không lưu `line_total`** (chỉ lưu config/công thức) ⇒ luôn rỗng |
| `child_table` | `doc.get(child_table_field)` | ⛔ `doc` ở B5 là **Quotation Item** — không có bảng con chứa dòng BOM/`line_total` |
| `doctype_query` | `frappe.get_all(doctype, …)` | ⛔ Thời điểm B5 chưa ghi `line_total` của từng dòng xuống DB theo bucket ⇒ query không có gì đúng để cộng |

### 3.2 `rows_var` — lỗi hay gặp nhất

Engine đặt:

```python
pre_resolved = dict(self.inputs)
pre_resolved["rows"] = [{cost_bucket, line_total}, …]
```

⇒ `rows_var` phải là `"rows"` (hoặc bỏ trống, mặc định là `rows`).

> 🔴 Tài liệu cũ ghi `rows_var = "bom_result"` là **SAI**. Handler đi tìm
> `resolved_so_far["bom_result"]` → không thấy → trả `default_value` (0) **mà không báo lỗi**.
> Triệu chứng: cấu hình đúng mọi thứ, bucket vẫn ra 0.

### 3.3 `key_field` / `key_value`

- `key_value` **literal**: 1 config cho 1 bucket — `"key_value": "VL_NHOM"`.
- `key_value` **template** `{{binding.variable_name}}`: engine đặt `variable_name = bucket_code`
  cho từng binding ⇒ **1 config dùng chung cho mọi bucket**, mỗi bucket tự lọc đúng tổng của mình.
  (Bản vá 2026-11-20 truyền `binding` vào bước resolve `key_value`.)
- `key_value` **rỗng**: không lọc → cộng **toàn bộ** `line_total` của mọi bucket. Chỉ dùng khi
  thật sự muốn tổng tất cả (thường là việc của bucket AGGREGATE ở B6, không phải B5).

So khớp là **so chuỗi sau khi strip** (`str(a).strip() == str(b).strip()`), không phân biệt
khoảng trắng thừa.

### 3.4 `value_field` / `sum_field`

- Cả hai cùng nghĩa: field để cộng. `value_field` được ưu tiên.
- `AL Cost Bucket` **bắt buộc** `sum_field` (kiểm khi Lưu) ⇒ khuyến nghị khai **cả hai** cùng
  `line_total` để vừa lưu được vừa đúng chuẩn.
- B5 chỉ có `line_total`. ⛔ Không cộng được `qty`, khối lượng, diện tích… vì engine **không
  truyền** các field đó cho FB.

### 3.5 `aggregate`

| Giá trị | Ý nghĩa | Ghi chú ở B5 |
|---|---|---|
| `sum` | Tổng | Mặc định, dùng nhiều nhất |
| `avg` | Trung bình cộng các `value_field` khác `None` | |
| `min` / `max` | Nhỏ nhất / lớn nhất | |
| `count` | Đếm số dòng khớp | Không cần `value_field`; không dòng nào → trả **0** (không phải `default_value`). Đếm thô từng dòng, không gộp theo bucket |
| `first` / `last` | Giá trị đầu / cuối theo thứ tự rows engine truyền | Thứ tự rows = thứ tự `bom_result` |

### 3.6 `default_value`

Trả về khi:

- `rows_source=resolved` mà **không tìm thấy** `rows_var` trong context (hoặc không phải list) —
  ví dụ đặt sai `rows_var`;
- rows rỗng sau khi lọc;
- `value_field` rỗng (trừ `count`);
- không có giá trị số nào cộng được.

Đặt `"default_value": 0` nếu muốn im lặng; đặt số khác nếu muốn "phát hiện được" cấu hình hỏng
khi nhìn kết quả.

### 3.7 `filters`

Danh sách điều kiện, **kết hợp AND** với `key_field/key_value`:

```json
"filters": [["cost_bucket", "!=", "VL_PK"]]
```

- Mỗi điều kiện: `[field, op, value]`.
- `op` hỗ trợ: `=`, `==`, `!=`, `<>`, `>`, `<`, `>=`, `<=`, `like`, `in`, `not in`.
- `value` hỗ trợ template `{{row.field}}`, `{{doc.field}}`, `{{resolved.field}}`
  (⚠️ **chưa** hỗ trợ `{{binding.*}}` trong `filters` — chỉ `key_value` có scope này).
- Ở B5 chỉ có 2 field để lọc: `cost_bucket`, `line_total` (rows engine truyền chỉ có 2 field).
- Với `doctype_query`, `filters` còn được truyền xuống `frappe.get_all` (value dạng `{doc.x}` /
  `{resolved.x}` một ngoặc) — không áp dụng ở B5.

### 3.8 Các tham số ⛔ không dùng cho B5

`snapshot_doctype`, `snapshot_name`, `snapshot_field`, `rows_path`, `child_table_field`,
`doctype`, `fields`, `order_by`, `limit` — chỉ có nghĩa với `rows_source` khác `resolved`.
Điền vào config B5 không gây lỗi nhưng **không có tác dụng**; đừng dựa vào chúng để lọc dữ liệu.

---

## 4. Ví dụ copy-paste

Mở `AL Cost Bucket` → chọn bucket → dán vào ô **Source Config** (JSON).
Nhớ: `Source Type = aggregate_from_items`.

### 4.1 `VL_NHOM` — cố định 1 bucket

```json
{
  "rows_source": "resolved",
  "rows_var": "rows",
  "key_field": "cost_bucket",
  "key_value": "VL_NHOM",
  "value_field": "line_total",
  "sum_field": "line_total",
  "aggregate": "sum",
  "default_value": 0
}
```

### 4.2 `VL_KINH`, `VL_VTP`, `VL_PK` — cùng một khuôn, đổi `key_value`

| Bucket | `key_value` |
|---|---|
| `VL_KINH` | `"VL_KINH"` |
| `VL_VTP` | `"VL_VTP"` |
| `VL_PK` | `"VL_PK"` |

### 4.3 Một config dùng chung cho MỌI bucket (`{{binding.variable_name}}`)

Engine đặt `variable_name = bucket_code` trước khi resolve ⇒ dán y nguyên config này cho mọi
bucket LEAF, mỗi bucket tự ra tổng riêng:

```json
{
  "rows_source": "resolved",
  "rows_var": "rows",
  "key_field": "cost_bucket",
  "key_value": "{{binding.variable_name}}",
  "value_field": "line_total",
  "sum_field": "line_total",
  "aggregate": "sum",
  "default_value": 0
}
```

Kiểm nhanh: `VL_NHOM` phải khác `VL_KINH`; nếu mọi bucket ra **cùng một số** và số đó bằng tổng
toàn bộ `line_total` ⇒ `key_value` đang rỗng/không resolve.

### 4.4 Ví dụ có `filters`

`VL_VTP` chỉ cộng các dòng ≤ 5.000.000 (loại dòng giá trị lớn bất thường):

```json
{
  "rows_source": "resolved",
  "rows_var": "rows",
  "key_field": "cost_bucket",
  "key_value": "VL_VTP",
  "value_field": "line_total",
  "sum_field": "line_total",
  "aggregate": "sum",
  "filters": [["line_total", "<=", 5000000]],
  "default_value": 0
}
```

### 4.5 Ví dụ `transform` (hiếm dùng)

Cộng xong làm tròn 0 chữ số thập phân:

```json
{
  "rows_source": "resolved",
  "rows_var": "rows",
  "key_field": "cost_bucket",
  "key_value": "{{binding.variable_name}}",
  "value_field": "line_total",
  "sum_field": "line_total",
  "aggregate": "sum",
  "transform": {"round": 0}
}
```

---

## 5. Sáu lỗi thường gặp

| # | Cấu hình sai | Triệu chứng | Cách sửa |
|---|---|---|---|
| 1 | `rows_var = "bom_result"` (theo tài liệu cũ) | Bucket ra **0**, không có lỗi | Đổi thành `"rows"` hoặc bỏ hẳn `rows_var` |
| 2 | `key_value` để trống | **Mọi bucket cùng một số** = tổng toàn bộ `line_total` | Điền literal hoặc `{{binding.variable_name}}` |
| 3 | Đặt `aggregate_from_items` cho bucket **AGGREGATE** (TONG_VL, GIA_THANH…) | Không có tác dụng, không có số | Bỏ config; bucket AGGREGATE do `AL Cost Template` tính ở B6 |
| 4 | Chỉ khai `value_field`, thiếu `sum_field` | **Không Lưu được** bucket ("aggregate_from_items cần 'sum_field'") | Thêm `"sum_field": "line_total"` (khai cả hai càng tốt) |
| 5 | Mong cộng `qty`/khối lượng/diện tích | Ra 0 hoặc sai | Không hỗ trợ: engine chỉ truyền `cost_bucket` + `line_total` cho FB |
| 6 | `source_type` khác `aggregate_from_items` (vd `formula`) trên bucket LEAF | Cảnh báo `bucket_source_type_chua_ho_tro:<code>`, vẫn cộng Python | Đổi `source_type` sang `aggregate_from_items` nếu muốn dùng config |

---

## 6. Cách kiểm

1. Mở **Quotation Item** đã tính giá → xem nhóm bucket (B5) và giá (B6).
2. So số bucket LEAF với tổng `line_total` từng nhóm (nếu không dùng `filters` thì phải bằng).
3. Nếu số lệch / ra 0:
   - Mở **Error Log**, tìm tiêu đề `AlumGlass: resolve cost bucket qua FB lỗi (B5)` — lỗi resolve
     (config sai, thiếu app formula_builder…) hoặc `AlumGlass: đọc AL Cost Bucket lỗi (B5)`.
   - Mở `al_bom_result.errors` của dòng báo giá → tìm khoá
     `bucket_source_type_chua_ho_tro:<code>`.
   - Kiểm `source_type` + JSON `source_config` của bucket (nhớ `rows_var="rows"`,
     `key_value` không rỗng, có `sum_field`).
4. Muốn **tắt** đường FB cho 1 bucket (quay về cộng Python): xoá trắng `source_config`
   (hoặc đổi `source_type` sang giá trị khác `aggregate_from_items`).

> ℹ️ Đổi cấu hình **không cần migrate**: đọc lại `AL Cost Bucket` mỗi lần engine chạy. Chỉ cần
> tính lại báo giá.
