# AL Bom Item — Cấu hình từng dòng & đường đi mapping của engine
>
> 🔴 **Cập nhật 2026-11-27 (B2/R3):** `AL Variable Settings` **đã ngừng dùng**. Ba loại biến nay nằm
> trong **`AL Variable Library`**: biến người dùng nhập = bật **“Người dùng nhập”** (`is_input`);
> biến theo dòng = **Category = “Row Literals”**; còn lại = biến cấu hình. `default_profile` →
> **`AL Variable Profile.is_default`**; `preview_doctype` → **`AL Variable Profile.preview_doctype`**.
> Mọi câu bên dưới nhắc “mở `AL Variable Settings`” là **lịch sử** — trạng thái hiện tại xem
> [thiết kế gộp cấu hình](design/gop-noi-cau-hinh-bien-va-tinh-toan.md).


> **Dành cho:** admin/nghiệp vụ cấu hình BOM · dev mới cần biết "dòng cấu hình này đi đâu".
> **Mục tiêu:** đọc xong biết **mỗi ô cấu hình ảnh hưởng gì**, và **tra được** dòng đó chạy qua
> bước nào của engine.
>
> **Nguồn đối chiếu:** mã trong repo `alumglass` (nhánh `master`, đọc ngày 2026-11-20).
> Mọi khẳng định đều kèm `file:dòng` hoặc tên hàm. Chỗ chưa kiểm được ghi rõ ở mục 11.
>
> **Ví dụ mẫu:** bộ seed `BS-CDMQ-2C` — `alumglass/setup/seed_demo_data.py`, hàm
> `_bom_items_and_set()`.
>
> ⚠️ **Số liệu ở mục 7 là ví dụ minh hoạ (số giả định)**, tính tay theo đúng công thức trong mã,
> ⛔ không phải số đo trên site. Golden của bộ 2C nằm ở tài liệu khác — xem
> `docs/quotation-pricing-flow.md`.

---

## MỤC LỤC

1. [Ví dụ mẫu để bám vào](#1-ví-dụ-mẫu-để-bám-vào)
2. [Từng field của AL Bom Item](#2-từng-field-của-al-bom-item)
3. [Chọn nẹp kính / keo bằng Rule — cách tìm và cách gõ](#3-chọn-nẹp-kính--keo-bằng-rule--cách-tìm-và-cách-gõ)
4. [Vì sao lấy được từ AL Glass Master](#4-vì-sao-lấy-được-từ-al-glass-master)
5. [Bản vá lọc gợi ý chéo dòng có làm mất gợi ý theo dòng kính đại diện không?](#5-bản-vá-lọc-gợi-ý-chéo-dòng-có-làm-mất-gợi-ý-theo-dòng-kính-đại-diện-không)
6. [Đường đi mapping — từng bước B0 → B6](#6-đường-đi-mapping--từng-bước-b0--b6)
7. [Ví dụ chạy từng bước với số liệu](#7-ví-dụ-chạy-từng-bước-với-số-liệu-minh-hoạ)
8. [Bảng "field nào ảnh hưởng giá"](#8-bảng-field-nào-ảnh-hưởng-giá)
9. [Lỗi thường gặp + cách kiểm](#9-lỗi-thường-gặp--cách-kiểm)
10. [Căn cứ tính giá — rule_trace, price_trace, explain_bom_line](#10-căn-cứ-tính-giá--rule_trace-price_trace-explain_bom_line)
11. [Phụ lục — bảng tra file/hàm & điểm chưa kiểm](#11-phụ-lục--bảng-tra-filehàm--điểm-chưa-kiểm)

---

## 1. Ví dụ mẫu để bám vào

Bộ `BS-CDMQ-2C` gồm 14 dòng AL Bom Item (`seed_demo_data.py`, `_bom_items_and_set`). Bốn dòng dưới
đây phủ đủ **4 cơ chế chọn mã** mà engine có; các dòng còn lại chỉ là biến thể.

| Slug | Cơ chế | Mã lấy từ đâu | Điểm đáng chú ý |
|---|---|---|---|
| `khung_ngang_tren` | Fixed | `item_code = XF55-KB-20` | Giá tra theo `price_base_item = NHOM-XINGFA` (mã đại diện), ⛔ không theo `item_code` |
| `kinh_tren` | Fixed | `item_code = KINH-LOWE-24` | Có `default_glass_master` + `ctx_inject_prefix`; sinh `glass_thick`/`glass_type` cho dòng khác đọc |
| `nep_kinh_tren` | Rule | `RULE-NEP-GLASSTHICK` + input `items.kinh_tren.glass_thick` | Mã **phụ thuộc dòng kính** — đổi kính là đổi mã nẹp |
| `vit` | Fixed | `item_code = VIT-TK-35X16`, qty `10*n_panel + 8` | `calc_pattern = COUNT` → `unit_qty = 1`, số lượng nằm hết ở công thức `qty` |

Dòng phụ kiện (`tay_nam`, `khoa`, `ban_le`) **⛔ không nằm trong AL Bom Set**. Chúng nằm ở
`AL Accessory Set` (`ACC-CDMQ-2C`) và được engine **append** vào danh sách dòng lúc chạy —
`_load_accessories()` (`bom_orchestrator.py:835`). Chi tiết ở mục 6, bước B2.

### 1.1 Cấu hình 4 dòng mẫu (rút gọn từ seed)

```json
// khung_ngang_tren — Fixed, giá theo mã đại diện
{
  "slug": "khung_ngang_tren", "category": "NHOM", "item_selection_mode": "Fixed",
  "item_code": "XF55-KB-20", "width": "W_mm", "height": null, "qty": "1",
  "calc_pattern": "LENGTH_TO_WEIGHT", "cost_bucket": "VL_NHOM",
  "price_type": "Item Price", "price_base_item": "NHOM-XINGFA"
}

// kinh_tren — Fixed, kính; sinh glass_thick/glass_type cho dòng khác
{
  "slug": "kinh_tren", "category": "KINH", "item_selection_mode": "Fixed",
  "item_code": "KINH-LOWE-24",
  "width": "W_mm - 2*OFFSET_FIXED", "height": "TransomHeight_mm - OFFSET_FIXED", "qty": "1",
  "calc_pattern": "AREA", "cost_bucket": "VL_KINH",
  "price_type": "Fixed", "price_base_item": null,
  "default_glass_master": "KINH-LOWE-24", "ctx_inject_prefix": "kinh_tren"
}

// nep_kinh_tren — Rule: mã chọn theo độ dày kính của dòng kinh_tren
{
  "slug": "nep_kinh_tren", "category": "NHOM", "item_selection_mode": "Rule",
  "item_rule": "RULE-NEP-GLASSTHICK", "rule_input_expr": "items.kinh_tren.glass_thick",
  "width": "2*(items.kinh_tren.width + items.kinh_tren.height)", "height": null, "qty": "2",
  "calc_pattern": "LENGTH_TO_WEIGHT", "cost_bucket": "VL_NHOM",
  "price_type": "Item Price", "price_base_item": "NHOM-XINGFA"
}

// vit — Fixed, đếm theo số cánh
{
  "slug": "vit", "category": "VTP", "item_selection_mode": "Fixed",
  "item_code": "VIT-TK-35X16", "width": null, "height": null,
  "qty": "10*n_panel + 8", "calc_pattern": "COUNT", "cost_bucket": "VL_VTP",
  "price_type": "Fixed", "price_base_item": null
}
```

### 1.2 Dòng phụ kiện — cấu hình ở nơi khác

```json
// AL Accessory Set ACC-CDMQ-2C → items (seed_demo_data.py, _accessory_set)
{ "slug": "tay_nam", "item_code": "KL-MZS20",  "qty": 1, "qty_formula": "" },
{ "slug": "khoa",    "item_code": "KL-KHOA-01","qty": 1, "qty_formula": "" },
{ "slug": "ban_le",  "item_code": "KL-T-MJ06", "qty": 0,
  "qty_formula": "lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel" }
```

Engine biến mỗi dòng này thành một dòng dữ liệu nội bộ với:
`calc_pattern = "COUNT"`, `cost_bucket = "VL_PK"`, `item_selection_mode = ""`, `category = ""`
(`_load_accessories`, `bom_orchestrator.py:861-888`). Nghĩa là phụ kiện **không có** cơ chế Rule,
**không có** nhóm kính, **không có** `price_base_item` — giá lấy thẳng `Item Price` của `item_code`
hoặc `unit_price` khai trực tiếp.

---

## 2. Từng field của AL Bom Item

Nguồn field: `alumglass/al_bom_engine/doctype/al_bom_item/al_bom_item.json`.

### 2.1 Bảng tổng — field nào engine có đọc

| Field | Kiểu | Ai đọc | Trạng thái |
|---|---|---|---|
| `slug` | Link AL Slug Library | Engine (khoá biến) + validate | ✅ Đang dùng |
| `category` | Link AL Material Category | Validate + B2 + B4 | ✅ Đang dùng (nhiều vai) |
| `line_name` | Data | Không ai | Chỉ hiển thị trên form |
| `is_active` | Check | Engine gián tiếp qua snapshot | ✅ Đang dùng |
| `show_condition` | Small Text (công thức) | B3 (tính) — **không có nơi tiêu thụ** | ⚠️ Chỉ tính, chưa lọc dòng |
| `cost_bucket` | Link AL Cost Bucket | B5 | ✅ Đang dùng |
| `item_selection_mode` | Select Fixed/Rule/Formula | B2 | ✅ `Fixed` + `Rule`; ⚠️ `Formula` chưa có đường chạy |
| `item_code` | Link Item | B2 | ✅ (mode Fixed; cũng là giá trị dự phòng của mode Rule) |
| `item_rule` | Link AL Rule | B2 | ✅ (mode Rule) — Lưu chặn nếu rule không phải `result_type = ITEM` |
| `rule_input_expr` | Small Text | B2 | ✅ (mode Rule) |
| `item_fallback` | Link Item (hidden) | Không ai | ❌ Khai báo, chưa dùng |
| `item_condition_formula` | Small Text | Chỉ validate | ❌ Không đổi mã item ở runtime |
| `allow_sales_override` | Check (hidden) | Không ai | ❌ Khai báo, chưa dùng |
| `override_item_group` | Link (hidden) | Không ai | ❌ Khai báo, chưa dùng |
| `allow_substitute` | Check (hidden) | Không ai | ❌ Khai báo, chưa dùng |
| `substitute_item_group` | Link (hidden) | Không ai | ❌ Khai báo, chưa dùng |
| `width`, `height` | Small Text (công thức) | B3 | ✅ |
| `qty` | Small Text (công thức) | B3 | ✅ Bắt buộc |
| `calc_pattern` | Link AL Quantity Calc Method | B3 + B4 | ✅ |
| `input_vars` | JSON | B3 | ✅ |
| `price_type` | Select | **Chỉ điều khiển form** | ⚠️ Engine không đọc |
| `price_base_item` | Link Item | B2 (giá) | ✅ |
| `price_rule` | Link (hidden) | Không ai | ❌ Khai báo, chưa dùng |
| `price_list` | Link Price List | **Không ai** | ❌ Khai báo, chưa dùng |
| `fixed_price` | Currency (hidden) | Không ai | ❌ Khai báo, chưa dùng |
| `cut_fee_pct` | Float (hidden) | Không ai | ❌ Khai báo, chưa dùng |
| `default_glass_master` | Link AL Glass Master | B2 | ✅ |
| `ctx_inject_prefix` | Data | Chỉ validate | ⚠️ Engine không đọc |
| `panel_count_formula` | Small Text (hidden) | Không ai | ❌ Khai báo, chưa dùng |
| `qty_per_panel_formula` | Small Text (hidden) | Không ai | ❌ Khai báo, chưa dùng |
| `panel_glass_override_allowed` | Check (hidden) | Không ai | ❌ Khai báo, chưa dùng |
| `formula_set` | Link (hidden) | Không ai | ❌ Khai báo, chưa dùng |
| `default_color` | Link AL Color Standard | B2 | ✅ |
| `supplier_location` | Data | B2 → B4 | ✅ (hiển thị) |
| `install_position` | Data | B2 → B4 | ✅ (hiển thị) |
| `cut_angle` | Data | B2 → B4 | ✅ (hiển thị) |
| `note` | Small Text | B2 → B4 | ✅ (hiển thị) |

> "Không ai" = `grep` toàn repo (`.py`, `.js`, `.html`) **không tìm thấy** chỗ đọc — ngoài file
> `al_bom_item.json` khai báo field và seed tạo dữ liệu.

---

### 2.2 Nhóm "danh tính dòng"

#### `slug` — ⚠️ quan trọng nhất, đổi là vỡ công thức

- **Ý nghĩa:** khoá của dòng. Engine sinh **tên biến phẳng** `{slug}__{field}` cho mọi field của
  dòng (B3, `b3_build_formulas`), và dùng chính tên đó khi công thức dòng khác tham chiếu chéo
  `items.<slug>.<field>`.
- **Ai đọc:** B2 (build `glass_data`, `row_literals` theo slug) · B3 (đặt tên biến, chuẩn hoá
  tham chiếu chéo) · B4 (đọc kết quả theo tên).
- **Giá trị mẫu:** `nep_kinh_tren` → biến `nep_kinh_tren__width`, `nep_kinh_tren__unit_qty`…
- **Ràng buộc:** slug phải **duy nhất** trong bộ — `ALBomSet._validate_slug_uniqueness()`
  (`al_bom_set.py:75`).
- **Lỗi thường gặp:** đổi slug sau khi đã viết công thức ở dòng khác ⇒ công thức cũ trỏ vào tên
  không còn tồn tại ⇒ kết quả 0. Đổi slug phải sửa mọi `items.<slug>...` liên quan.

#### `category` — Link AL Material Category

Không phải "nhãn cho đẹp": nó là **công tắc** quyết định 4 thứ.

| Vai trò | Nơi đọc |
|---|---|
| Cổng validate khi lưu (bắt buộc Item Code / Price Base Item / CTX prefix) | `ALBomItem.validate()` (`al_bom_item.py:84-166`) |
| Nhận diện **dòng kính** (nhóm `requires_glass_master`) | `glass_group_resolver.fetch_glass_category_codes()` |
| Lấy `default_scrap_pct` + `has_weight` cho dòng | B2 batch #4 (`bom_orchestrator.py:982-996`) |
| Lọc bộ pricing dimension áp cho mã hàng của dòng khi tra giá | `_dim_fieldnames_for_category()` (`bom_orchestrator.py:1300`) |

- **Giá trị mẫu:** `NHOM` (nhôm), `KINH` (kính), `VTP` (vật tư phụ), `PK` (phụ kiện).
- **Cờ trên category** (nguồn: `al_master_data/doctype/al_material_category/al_material_category.json`):
  `requires_item_code` · `requires_price_base_item` · `requires_glass_master` ·
  `requires_ctx_inject_prefix` · `has_weight` · `has_dimensions` · `default_calc_pattern` ·
  `default_cost_bucket` · `default_scrap_pct`.
- **Lỗi thường gặp:**
  - Chọn category sai ⇒ form không bắt buộc ô cần thiết, và dòng không được nhận là dòng kính ⇒
    `glass_thick = 0` cho mọi dòng phía sau.
  - `default_calc_pattern` / `default_cost_bucket` là **giá trị gợi ý** — engine **không** đọc hai
    field này lúc tính; nó dùng `calc_pattern` / `cost_bucket` **khai trên chính dòng**. Xem mục 11
    về việc form có tự điền hay không.

#### `line_name` — chỉ hiển thị

- **Ý nghĩa:** tên dòng cho người đọc.
- **Ai đọc:** **không ai trong engine**. Bảng kết quả (`get_result_display`) lấy nhãn từ
  `AL Slug Library.label`, ⛔ không lấy `line_name` — xem `_get_slug_labels()` (`api/__init__.py:1533`).
  `line_name` chỉ được dùng làm **nhãn của gợi ý chéo dòng** (mục 5), và làm **nhãn DỰ PHÒNG** của
  nhóm chọn kính trong dialog (`get_variable_set_for_bom` → `glass_groups.label`: nhãn slug library
  → `line_name` → `Item.item_name` → slug) khi dòng kính không có `default_glass_master` và slug
  chưa có nhãn — tránh phơi slug kỹ thuật ra dialog.
- **Giá trị mẫu:** `Nẹp kính trên`.
- **Lỗi thường gặp:** sửa `line_name` rồi chờ nhãn trên Preview đổi → **không đổi**. Muốn đổi nhãn
  hiển thị phải sửa `AL Slug Library.label`.

#### `is_active` — bị loại **trước khi** engine nhìn thấy

- **Ý nghĩa:** bật/tắt dòng khi chụp ảnh (snapshot) BOM Version.
- **Ai đọc:** `AL BOM Version._take_snapshots()` (`al_bom_version.py:108-138`) — dòng có
  `is_active = 0` **không được chép** vào `bom_set_snapshot`.
- **Hệ quả:** engine chỉ đọc từ snapshot (B2 dòng đầu). Vì vậy dòng `is_active = 0` **vẫn nằm trên
  Bom Set** nhưng **biến mất hoàn toàn** khỏi kết quả tính — không có cảnh báo, không có dòng 0.
- **Điều kiện có hiệu lực:** phải **xuất bản lại** BOM Version (hoặc tạo version mới) thì snapshot
  mới phản ánh thay đổi. Version đã Published là bất biến (`_guard_published_immutability`).
- **Lỗi thường gặp:** tắt dòng trên Bom Set → bấm Tính giá → vẫn ra như cũ, vì version đang dùng
  còn snapshot cũ. Xem mục 9.

---

### 2.3 Nhóm "chọn mã vật tư"

#### `item_selection_mode` — quyết định mã lấy từ đâu

| Giá trị | Engine làm gì | Nơi đọc |
|---|---|---|
| `Fixed` | Dùng thẳng `item_code` | B2 gom mã; `row_literals` |
| `Rule` | Gọi `AL Rule.resolve(input)` (chỉ rule `result_type = ITEM`); `input` lấy từ `rule_input_expr` | B2 batch #5 (`bom_orchestrator.py:1021-1049`) |
| `Formula` | **Không có nhánh xử lý nào.** Ngoài `Fixed`/`Rule` engine không tra mã item | `grep "item_selection_mode"` trong `bom_orchestrator.py` chỉ có 2 nhánh |

- **Giá trị mẫu:** `Rule` (dòng `nep_kinh_tren`).
- **Lỗi thường gặp:**
  - Chọn `Formula`, khai `item_condition_formula` ⇒ lưu được, nhưng **không dòng nào được chọn mã**
    ⇒ giá 0 (trừ khi dòng có sẵn `item_code`). `CONDITION_FORMULA_FIELDS` chỉ dùng để **validate cú
    pháp** khi lưu (`al_bom_item.py:12`, `al_bom_set.py:108-112`).
  - Đổi `Rule` → `Fixed` mà quên nhập `item_code` ⇒ validate chặn ngay khi lưu (category bật
    `requires_item_code`).

#### `item_code`

- **Ý nghĩa:** mã Item thật của dòng (mode `Fixed`).
- **Ai đọc:** B2 gom vào danh sách tra khối lượng + giá; là nguồn dự phòng cho giá khi
  `price_base_item` trống (`bom_orchestrator.py:1131-1134`).
- **Với mode `Rule`:** `item_code` khai sẵn **vẫn được dùng** nếu rule không resolve được — engine
  lấy literal `item_code` trước, chỉ ghi đè khi rule trả về mã (`bom_orchestrator.py:1154-1161`).
  Đây là "mã dự phòng" thực tế, ⛔ không phải field `item_fallback`.
- **Giá trị mẫu:** `XF55-KB-20`, `VIT-TK-35X16`.
- **Lỗi thường gặp:** nhập mã Item chưa có `weight_per_unit` ⇒ dòng tính theo **mét** thay vì **kg**
  (pattern `LENGTH_TO_WEIGHT` ra 0) — không báo lỗi.

#### `item_rule` + `rule_input_expr` — cơ chế "mã phụ thuộc dòng khác"

Xem hướng dẫn đầy đủ ở **mục 3**. Tóm tắt ràng buộc:

- `rule_input_expr` chỉ đúng **một định dạng** `items.<slug>.<field>` — validate regex
  `^items\.[\w-]+\.\w+$` ngay khi lưu (`al_bom_item.py:154-159`). Sai định dạng ⇒ **chặn lưu**.
- Input tra theo thứ tự: `glass_data[ref_slug][ref_field]` → `row_literals[ref_slug][ref_field]` → `0`
  (`_resolve_rule_input_for_item`, `bom_orchestrator.py:2061`).
- Cache theo **cặp** `(rule_code, rule_input)` — nhiều dòng cùng rule nhưng khác kính vẫn đúng.

#### `item_fallback` — ❌ khai báo nhưng engine **không đọc**

- **Ý nghĩa (theo tên):** mã dự phòng khi rule không trả kết quả.
- **Thực tế:** `grep` toàn repo không có chỗ đọc. "Dự phòng" duy nhất đang chạy là `item_code` khai
  sẵn trên dòng (xem ở trên).
- **Field ẩn trên form** (`hidden: 1`).

#### `item_condition_formula` — ❌ không đổi mã item

- **Ý nghĩa (theo tên):** công thức điều kiện chọn item khi mode = `Formula`.
- **Thực tế:** chỉ được đưa vào **validate cú pháp** (`CONDITION_FORMULA_FIELDS`,
  `al_bom_set.py:108-112`, trong `_validate_child_formulas`). Không có đoạn mã nào biến kết quả
  công thức thành mã item.
- **Lỗi thường gặp:** tưởng khai công thức trả `1` là dòng được chọn. Không có tác dụng.

#### `allow_sales_override` · `override_item_group` · `allow_substitute` · `substitute_item_group`

Nhóm quyền "cho sales đổi mã / dùng mã thay thế". **Cả 4 field ẩn trên form và không có nơi đọc
trong mã.** Khai vào chỉ nằm đó.

---

### 2.4 Nhóm "kích thước & số lượng"

#### `width`, `height` — công thức Formula Builder

- **Ý nghĩa:** kích thước 1 đơn vị (mm).
- **Ai đọc:** B3 — sinh formula `{slug}__width` / `{slug}__height`; sau đó
  `lookup_calc_pattern(calc_pattern, width, height, weight_per_unit, …)`.
- **Giá trị mẫu:** `W_mm - 2*OFFSET_FIXED` · `TransomHeight_mm - OFFSET_FIXED`.
- **Tham chiếu chéo:** `items.X.Y` được chuẩn hoá **về tên phẳng** `X__Y`
  (`_normalize_items_ref`, `bom_orchestrator.py:2306`) — ⛔ **không** phải truy cập dict lồng.
  Docstring của hàm ghi rõ vì sao: nếu đọc dict lồng thì chỉ thấy giá trị literal, field đã tính
  = 0 ⇒ nẹp/keo/gioăng ra 0.
- **Rỗng:** dòng không khai ⇒ B3 đặt sẵn `0` (tránh lỗi "biến không tồn tại").
- **Lỗi thường gặp:** dùng `items.kinh_tren.width` ở **dòng khai Rule input** — xem mục 3.3.

#### `qty` — **bắt buộc**

- **Ý nghĩa:** số đơn vị trong 1 sản phẩm (số cánh, số bộ…).
- **Ai đọc:** B3; `total_qty = unit_qty × qty` (× `(1 + scrap%/100)` nếu bộ có bật hao hụt).
- **Bắt buộc:** `ALBomItem.validate()` throw nếu rỗng (`al_bom_item.py:136-137`); JSON cũng `reqd: 1`.
- **Giá trị mẫu:** `2` · `2*n_panel` · `10*n_panel + 8`.
- **Lỗi thường gặp:** để trống ⇒ không lưu được. Muốn "1 đơn vị" phải ghi `1`, ⛔ không để trống.

> Tất cả `width`/`height`/`qty`/`show_condition` là **field công thức** (`FORMULA_FIELDS`,
> `al_bom_item.py:11`). Cú pháp sai bị chặn **ngay khi lưu AL Bom Set**
> (`_validate_child_formulas`, `al_bom_set.py:91-116`), ⛔ không đợi tới lúc báo giá.

#### `calc_pattern` — Link AL Quantity Calc Method

- **Ý nghĩa:** công thức quy đổi `(width, height, weight_per_unit)` → **số đơn vị tính**.
- **Sinh ra:** `unit_qty = lookup_calc_pattern(code, width, height, weight_per_unit, {biến phụ})`
  (`bom_orchestrator.py:2124-2131`).
- **Resolver:** DB-first — đọc `calc_fn` của record; không có thì rơi về bảng built-in
  `PATTERN_FORMULAS` (14 mã) trong `formula_handlers.py:28-46`; không có nữa thì lỗi.
- **Giá trị mẫu:** `LENGTH_TO_WEIGHT` (kg = m × kg/m) · `AREA` (m²) · `COUNT` (luôn 1).
- **`output_unit`:** B4 đọc `output_unit` của pattern để điền cột ĐVT
  (`bom_orchestrator.py:2257-2268`).
- **Lỗi thường gặp:**
  - Để trống `calc_pattern` ⇒ `lookup_calc_pattern("")` lỗi ⇒ engine ghi lỗi cho dòng và trả **0**
    (engine cấu hình `on_error="default"`, `default_value=0`). Dòng vẫn hiện, tiền = 0.
  - Chọn pattern sai nhóm với category (vd nhôm dùng `AREA`) ⇒ số lượng đúng đơn vị nhưng sai
    bản chất — không có cảnh báo.

#### `input_vars` — biến phụ cho pattern

- **Ý nghĩa:** JSON object `{tên_biến: giá trị}` cấp cho pattern (vd `piece_length`, `depth`,
  `spacing`).
- **Ai đọc:** B3. Chỉ **biến có trong danh sách `input_vars` của pattern** mới được truyền; biến lạ
  bị bỏ qua an toàn.
- **Tự backfill:** khi lưu dòng (và khi lưu Bom Set), hook `backfill_input_vars` thêm key thiếu với
  giá trị `""` (`al_bom_item.py:47-73`; `hooks.py:70-72`).
- **Thứ tự ưu tiên giá trị** (`bom_orchestrator.py:2088-2104`):
  1. `input_vars` của **dòng**
  2. biến **toàn cục** người dùng đã nhập (vd `piece_length` ở cấp báo giá)
  3. `row_literals` của dòng
  4. `0`
- **Lỗi thường gặp:** nhập biến phụ ở cấp báo giá nhưng **pattern không khai biến đó** ⇒ không được
  truyền, pattern dùng mặc định của nó.

---

### 2.5 Nhóm "giá"

#### `price_type` — ⚠️ **chỉ để hiện/ẩn ô trên form**, engine không đọc

- **Ý nghĩa thật:** chọn field nào hiện ra trên form (`depends_on` của `price_base_item`,
  `price_rule`, `price_list`, `fixed_price`).
- **Bằng chứng:** `al_bom_item.py:100-107` ghi rõ engine **không** đọc `price_type` khi tra giá;
  `grep` trong `bom_orchestrator.py` không có `price_type`.
- **Hệ quả thực tế:** đặt `price_type = Rule` hay `Fixed` **vẫn tra giá theo `price_base_item`**
  (trống thì theo `item_code`). Hai giá trị `Rule`/`Fixed` **chưa từng có mã nào xử lý**.
- **Lỗi thường gặp:** chọn `Fixed` để "nhập giá tay" ⇒ không có ô nhập giá tay nào được dùng
  (`fixed_price` cũng không ai đọc) ⇒ vẫn ra giá từ bảng giá.

#### `price_base_item` — mã **đại diện** để tra bảng giá

- **Ý nghĩa:** mã Item mang bảng giá composite (theo màu / xuất xứ / độ dày / bề mặt). Nhiều dòng
  nhôm khác nhau thường dùng **cùng** một mã đại diện (`NHOM-XINGFA`).
- **Ai đọc:** B2 — `unit_price = prices[price_base_item]`, trống thì `prices[item_code]`
  (`bom_orchestrator.py:1131-1134`).
- **Bắt buộc:** khi category bật `requires_price_base_item` — validate throw
  (`al_bom_item.py:108-117`). Thông điệp lỗi đã ghi rõ "không phải Item Code của chính dòng này".
- **Lỗi thường gặp:** để trống ⇒ **lặng lẽ** lùi về `item_code` ⇒ mất phụ phí composite
  (màu/xuất xứ/độ dày/bề mặt) ⇒ **tính thiếu tiền mà không có cảnh báo**. Đây là lý do cổng
  validate này bỏ điều kiện `price_type == "Item Price"`.

#### `price_list` — ❌ khai trên dòng nhưng engine **không đọc**

- **Thực tế:** bảng giá lấy từ **binding** `aluminum_price_composite` (`source_config.price_list`);
  không có binding thì lấy từ **Selling Settings** (`_default_price_list()`,
  `bom_orchestrator.py:159-166`; `_active_price_list()`, `:1462`).
- **Lỗi thường gặp:** đổi `price_list` trên dòng để đổi giá ⇒ **không có tác dụng**. Muốn đổi phải
  đổi cấu hình binding hoặc Selling Settings.

#### `price_rule`, `fixed_price` — ❌ không ai đọc (đều ẩn trên form)

Cùng nhóm "khai báo nhưng chưa dùng". Nếu ai cấu hình hai field này và thấy giá không đổi: đúng như
mã đang chạy.

#### `cut_fee_pct` — ❌ không ai đọc trên AL Bom Item (ẩn)

`grep` chỉ thấy tên này ở `formula_builder/templates.py` (tham số của hàm dựng template) — **không
liên quan** tới field trên dòng BOM. Dòng BOM không có phí cắt riêng.

---

### 2.6 Nhóm "kính"

Chi tiết cơ chế lấy số liệu kính: **mục 4**.

#### `default_glass_master` — mã kính **mặc định** cho dòng/vị trí

- **Ý nghĩa:** mã `AL Glass Master` mặc định. Cung cấp bộ thông số kính cho dòng và cho các dòng
  phụ thuộc: `glass_thick` (`total_thick_mm`), `glass_type`, `max_area_m2`.
- **Không bắt buộc** (từ V6 P11): để trống thì người lập báo giá chọn kính theo từng vị trí trong
  dialog "Kính theo vị trí"; chưa chọn ⇒ `glass_thick = 0` **hiện rõ trên kết quả**, ⛔ không âm
  thầm sai (`al_bom_item.py:119-127`). *(Nhưng xem mục 4.3 — hậu quả của `0` phụ thuộc loại rule.)*
- **Giá trị mẫu:** `KINH-LOWE-24` (dày 24 mm, loại `LOWE`).

#### `ctx_inject_prefix` — ⚠️ chỉ validate, engine **không đọc**

- **Ý nghĩa (theo tên):** tiền tố để bơm biến vào context.
- **Thực tế:** `grep` toàn repo: chỉ có (a) validate bắt buộc khi category bật
  `requires_ctx_inject_prefix` (`al_bom_item.py:130-133`), (b) trả về cho client qua
  `get_category_requirements()`. **Không** có dòng nào trong engine đọc field này.
- **Lỗi thường gặp:** điền `kinh_tren` (như seed) và chờ biến `kinh_tren__*` xuất hiện "nhờ" nó —
  biến đó xuất hiện là do cơ chế `{slug}__{field}` ở B3, ⛔ không phải do field này.

#### `panel_count_formula`, `qty_per_panel_formula`, `panel_glass_override_allowed`

❌ Ẩn trên form, **không có nơi đọc** trong mã hiện tại. Ghi chú ở
`public/js/formula_setup.js:250` chỉ nói về việc build lại asset, không phải logic tính.

---

### 2.7 Nhóm "màu & hiển thị"

#### `default_color` — màu đại diện, **có ảnh hưởng giá**

- **Ý nghĩa:** mã `AL Color Standard` cố định/mặc định cho dòng. Trống = dòng **luôn dùng 1 màu cố
  định**, không tham gia nhóm chọn màu (`color_group_rep` trả `None`).
- **Ai đọc:** B2 — resolve theo vị trí rồi **ghi đè biến màu** khi tra giá
  (`_compute_color_price_overrides`, `bom_orchestrator.py:1423`), và đưa vào `row_literals["color"]`
  để hiển thị.
- **Ảnh hưởng giá thế nào:** màu được ghi vào biến dimension (vd `aluminum_color`) ⇒ dòng `Item Price`
  có dimension màu tương ứng được chọn; hoặc hệ số multiplier của màu được nhân (mode
  `multiplier_chain`).
- **Thứ tự resolve** — `_resolve_color_override` (`bom_orchestrator.py:1914`): `color_master_map[vị
  trí]` → mã màu global → chính `default_color`.
- **Giới hạn đã biết:** ≥2 dòng **khác màu** nhưng dùng **chung** `price_base_item` ⇒ dòng xử lý sau
  ghi đè; muốn tách giá theo 2 màu cho cùng 1 mã nhôm phải dùng **`price_base_item` khác nhau**
  (docstring `_compute_color_price_overrides`).
- **Lỗi thường gặp:** nhập mã màu **chưa tích "Màu đại diện"** ⇒ dòng không được coi là đại diện
  trong dialog chọn màu.

#### `supplier_location` · `install_position` · `cut_angle` · `note`

- **Ai đọc:** B2 đưa nguyên văn vào `row_literals`, B4 đưa nguyên văn vào `bom_result`, hiển thị ở
  bảng Preview. **Không tham gia tính tiền.**
- **Lỗi thường gặp:** mong các field này lọc/nhóm dòng — không có cơ chế đó.

#### `cost_bucket` — quyết định dòng vào Nhóm chi phí nào

- **Ý nghĩa:** Link `AL Cost Bucket`; B5 cộng `line_total` của dòng vào Nhóm này.
- **Giá trị mẫu:** `VL_NHOM` · `VL_KINH` · `VL_VTP` · `VL_PK`.
- **Trống = không vào Nhóm nào** ⇒ tổng vật liệu **thiếu** đúng phần của dòng đó, nhưng giá bán vẫn
  tính được từ các Nhóm khác ⇒ **sai tiền mà không có cảnh báo**. Xem mục 9.
- **Chi tiết bucket & nguồn resolve của từng Nhóm:** xem `docs/cost-bucket-source-config.md`
  (tài liệu của DEV1) — ở đây chỉ nói phần liên quan tới dòng Bom Item.

#### `show_condition` — ⚠️ **được tính, nhưng chưa dùng để ẩn dòng**

- **Ý nghĩa (theo tên):** điều kiện hiện dòng.
- **Thực tế:** nằm trong `FORMULA_FIELDS` (`al_bom_item.py:11`) nên B3 **có sinh**
  `{slug}__show_condition`. Nhưng `grep` toàn app **không có nơi tiêu thụ** giá trị này — B4 vẫn
  đưa **mọi** dòng vào `bom_result`, B5 vẫn cộng tiền.
- **Kết luận đúng để ghi vào tài liệu cấu hình:** *hiện chỉ tính, chưa lọc dòng.* Muốn bỏ 1 dòng
  khỏi kết quả phải dùng **`is_active`** (rồi xuất bản lại version) hoặc xoá dòng khỏi Bom Set.

#### `formula_set` — ❌ ẩn, không ai đọc

`grep "formula_set"` chỉ ra tên file/module `formula_setup.js` — không phải field này.

---

## 3. Chọn nẹp kính / keo bằng Rule — cách tìm và cách gõ

Đây là cơ chế hay bị cấu hình sai nhất, vì **3 lớp khác nhau** cùng tham gia: bảng rule (chọn mã),
biểu thức trỏ dòng kính, và bộ gợi ý trên form.

### 3.1 Hai kiểu rule — `AL Rule` (result_type = ITEM)

Nguồn: `alumglass/al_formula_rules/doctype/al_rule/al_rule.py` (Chặng 2B gộp
`AL Dynamic Item Rule` vào `AL Rule`; doctype cũ chỉ còn để rollback). Dòng con
dùng chung `AL Rule Threshold Row` / `AL Rule Lookup Row` — cột kết quả là
`result_item`.

| Kiểu | Cách khớp | Ghi chú |
|---|---|---|
| `THRESHOLD` | Sắp dòng theo `from_value` **tăng dần**, duyệt tìm `from <= val < to` (**nửa mở**) | Chạm biên ⇒ **dải trên thắng**. Dữ liệu cũ khai **đóng hai đầu** còn lưới tương thích: nếu nửa mở không khớp dòng nào, thử lại `val == to_value` ⇒ trả dòng đó |
| `LOOKUP` | `str(row.key_field) == str(input)` — **chuỗi khớp chính xác** | Không trim, không phân biệt hoa/thường — khác một ký tự là trượt |

- `resolve(input)` trả **`None`** khi input rỗng (`None` hoặc `""`) hoặc không khớp dòng nào.
- Validate khi lưu rule: `THRESHOLD` phải có ≥1 dòng, `from <= to`, **không chồng lấp** (chạm biên
  `to == next.from` là hợp lệ). **Khe hở** giữa 2 dải chỉ **cảnh báo cam** (`msgprint`,
  `_warn_threshold_gaps`) — ⛔ không chặn lưu.
- `THRESHOLD` không có dòng nào phủ giá trị (vd dải bắt đầu từ `0.01`) ⇒ `None`.
- `LOOKUP` với input rỗng ⇒ `None` — **không** rơi vào dòng đầu.

### 3.2 Ví dụ seed thật

`setup/seed_demo_data.py::_dynamic_item_rules`:

| Rule | Kiểu | Dữ liệu |
|---|---|---|
| `RULE-NEP-GLASSTHICK` | THRESHOLD | `[0, 10.38] → C3209-20` · `[10.39, 16] → C3210-20` · `[16.01, 999] → C3211-20` |
| `RULE-KEO-GLASSTYPE` | LOOKUP | `LOWE → KEO-TT-01` · `DON → KEO-TT-02` |

🔴 **Dữ liệu mẫu này CÓ KHE:** `10.38 → 10.39` và `16 → 16.01`.

| Giá trị độ dày | Kết quả |
|---|---|
| `10.38` | Khớp `[0, 10.38)`? **Không** (nửa mở). Lưới tương thích: `val == to_value` ⇒ **C3209-20** |
| `10.385` | **Rơi vào khe** — `10.385` không nằm trong dải nào, cũng không bằng `to` nào ⇒ **`None`** |
| `10.39` | Khớp `[10.39, 16)` ⇒ C3210-20 |
| `16.0` | Khớp lưới tương thích (`== 16`) ⇒ **C3210-20** |
| `16.005` | Rơi vào khe ⇒ **`None`** |
| `16.01` / `24` | Khớp `[16.01, 999)` ⇒ **C3211-20** |

**Khuyến nghị:** khai **liền dải** — dải sau bắt đầu đúng bằng `to` của dải trước. Ví dụ đúng:
`[0, 10.38]` · `[10.38, 16]` · `[16, 999]`. Khi đó biên luôn xác định và không còn giá trị nào rơi
vào khe.

### 3.3 Cách gõ `rule_input_expr`

Chỉ có hiệu lực khi dòng có `item_selection_mode = Rule`. Engine nhận **đúng một dạng**:

```text
items.<slug>.<field>
```

Regex engine dùng khi tra: `items\.(\w[\w-]*)\.(\w+)` — `_resolve_rule_input_for_item`
(`bom_orchestrator.py:2061`). Regex lúc **lưu** chặt hơn một chút:
`^items\.[\w-]+\.\w+$` (`al_bom_item.py:155`).

**Cách gõ trên form:**
1. Chọn dòng kính trong danh sách gợi ý (slug dòng kính) — gợi ý có sẵn dạng
   `items.<slug>.total_thick_mm` (tên chuẩn), `items.<slug>.glass_thick` (tên cũ, vẫn chạy)
   và `items.<slug>.glass_type`.
2. Field đích nên là **`total_thick_mm`** hoặc **`glass_thick`** (rule `THRESHOLD` — so số)
   hoặc **`glass_type`** (rule `LOOKUP` — so chuỗi). Hai tên đầu trả **cùng một giá trị**
   (xem mục 4.5) — rule đã viết bằng `glass_thick` ⛔ không cần sửa.

**Ba kiểu gõ SAI — engine không nhận, rule không chạy:**

| Gõ | Vì sao sai | Kết quả |
|---|---|---|
| `glass_thick` (thiếu tiền tố) | Không khớp regex ⇒ `_resolve_rule_input_for_item` trả `None` ⇒ bỏ qua dòng | Rule không chạy. **Không có cảnh báo** (bộ kiểm chỉ báo khi thấy ref `items.x.y`) |
| `items[0].glass_thick` | Gợi ý dạng **chỉ số** có xuất hiện trong autocomplete, nhưng regex của rule **không nhận** dạng này | Rule không chạy |
| `items.kinh_tren.glass_thick` nhưng dòng `kinh_tren` không còn | Slug không tồn tại trong bộ | Resolve ra `0`; có **cảnh báo cam** khi lưu Bom Set (`validate_rule_input_expr`) |

> ⚠️ Chú thích trong `formula_validate.validate_rule_input_expr` (dòng 124-125) nói rằng khi
> **không có** ref `items.x.y` thì "engine fallback `glass_thick`/`glass_type` của CHÍNH dòng đó".
> Mã đang chạy **không** làm vậy: `_resolve_rule_input_for_item` trả `None` ⇒ batch #5 `continue`.
> Hành vi fallback đó thuộc về hàm cũ `_resolve_rule_input()` — **không có nơi gọi**. Nếu đọc mã,
> tin theo `_resolve_rule_input_for_item`, ⛔ không tin chú thích.

### 3.4 Chuỗi tra cứu — đúng thứ tự engine đọc

| Bước | Việc | Nơi thực hiện |
|---|---|---|
| 1 | B2 dựng `glass_data[slug]` cho **mọi dòng category kính** | `bom_orchestrator.py:998-1019` |
| 2 | `_resolve_rule_input_for_item(item, glass_data)` đọc ref trong `rule_input_expr`: lấy `glass_data[ref_slug][ref_field]`; ref_slug không phải dòng kính → `row_literals[ref_slug][ref_field]`; không có → `0`. **`total_thick_mm` và `glass_thick` là 2 tên của CÙNG giá trị** (mục 4.5) | `:1953` |
| 3 | `_resolve_dynamic_item(rule_code, input)` → `AL Rule.resolve()` → mã item (vd `C3211-20`) | `:1982` |
| 4 | **Cache theo cặp `(rule_code, input)`** — nhiều dòng cùng rule nhưng khác kính vẫn đúng | `:1043-1069` |
| 5 | Tra weight + giá cho mã vừa resolve (**batch #6**), ⛔ **không ghi đè** mã đã resolve ở batch #2. Mã có >1 dòng giá ⇒ cảnh báo `gia_nhieu_dong_rule_item` + lấy dòng đầu | `:1071-1122` |
| 6 | Row literal mang `item_code` / `unit_price` / `weight_per_unit` đã resolve → B3/B4 | `:1180-1187` |

Bước 2 có một điểm thời gian cần nhớ: ở batch #5, `row_literals` **chưa được dựng** (dựng ở
`:1126+`). Nên **chỉ field kính** là chắc chắn có giá trị tại thời điểm resolve rule.

### 3.5 Ví dụ số (minh hoạ — số giả định)

Giả định: kính dày **24 mm**.

```text
nep_kinh_tren.rule_input_expr = "items.kinh_canh.glass_thick"
        ↓  glass_data["kinh_canh"]["glass_thick"] = 24
RULE-NEP-GLASSTHICK.resolve(24)
        ↓  24 ∈ [16.01, 999)
item_code = "C3211-20"
        ↓  batch #6: Item Price của C3211-20 (vd 113.000 đ/kg), weight 0.312 kg/m
nep_kinh_canh: width = 2*(...kính...) = 5700 mm, qty = 2
        ↓  LENGTH_TO_WEIGHT: (5700/1000) × 0.312 = 1,7784 kg/đơn vị
total_qty = 3,5568 kg  →  line_total = 3,5568 × 113.000 = 401.918,4 đ
```

Về bản chất tiền: nẹp tính theo **chiều dài cắt (m)** → quy ra kg qua `weight_per_unit` → nhân đơn
giá theo kg. Quy đổi nhanh: 113.000 đ/kg × 0,312 kg/m ≈ **35.256 đ/m**.
Nếu dòng nẹp dùng pattern `LENGTH_ONLY` (tính thẳng mét) thì `unit_price` phải là giá **theo mét**.

---

## 4. Vì sao lấy được từ AL Glass Master

### 4.1 Batch query ở B2

`b2_prefetch_master_data` — batch #3 (`bom_orchestrator.py:1119-1155`) đọc `AL Glass Master`:

| Field trên AL Glass Master | Thành khoá trong `glass_data` | Kiểu / nguồn |
|---|---|---|
| `total_thick_mm` | `total_thick_mm` (+ alias `glass_thick`) | Float — độ dày tổng (mm) |
| `glass_type` | `glass_type` | **Link tới `AL Glass Type`** — lưu **mã** (vd `LOWE`, `DON`) |
| `max_area_m2` | `max_area_m2` | Float — khổ tối đa; `0` = chưa khai ⇒ bỏ qua validate diện tích |

> `glass_thick` là **tên cũ** của `total_thick_mm`; engine ghi **cả hai khoá cùng giá trị**
> vào `glass_data`, `row_literals` và context công thức (`{slug}__total_thick_mm`,
> `{slug}__glass_thick`) để rule/công thức đã viết không vỡ.

Danh sách mã được fetch gồm: `default_glass_master` của mọi dòng **+ mọi mã trong
`glass_master_map` + `glass_master_override`** — nên kính người dùng chọn trong dialog cũng có sẵn
thông số.

### 4.2 Thứ tự chọn mã kính cho mỗi dòng

`_resolve_glass_override(rep, is_real_master)` (`bom_orchestrator.py:2197`):

```text
1. glass_master_map[rep]      ← user chọn trong dialog "Kính theo vị trí"
2. glass_master_override      ← biến toàn cục `glass_master` (1 kính cho cả BOM, đường cũ)
3. rep                        ← CHỈ khi rep là mã Glass Master thật
                                 (tức dòng có cấu hình default_glass_master)
4. None                       ← chưa chọn gì và dòng không có mã mặc định
```

`rep` lấy từ `glass_group_rep(item)` (`al_bom_engine/glass_group_resolver.py`):

| Dòng kính có | `rep` | Ý nghĩa |
|---|---|---|
| `default_glass_master` | chính mã đó | Dòng dùng mã mặc định; nhiều dòng **cùng mã** ⇒ **chung 1 selector** |
| không có | `__slug__<slug>` | Khoá tổng hợp **theo vị trí** — mỗi dòng một selector riêng. `is_real_master = False` ⇒ nếu user chưa chọn, kết quả là `None` (⛔ không coi slug là mã item) |

### 4.3 Kết quả và hậu quả khi chưa chọn kính

```text
glass_data[slug] = { "total_thick_mm": …, "glass_thick": …,   # cùng giá trị
                     "glass_type": …, "max_area_m2": … }
```

Dòng không phải dòng kính (nhôm, vật tư phụ, phụ kiện) luôn nhận
`{total_thick_mm: 0, glass_thick: 0, glass_type: "", max_area_m2: 0}` (`bom_orchestrator.py:1025-1034`).

**Khi user CHƯA chọn kính và dòng cũng không có `default_glass_master`:**

```text
glass_thick = 0, glass_type = ""
```

Hậu quả **khác nhau theo kiểu rule** — đây là điểm dễ hiểu sai:

| Rule của dòng phụ thuộc | Hành vi thật | Người dùng thấy |
|---|---|---|
| `THRESHOLD` có dải bắt đầu từ `0` (như seed `[0, 10.38]`) | Input `0` **vẫn được resolve** (`0` khác `""`) ⇒ khớp dải thấp nhất ⇒ **mã nẹp mỏng nhất** | Có mã, có tiền — **sai tiền mà không có cảnh báo** |
| `THRESHOLD` mà dải thấp nhất bắt đầu > `0` | Không khớp ⇒ `None` | Dòng không có `item_code` (nếu không khai sẵn) ⇒ tiền 0 |
| `LOOKUP` (như `RULE-KEO-GLASSTYPE`) | `resolve("")` trả `None` ngay từ đầu | Dòng không có `item_code` ⇒ tiền 0 |

Nên **luôn chọn kính (theo vị trí hoặc mã mặc định) trước khi tính giá**. Dòng thiếu mã thấy được ở
cột mã vật tư của Preview; nhưng trường hợp `THRESHOLD` rơi vào dải `0` thì **không** thấy gì bất
thường.

### 4.4 `glass_type` phải khớp **chính xác chuỗi** của rule LOOKUP

- `glass_type` là **Link** tới `AL Glass Type` và được lưu dưới dạng **mã** (`type_code`), vd
  `LOWE`, `DON`, `CUONG_LUC`, `HOP`, `LAM`.
- Rule `LOOKUP` so `str(row.key_field) == str(input)` — khớp **tuyệt đối**.
- ⇒ `key_field` của rule phải ghi đúng **mã** (`LOWE`), ⛔ không ghi tên hiển thị (`Kính Low-E`),
  không thêm khoảng trắng.

### 4.5 Tên chuẩn / tên cũ (alias) & nguồn của từng biến

Từ 2026-11-20, biến độ dày kính có **hai tên cùng trỏ một giá trị**. Tên mới trùng đúng tên
field nguồn trên `AL Glass Master`; tên cũ giữ nguyên để rule/công thức đã cấu hình vẫn chạy.
**Alias là additive** — không tên nào bị bỏ, ⛔ không phải đổi cấu hình cũ.

| Tên biến | Tên khác / alias | Nguồn thật (`Doctype.field`) | Ghi chú |
|---|---|---|---|
| `total_thick_mm` | — (tên CHUẨN) | `AL Glass Master.total_thick_mm` | Độ dày kính (mm) |
| `glass_thick` | alias của `total_thick_mm` | `AL Glass Master.total_thick_mm` | **Tên cũ — vẫn chạy** |
| `glass_type` | — | `AL Glass Master.glass_type` | Mã loại kính (Link `AL Glass Type`) |
| `max_area_m2` | — | `AL Glass Master.max_area_m2` | Khổ kính tối đa (m²) |
| `scrap_pct` | — | `AL Material Category.default_scrap_pct` | % hao hụt |
| `unit_price` | — | `Item Price.price_list_rate` | Đơn giá theo bảng giá |
| `weight_per_unit` | — | `Item.weight_per_unit` | TL riêng (kg/m) |
| `calc_pattern` | — | `AL Bom Item.calc_pattern` | Pattern tính số lượng |
| `has_weight` | — | `AL Material Category.has_weight` | Có tính trọng lượng |

Nguồn của biến nằm ở **một chỗ duy nhất**:
`alumglass/variable_sources/field_provenance.py` (`ROW_LITERAL_SOURCES`). Dòng
`AL Row Literal` có thêm 2 cột `source_doctype` / `source_field` — khai trên dòng thì **thắng**
bảng mặc định (dùng cho biến riêng của khách). Adapter `row_literal` và nhãn gợi ý chéo dòng
đọc từ đây nên tooltip autocomplete hiện được câu **"Nguồn: `AL Glass Master.total_thick_mm`"**.

Công thức dòng BOM dùng được cả hai tên:

```text
# Dòng kính — width/qty đọc trực tiếp biến độ dày / khổ kính
width = items.kinh_tren.total_thick_mm * 100
qty   = items.kinh_tren.max_area_m2

# Dòng nẹp — rule theo độ dày; glass_thick CŨ vẫn khớp cùng dòng kính
rule_input_expr = items.kinh_tren.glass_thick   # = total_thick_mm
```

> **Bản vá dữ liệu cho site đang chạy:** `alumglass/patches/v28_15/sync_variable_sources_and_fields.py`
> (đăng ký `[post_model_sync]` trong `patches.txt`). Patch **idempotent**, chạy lại không nhân đôi:
> bù dòng `AL Variable Settings.row_literals` còn thiếu (`total_thick_mm`, `max_area_m2`), điền
> `source_doctype`/`source_field` cho các dòng còn trống, đổi nhãn `glass_thick` thành
> "Độ dày kính (tên cũ)" **chỉ khi nhãn vẫn là giá trị seed cũ**, và thêm 2 field vào
> `cross_row.fields` của các profile đã khai danh sách tường minh (⛔ không đụng `fields` rỗng =
> "mọi field").

### 4.6 Giá và trọng lượng của mã kính — đủ cả 3 đường chọn kính

Trước bản vá Pha 3 (2026-11-20), **chỉ 2 đường đầu** được đưa vào danh sách tra giá/trọng lượng ở
B2 (`glass_master_map`, `glass_master_override`). Mã kính lấy theo **`default_glass_master`** chỉ
được nạp *thông số* (`AL Glass Master`) — nên dòng kính "ăn" theo đường mặc định ra
`unit_price = 0`, `weight_per_unit = 0`, `line_total = 0` **mà không có cảnh báo**.

Số đo trên harness `standalone_tests/test_phase_c_traces.py` (dòng kính `item_code = ""`,
`default_glass_master = "GM-01"`, `glass_master_map = {}`):

| Đường chọn kính | `unit_price` | `weight_per_unit` | `line_total` |
|---|---|---|---|
| `glass_master_map['__slug__kinh_tren'] = 'GM-01'` (trước & sau vá) | 300 000 | 20 | 1 584 000 |
| `default_glass_master = 'GM-01'` — **trước vá** | **0** | **0** | **0** |
| `default_glass_master = 'GM-01'` — **sau vá** | 300 000 | 20 | 1 584 000 |

Cách vá (Owner chốt **"cách B — mềm"**):

- Mã từ `default_glass_master` được thêm vào batch query **#1** (trọng lượng + tên) —
  `b2_prefetch_master_data` (`bom_orchestrator.py:1016`).
- Giá tra ở **batch #2b** — `bom_orchestrator.py:1164`: gọi **riêng**
  `_fetch_composite_prices(..., allow_missing=True)`, rồi **merge vào `prices` và ⛔ không ghi đè**
  mã đã có giá ở batch #2 (đường map/override luôn thắng).
- 🔴 **Vì sao phải đi đường cho phép thiếu:** nhánh mặc định của batch #2 dùng
  `allow_missing=False` ⇒ một mã không có dòng `Item Price` sẽ **THROW và dừng cả lần tính giá**.
  "Cách B" = không chặn: thiếu giá thì giữ **0** + cảnh báo `thieu_gia_item:<mã>` nổi lên ở
  `errors.bom_items`.
- Mã kính **CÓ** được đọc giá nên cảnh báo thiếu giá của nó **phải giữ** — ⛔ không nằm trong
  `_unused_placeholder_codes` (`bom_orchestrator.py:1786`, hàm này chỉ nuốt cảnh báo của mã **kính
  giữ chỗ** mà không dòng nào đọc giá).

> Khi mã kính đã có **1 dòng Item Price không gắn dimension**, giá vẫn tra theo đúng composite key
> hiện tại (màu/độ dày) như mọi mã khác. Mã kính *chưa* có dòng giá nào chỉ cảnh báo, không chặn.

### 4.7 Hợp đồng dialog "Kính theo vị trí" (Pha 3)

`alumglass.api.get_variable_set_for_bom(bom_code, quotation_item_name=None)` — tham số thứ hai
**tuỳ chọn**: truyền tên dòng báo giá đang mở thì mỗi phần tử `glass_groups` mang thêm trạng thái
THẬT của báo giá đó. Các field cũ (`rep`, `label`, `default`, `slug`, `is_real_master`) **giữ
nguyên** — bản cũ không truyền tham số vẫn chạy, chỉ là giá 0 + `price_approx = true`.

| Field | Nghĩa |
|---|---|
| `saved` | Giá trị **đã lưu** trong `glass_master_map` cho `rep` này (`""` nếu chưa chọn) |
| `effective_code` | Mã kính engine **SẼ dùng**: `saved` → `glass_master` (override global) → `default_glass_master` (khi `is_real_master`) → `item_code` của dòng → `""` |
| `effective_source` | `"saved"` · `"override"` · `"bom_default"` · `"item_code"` · `"none"` — đúng thứ tự ưu tiên của `_resolve_glass_override` |
| `effective_name` | Tên `AL Glass Master.glass_name`, không có thì `Item.item_name` (`""` nếu chưa có tên) |
| `effective_is_glass_master` | `true` khi `effective_code` là mã **có thật** trong `AL Glass Master`. `false` với mã giữ chỗ (`item_code` của dòng BOM, VD `KINH-01`) ⇒ dialog ⛔ **không** nhét mã đó vào control Link → AL Glass Master (giá trị không có trong danh mục trông như lỗi) |
| `price` | Đơn giá của `effective_code` theo **bảng giá đang dùng** (0 nếu không tra được) |
| `price_list` | Tên bảng giá đã dùng |
| `has_price` | `true` khi **có dòng Item Price hợp lệ** — kể cả `price_list_rate = 0` (giá 0 là giá **thật**: hàng tặng/kính giá 0). ⛔ KHÔNG suy từ `price > 0`; `false` chỉ khi không có dòng giá nào |
| `price_approx` | `true` khi giá **CHƯA áp composite dimension** (màu/độ dày) — xem bên dưới |

**API tra giá một mã kính** — `alumglass.api.get_glass_master_price(quotation_item_name, glass_code)`:

```json
{"success": true, "code": "GM-01", "name": "Kính trắng 8 mm",
 "price": 300000, "price_list": "Standard Selling",
 "has_price": true, "approx": false, "note": ""}
```

- 🔴 **Giá phải khớp giá engine sẽ tính** — không được là "con số thứ hai". Cả 2 API đi qua
  `_resolve_glass_price()` (`api/__init__.py:1158`), hàm này dựng `BomOrchestrator` bằng
  `prepare_price_context()` (`bom_orchestrator.py:956` = b0 + b1 + snapshot, **không** chạy batch
  query của b2) rồi gọi `price_for_code()` (`:978`) — **chính** đường giá của batch #2
  (FB binding trước, resolver composite sau, cùng `inputs`, cùng price list).
- **Không dựng được đủ ngữ cảnh** (chưa lưu biến, thiếu giá trị dimension, BOM chưa có version…):
  trả **dòng Item Price thô** + `approx = true` + `note` =
  `Giá thực tế còn phụ thuộc màu/độ dày — sẽ chốt khi hệ thống tính lại giá.` — ⛔ không im lặng trả số
  khác engine.
- **Mã kính chưa có dòng giá nào:** `has_price = false`, `price = 0`, `note` =
  `Mã kính này chưa có giá trong bảng giá "<tên bảng giá>".`
- **Có dòng giá nhưng `price_list_rate = 0`:** `has_price = true`, `price = 0`, `note = ""` —
  giá 0 là giá THẬT, ⛔ không báo "chưa có giá" (đối chứng: ca không có dòng giá ở trên).
- **Mã kính không tồn tại:** `{"success": false, "message": "Không tìm thấy mã kính này."}`.
- Cả 2 API kiểm quyền **đọc trên Quotation cha** (`_require_quotation_item_permission`).

> Đo khớp giá (test `test_get_glass_master_price_matches_engine_unit_price`): cùng báo giá, cùng
> inputs — `get_glass_master_price(...).price = 300 000` = `unit_price` của dòng kính sau B4.

---

## 5. Bản vá lọc gợi ý chéo dòng có làm mất gợi ý theo dòng kính đại diện không?

**Trả lời: KHÔNG.**

### 5.1 Vì sao

Gợi ý chéo dòng được sinh theo **từng CẶP** (slug của dòng × field khai trong `cross_row.fields`) —
⛔ không theo mã kính, ⛔ không theo "dòng kính đại diện".

Cơ chế (`alumglass/variable_sources/adapters.py`):
- `build_references()` (dòng 822) chọn bảng `items` từ `cross_row` của profile gắn với `AL Bom Set`.
- `_append_references()` (dòng 782) duyệt **mọi dòng** của bảng, mỗi dòng × **mọi field** trong
  `fields` ⇒ sinh `items.<slug>.<field>` (và thêm dạng chỉ số `items[<i>].<field>` nếu
  `include_index_form = 1`).

Profile mặc định của `AL Bom Set` là `P_BOM_DEFAULT`, seed ở
`alumglass/patches/v28_14/seed_bom_profile.py`. `CROSS_ROW_FIELDS` (dòng 70) **có** `glass_thick` và
`glass_type`. ⇒ Sau khi lọc, vẫn còn đầy đủ:

```text
items.<slug_kính_1>.glass_thick   items.<slug_kính_1>.glass_type
items.<slug_kính_2>.glass_thick   items.<slug_kính_2>.glass_type
…                                  (mỗi dòng kính trong bộ đều có)
```

Danh sách `CROSS_ROW_FIELDS` hiện tại: `width` · `height` · `qty` · `unit_qty` · `unit_price` ·
`total_qty` · `line_total` · `weight_per_unit` · `total_thick_mm` · `glass_thick` · `glass_type` ·
`max_area_m2` · `calc_pattern` · `scrap_pct`.

### 5.2 Cái **mất** sau bản vá

| Mất | Ví dụ |
|---|---|
| Field meta **không khai** trong `cross_row.fields` | `line_name`, `price_type`, `fixed_price`, `supplier_location`, `install_position`, `cut_angle`, `note`, `cost_bucket` |
| Bảng con **không có** cấu hình `cross_row` | bảng khác của doctype đó (nếu có) |
| Dạng gợi ý "mọi field vô hướng" (hành vi cũ) | chỉ còn field trong allowlist |

`P_BOM_DEFAULT` cố ý dùng `default_action = EXCLUDE_ALL` ⇒ **không khai = không gợi ý**. Patch ghi
rõ lý do loại `cost_bucket` (chỉ có sau B5), `row_literal` trần và `cost_template_line` (chỉ có ở
B6) — xem docstring đầu file patch.

### 5.3 Engine **không** đổi

`rule_input_expr` vẫn resolve bằng regex + `glass_data`/`row_literals` như mục 3. Gợi ý **chỉ là
lớp gợi ý trên form** — ⛔ không phải điều kiện hợp lệ của engine. Hệ quả: gõ tay một tham chiếu
không có trong gợi ý vẫn "chạy" (nếu đúng cú pháp và đúng slug), còn gợi ý có sẵn **không** bảo đảm
field đó có giá trị lúc tính.

### 5.4 Ba rủi ro cấu hình cần biết

**a. Sửa `cross_row.fields` trên `AL Variable Profile`**

| Việc admin làm | Hệ quả |
|---|---|
| Xoá `glass_thick`/`glass_type` khỏi `cross_row.fields` | Gợi ý **mất**; `rule_input_expr` đã gõ vẫn chạy (engine không đọc cấu hình gợi ý) |
| Khai thêm một field mà engine **không nạp** cho dòng (vd `line_name`) | Gợi ý **có**, gõ vào công thức nhưng lúc tính ra **0** — gợi ý dẫn tới kết quả sai |

Nói cách khác: **cấu hình gợi ý và hành vi engine là hai lớp độc lập**. Sửa lớp gợi ý không làm
hỏng công thức đang chạy, nhưng có thể **dẫn người dùng** tới field rỗng.

**b. Dòng kính bị tắt `is_active` hoặc bị xoá khỏi Bom Set**

| Tình huống | Gợi ý | Cảnh báo khi lưu | Kết quả tính |
|---|---|---|---|
| **Xoá hẳn** dòng kính khỏi Bom Set | Mất (không còn dòng để duyệt) | **Có** — `validate_rule_input_expr` báo "không có dòng nào mang slug…" | `rule_input_expr` cũ resolve ra 0 |
| **Tắt `is_active`** dòng kính | **Vẫn còn** — gợi ý đọc các dòng của chứng từ (`ctx.get_child_rows`), ⛔ không lọc `is_active` | **Không** — validate so slug với **toàn bộ** `self.items`, kể cả dòng đã tắt | Engine **không thấy** dòng đó trong snapshot ⇒ `glass_thick = 0` ⇒ hậu quả theo bảng 4.3 |

Trường hợp tắt `is_active` là trường hợp **nguy hiểm nhất**: gợi ý vẫn đúng, form không cảnh báo,
nhưng engine tính như không có dòng kính.

**c. Chọn kính trong dialog đổi **GIÁ TRỊ**, ⛔ không đổi **chuỗi gợi ý**

```text
Chuỗi trên form luôn là:  items.kinh_canh.glass_thick
Giá trị lúc tính đổi:      8 → 12 → 24  (tuỳ kính user chọn)
```

Vì vậy **cùng một cấu hình** có thể ra mã nẹp khác nhau ở mỗi báo giá — đó là thiết kế đúng, ⛔ không
phải lỗi cấu hình. Muốn cố định mã nẹp thì phải cố định kính (`default_glass_master` và không cho
đổi vị trí).

---

## 6. Đường đi mapping — từng bước B0 → B6

Chuỗi chạy: `BomOrchestrator.run()` → `b0` → `b1` → … → `b7`
(`bom_orchestrator.py:301-310`). Mỗi bước dưới đây ghi **Đầu vào → Xử lý → Đầu ra**.

### B0 — `b0_version_pinning()` (`bom_orchestrator.py:323`)

| | |
|---|---|
| **Đầu vào** | Quotation Item (`al_bom`, `al_bom_version`) |
| **Xử lý** | Có `al_bom_version` → dùng version đó. Không có → `AL BOM.current_version`. Không có nữa → **version mới nhất theo `creation DESC`** (`_latest_existing_version`). Không có version nào → **throw** kèm hướng dẫn tạo version |
| **Đầu ra** | `self.bom_version` + `self.bom_code` |

> Engine **cố ý không tạo version** trong đường tính giá. Snapshot (dòng Bom Item + cost template +
> pricing dimension) được chụp tại **lúc tạo version** — `AL BOM Version._take_snapshots()`
> (`al_bom_version.py:108`). Đây là lý do "sửa Bom Set xong vẫn ra số cũ" (mục 9).

### B1 — `b1_gather_inputs()` (`bom_orchestrator.py:372`)

| | |
|---|---|
| **Đầu vào** | `al_bom_vars` trên Quotation Item, Formula Global Variable, binding của Formula Builder, `AL Variable Library`, `AL Profile System.system_variables` |
| **Xử lý** | Hợp đồng ưu tiên (cao → thấp): **user nhập tay** > child `system_variables` của profile > FB `get_live_context` > Global Variable; lớp chỉ-điền-khi-thiếu: Library system var + `default_value` của user var. Cuối cùng chuẩn hoá **biến phần trăm**: `8` → `0.08` (`_normalize_percent_inputs`, `:549`) |
| **Đầu ra** | `self.inputs` (namespace phẳng `{tên_biến: giá trị}`) + cờ override: `accessory_set_code`, `glass_master_override`, `glass_master_map`, `color_master_override`, `color_master_map`, `profile_system_override`, `cost_template_override` |

Chi tiết bẫy phần trăm: giá trị **đúng bằng `1`** là ca mơ hồ (1% hay 100%) — engine hiểu là 100% và
**phát cảnh báo**, ⛔ không tự đổi luồng tính.

### B2 — `b2_prefetch_master_data()` (`bom_orchestrator.py:901`) — nặng nhất

| | |
|---|---|
| **Đầu vào** | `bom_set_snapshot` của version |
| **Xử lý** | 1. Đọc snapshot → `self.bom_items` (dòng `is_active = 0` đã bị loại từ B0). 2. **Append phụ kiện** từ `AL Accessory Set` (`_load_accessories`). 3. Gom mã. 4. **6 batch query**. 5. Dựng `glass_data`. 6. Dựng `row_literals` |
| **Đầu ra** | `self.bom_items`, `self.row_literals`, `self._glass_data` |

**6 batch query** (theo đúng thứ tự phụ thuộc) — cộng **batch #2b** (Pha 3) tra giá riêng cho mã
kính `default_glass_master`, xem mục 4.6:

| # | Query | Dùng cho |
|---|---|---|
| 1 | `Item.weight_per_unit` cho mọi `item_code` + mã kính override + **mã kính `default_glass_master`** | `LENGTH_TO_WEIGHT`, cột Trọng lượng |
| 2 | `Item Price` theo **composite key** cho `item_code` ∪ `price_base_item` ∪ mã kính override | `unit_price` |
| 2b | `Item Price` cho **mã kính `default_glass_master`** — `allow_missing=True`, merge **không ghi đè** (mục 4.6) | `unit_price` dòng kính chọn kính theo đường mặc định |
| 3 | `AL Glass Master` (`total_thick_mm`, `glass_type`, `max_area_m2`) | `glass_data` (mục 4) |
| 4 | `AL Material Category` (`default_scrap_pct`, `has_weight`) + nhận diện **category kính** | scrap, cột Trọng lượng, `glass_data` |
| 5 | `AL Rule` (result_type = ITEM) — resolve **từng dòng** theo `rule_input_expr` của chính nó | `item_code` của dòng Rule (mục 3) |
| 6 | `Item` weight + `Item Price` của **mã vừa resolve từ rule** | `unit_price` dòng Rule |

Thứ tự này là bắt buộc: batch **#5 phải sau `glass_data`** vì `rule_input_expr` đọc
`glass_thick`/`glass_type`; batch **#6 phải sau #5** vì mã chưa tồn tại trước đó.

**Dựng `glass_data`** (`:1208-1236`): với mỗi dòng có category ∈ nhóm kính →
`glass_group_rep` → `_resolve_glass_override` → tra `glass_masters`; không có → `{glass_thick: 0,
glass_type: "", max_area_m2: 0}`.

**Dựng `row_literals`** (`:1331-1400`) — "nguyên liệu thô" cho B3, mỗi slug một dict:

```python
{
  "weight_per_unit": ...,
  "unit_price": prices[price_base_item] nếu có, ngược lại prices[item_code],
  "calc_pattern": ..., "glass_thick": ..., "glass_type": ...,
  "item_code": <mã kính đã resolve nếu là dòng kính; mã rule nếu là dòng Rule>,
  "scrap_pct": <từ category>, "has_weight": 0/1,
  "color": <màu đã resolve theo vị trí>, "supplier_location": ..., "install_position": ...,
  "cut_angle": ..., "note": ...
}
```

> Ghi đè thêm: dòng phụ kiện/accessory có `unit_price` khai trực tiếp thì **thay** giá tra được
> (`:1163-1167`).
>
> Dòng KÍNH: `item_code` ở đây là **mã kính đã resolve** (một trong 3 đường — mục 4.2), nên
> `unit_price`/`weight_per_unit` tra theo **chính mã kính đó**. Mã kính lấy theo đường mặc định có
> giá nhờ batch #2b (mục 4.6); thiếu giá ⇒ 0 + cảnh báo `thieu_gia_item:<mã>`.

### B3 — `b3_build_formulas()` (`bom_orchestrator.py:2122`)

| | |
|---|---|
| **Đầu vào** | `row_literals`, cấu hình công thức từng dòng, `formula_fieldnames` của Bom Set (fallback `DEFAULT_FORMULA_FIELDS`) |
| **Xử lý** | 1. Bơm literal vào `self.inputs` dưới tên `{slug}__{key}`. 2. Đặt sẵn mặc định `0` cho `width/height/qty/calc_pattern/weight_per_unit/unit_price/scrap_pct`. 3. Resolve biến phụ của `calc_pattern`. 4. Sinh formula cho từng field trong `formula_fieldnames`. 5. Sinh **3 formula tổng hợp** cho **mọi** dòng |
| **Đầu ra** | `self.bom_formulas` (danh sách `{name, formula}`) |

**3 formula tổng hợp — hợp đồng engine, ⛔ không tắt được** (`al_bom_item.py:18`):

```text
{slug}__unit_qty   = lookup_calc_pattern({slug}__calc_pattern, {slug}__width,
                                         {slug}__height, {slug}__weight_per_unit [, {…biến phụ}])
{slug}__total_qty  = {slug}__unit_qty * {slug}__qty
                     # nếu AL Bom Set.apply_scrap_pct = 1:
                     # ({slug}__unit_qty * {slug}__qty) * (1 + {slug}__scrap_pct/100)
{slug}__line_total = {slug}__total_qty * {slug}__unit_price
```

- **Hao hụt cắt là OPT-IN:** chỉ áp khi `AL Bom Set.apply_scrap_pct = 1` (mặc định **0**). Bật cờ
  này là **đổi số liệu thật** (tăng giá thành) — phải review với kinh doanh trước.
- **`scrap_pct`** lấy từ `AL Material Category.default_scrap_pct` (số nguyên %, vd `3` = 3%).
- **Dict `items` lồng** vẫn được dựng (`:2153-2162`) nhưng công thức dòng đã chuẩn hoá về tên
  phẳng, nên giá trị dùng thật là `{slug}__{field}`.

### B4 — `b4_calculate_bom_items()` (`bom_orchestrator.py:2417`)

| | |
|---|---|
| **Đầu vào** | `bom_formulas` + `inputs` |
| **Xử lý** | Engine công thức (`FormulaEngine`) có **cache theo vân tay công thức**; tính 1 lượt theo DAG; gom lỗi từng dòng (`on_error="default"` → lỗi ⇒ giá trị **0**, không chết cả BOM); **validate diện tích kính** vs `max_area_m2` |
| **Đầu ra** | `self.bom_result` — mỗi dòng: `slug, item_code, width, height, qty, unit_qty, total_qty, unit_price, line_total, cost_bucket, unit, weight_per_unit, has_weight, trace, color, supplier_location, install_position, cut_angle, note` |

- `unit` = `output_unit` của `calc_pattern` (`:2257-2268`).
- **Validate diện tích kính** (`_validate_glass_max_area`, `:2316`): chỉ **cảnh báo**, ⛔ không chặn —
  `max_area_m2 = 0` (chưa khai) thì bỏ qua. Cảnh báo đi vào `errors.bom_items`.
- Dòng lỗi công thức vẫn **có mặt** trong kết quả với giá trị 0 và có câu lỗi tương ứng ở
  `errors.bom_items` — đây là cách phát hiện cấu hình sai (xem mục 9).

### B5 — `b5_aggregate_cost_buckets()` (`bom_orchestrator.py:2568`)

| | |
|---|---|
| **Đầu vào** | `bom_result` |
| **Xử lý** | Với từng dòng: `cost_bucket` trống → **bỏ qua**. Nhóm có `source_type = "aggregate_from_items"` **và** có `source_config` → resolve qua Formula Builder (1 lần cho cả Nhóm). Còn lại → **cộng Python** `line_total` vào Nhóm |
| **Đầu ra** | `self.buckets` = `{bucket_code: tiền}` |

- `source_type` khác `aggregate_from_items` nhưng **có khai** ⇒ engine cảnh báo "chưa hỗ trợ, tạm
  cộng line_total" (`:2419-2432`).

### B6 — `b6_calculate_cost_template()` (`bom_orchestrator.py:2694`)

| | |
|---|---|
| **Đầu vào** | `cost_template_snapshot` (hoặc template override), `inputs` + `buckets` |
| **Xử lý** | Dựng DAG từ `calc_formula` của từng dòng template; context = `inputs ⊕ buckets ⊕ 0` cho mã bucket được tham chiếu; tính 1 lượt; dựng `cost_template_trace` để giải thích |
| **Đầu ra** | `self.cost_result`, `self.gia_vat` (dòng có `is_final_price = 1`, không có thì `GIA_VAT`) |

Sau đó `b7_save_results()` (`:2850`) ghi vào Quotation Item: `al_gia_vat`, `al_gia_ban` (= giá trước
VAT, cũng ghi vào `rate`), `al_bom_result` (JSON gồm `buckets`, `cost_template`, `cost_template_trace`,
`lines`, `gia_vat`, `gia_ban`, `errors`), rồi tính lại tổng Quotation cha.

### 6.1 Bước tra giá — chi tiết (nằm trong B2 batch #2)

Đường chuẩn: `_fetch_composite_prices_via_fb()` (`:1597`)

1. Đọc **binding** pricing (`_get_pricing_bindings`, `:1328`) — `source_type = aluminum_price_composite`.
2. Đọc `source_config`: `pricing_mode` (mặc định `exact_match`), `price_list` (mặc định Selling Settings).
3. Đúng **1 binding** loại này ⇒ đi đường nhanh. 0 hoặc >1 binding ⇒ đường chậm per-item
   (`_fetch_composite_prices_via_fb_slow`) — vẫn đúng nhưng N+1.
4. Không có binding nào ⇒ **fallback** `_fetch_composite_prices()` (`:1792`).

**Thuật toán `best_partial_match`** — `engine/composite_pricing.py:25`:

| Tình huống dòng `Item Price` | Xử lý |
|---|---|
| Chỉ có 1 dòng | Lấy luôn |
| Dòng **không set** một dimension | Bỏ qua dimension đó, **không loại** |
| Dòng **có set** dimension nhưng **khác** input hiện tại | **Loại** dòng |
| Nhiều dòng còn lại | Chọn dòng **khớp nhiều dimension nhất** (điểm cao nhất) |
| Không dòng nào khớp | Fallback dòng **"trần"** (không set dimension nào) = giá mặc định |
| Không có cả dòng trần | Trả `None` ⇒ **caller quyết định**: nhánh fallback `throw`, nhánh FB `allow_missing` ⇒ **0 + cảnh báo** |

Lọc trước khi match: dòng `Item Price` **còn hiệu lực** (`valid_from`/`valid_upto`, trống = vô thời
hạn) và **đúng tiền tệ** (`filter_price_rows`, `composite_pricing.py:183`). Bảng giá khác tiền tệ báo
giá ⇒ **không lọc** + ghi Error Log (tránh giá 0 im lặng).

**Hai `pricing_mode`** (`fb_handlers.py:85-99`):

| Mode | Cách tính giá | Điều kiện |
|---|---|---|
| `exact_match` (mặc định) | Lấy `price_list_rate` của dòng khớp nhất như trên | — |
| `multiplier_chain` | **giá gốc × ∏ multiplier**, mỗi chiều một multiplier | Giá gốc = dòng **"trần"** (`pick_base_price`). Mỗi mapping: ưu tiên `price_multiplier` của **bản ghi link** (màu/mục…), vắng/0 thì dùng `price_multiplier` của **mapping**. Không có dòng trần ⇒ lấy dòng đầu + **cảnh báo** `gia_goc_thieu_dong_tran` |

`multiplier_chain` phân biệt rõ **"không khai"** với **"khai đúng 1.0"** — màu không phụ phí phải
giữ 1.0, ⛔ không bị thay bằng multiplier của mapping.

---

## 7. Ví dụ chạy từng bước với số liệu (minh hoạ)

> 🔵 **Số giả định**, tính tay theo công thức trong mã. Không phải số đo trên site.
> Đầu vào: `W_mm = 2400`, `H_mm = 2600`, `TransomHeight_mm = 600`, `n_panel = 2`,
> `OFFSET_FIXED = 50`, kính chọn `KINH-LOWE-24` (dày 24 mm, loại `LOWE`), giá `NHOM-XINGFA` =
> 113.000 đ/kg, `KINH-LOWE-24` = 1.150.000 đ/m², `VIT-TK-35X16` = 850 đ/cái.
> `AL Bom Set.apply_scrap_pct = 0`.

### Bước 1 — dòng kính sinh `glass_data`

```text
kinh_tren.width  = W_mm - 2*OFFSET_FIXED      = 2400 - 100  = 2300 mm
kinh_tren.height = TransomHeight_mm - OFFSET_FIXED = 600 - 50 = 550 mm
glass_data["kinh_tren"] = { glass_thick: 24, glass_type: "LOWE", max_area_m2: 0 }
```

`max_area_m2 = 0` nghĩa là Glass Master chưa khai khổ tối đa ⇒ bước validate diện tích **bỏ qua**.

### Bước 2 — dòng nẹp đọc độ dày kính của dòng kính

`nep_kinh_tren.rule_input_expr = "items.kinh_tren.glass_thick"`

```text
_resolve_rule_input_for_item(): glass_data["kinh_tren"]["glass_thick"] = 24
```

### Bước 3 — rule THRESHOLD chọn mã

`RULE-NEP-GLASSTHICK` (seed): `[0, 10.38] → C3209-20` · `[10.39, 16] → C3210-20` ·
`[16.01, 999] → C3211-20`

```text
24 nằm trong [16.01, 999)  →  item_code = "C3211-20"
cache key = ("RULE-NEP-GLASSTHICK", 24)
```

### Bước 4 — tra giá cho mã vừa resolve (batch #6)

`C3211-20` chưa có trong lần tra giá đầu (nó không phải `item_code`/`price_base_item` của dòng nào)
⇒ batch #6 tra `Item Price` ⇒ `113.000`. Không ghi đè mã nào đã resolve ở batch #2.

### Bước 5 — literal + tính dòng

```text
row_literals["nep_kinh_tren"] = {
  item_code: "C3211-20", unit_price: 113000, weight_per_unit: 0.312,
  calc_pattern: "LENGTH_TO_WEIGHT", glass_thick: 0, glass_type: ""
}
```

Công thức:

```text
nep_kinh_tren.width     = 2*(items.kinh_tren.width + items.kinh_tren.height)
                        = 2*(2300 + 550) = 5700 mm          (→ tên phẳng kinh_tren__width …)
nep_kinh_tren.height    = (trống) = 0
nep_kinh_tren.qty       = 2
nep_kinh_tren.unit_qty  = LENGTH_TO_WEIGHT: (5700/1000) * 0.312 = 1.7784 kg
nep_kinh_tren.total_qty = 1.7784 * 2 = 3.5568 kg
nep_kinh_tren.line_total= 3.5568 * 113000 = 401.918,4 đ
```

Dòng kính và dòng vít, cùng lượt:

| Slug | width | height | qty | calc_pattern | unit_qty | total_qty | unit_price | line_total | bucket |
|---|---|---|---|---|---|---|---|---|---|
| `kinh_tren` | 2300 | 550 | 1 | `AREA` | 2,3 × 0,55 = **1,265 m²** | 1,265 | 1.150.000 | **1.454.750** | `VL_KINH` |
| `nep_kinh_tren` | 5700 | 0 | 2 | `LENGTH_TO_WEIGHT` | **1,7784 kg** | 3,5568 | 113.000 | **401.918,4** | `VL_NHOM` |
| `vit` | — | — | `10*2+8 = 28` | `COUNT` | **1** | 28 | 850 | **23.800** | `VL_VTP` |

### Bước 6 — gom Nhóm (chỉ 3 dòng trên)

```text
VL_KINH  = 1.454.750
VL_NHOM  = 401.918,4
VL_VTP   = 23.800
```

Sau đó B6 dùng các Nhóm này trong công thức cost template (`TONG_VL = VL_NHOM + VL_KINH + VL_VTP + VL_PK`…).

### Đọc lại chuỗi phụ thuộc

```text
default_glass_master (KINH-LOWE-24)
   → AL Glass Master.total_thick_mm = 24
      → glass_data["kinh_tren"].glass_thick
         → rule_input_expr của nep_kinh_tren
            → RULE-NEP-GLASSTHICK chọn C3211-20
               → Item Price 113.000
                  → unit_qty × qty × giá → line_total
                     → VL_NHOM
                        → TONG_VL → … → GIA_VAT
```

Đây là lý do **sai một ô `default_glass_master` làm sai tiền của dòng nẹp và dòng keo cùng lúc**, dù
hai dòng đó không nhắc gì tới kính.

---

## 8. Bảng "field nào ảnh hưởng giá"

### 8.1 Ảnh hưởng **TIỀN** (đổi là đổi số)

| Field | Ảnh hưởng qua đâu | Mức |
|---|---|---|
| `item_selection_mode` + `item_code` / `item_rule` + `rule_input_expr` | Chọn mã ⇒ chọn giá | Cao |
| `price_base_item` | Mã dùng tra bảng giá composite | Cao |
| `default_glass_master` | `glass_thick`/`glass_type` → mã nẹp/keo + validate diện tích | Cao (lan sang dòng khác) |
| `default_color` | Ghi đè biến màu khi tra giá / multiplier | Cao |
| `calc_pattern` | `unit_qty` (m / m² / kg / cái) | Cao |
| `width`, `height`, `qty` | `unit_qty`, `total_qty` | Cao |
| `input_vars` | Tham số của `calc_pattern` | Trung bình |
| `cost_bucket` | Dòng có vào Nhóm hay không | Cao nếu trống |
| `category` | `default_scrap_pct` (khi bật hao hụt), nhóm kính, bộ dimension khi tra giá | Trung bình (gián tiếp) |
| `is_active` | Dòng có tồn tại trong snapshot | Cao (bật/tắt cả dòng) |

### 8.2 Chỉ **VALIDATE** (chặn lưu, không đổi số khi đã lưu hợp lệ)

| Field | Vai trò |
|---|---|
| `ctx_inject_prefix` | Bắt buộc khi category yêu cầu; engine không đọc |
| `item_condition_formula` | Bắt buộc + đúng cú pháp khi mode `Formula`; không chọn mã |
| `price_type` | Chỉ hiện/ẩn ô trên form (nhưng xem cảnh báo: đổi nó **không** đổi cách tra giá) |
| `category` (cờ `requires_*`) | Bắt buộc `item_code` / `price_base_item` |

### 8.3 Chỉ **HIỂN THỊ**

`line_name` (thực tế không được dùng để hiển thị — nhãn lấy từ `AL Slug Library.label`; chỉ dùng làm
nhãn gợi ý chéo dòng) · `supplier_location` · `install_position` · `cut_angle` · `note` · `trace`
(sinh tự động).

> `price_list` trên dòng: không hiển thị, không tính — xem 8.4.

### 8.4 **KHAI BÁO NHƯNG CHƯA DÙNG** (engine không đọc — đã `grep` toàn repo)

`item_fallback` · `allow_sales_override` · `override_item_group` · `allow_substitute` ·
`substitute_item_group` · `price_rule` · `price_list` · `fixed_price` · `cut_fee_pct` ·
`panel_count_formula` · `qty_per_panel_formula` · `panel_glass_override_allowed` · `formula_set`.

⚠️ **Đặc biệt lưu ý `price_list`:** dòng có ô này và nó **hiện trên form**, nhưng engine tra giá
theo bảng giá của binding / Selling Settings. Đây là bẫy cấu hình hay gặp nhất trong nhóm này.

### 8.5 **Được tính nhưng chưa dùng**

`show_condition` — B3 sinh `{slug}__show_condition`, **không** có nơi lọc dòng.

---

## 9. Lỗi thường gặp + cách kiểm

### 9.1 Rule trả 0 / chọn nhầm mã

| Triệu chứng | Nguyên nhân thường gặp | Kiểm thế nào |
|---|---|---|
| Dòng Rule có giá 0 | `rule_input_expr` sai **slug** hoặc **field**; hoặc rule trả `None` và dòng **không khai** `item_code` | Xem cảnh báo cam khi lưu Bom Set (`validate_rule_input_expr`); đối chiếu slug với danh sách dòng |
| **Gõ `glass_thick` thiếu `items.<slug>.`** | Không khớp regex ⇒ engine **bỏ qua** dòng đó, rule không chạy; bộ kiểm cũng **không cảnh báo** vì không thấy ref `items.x.y` | Gõ lại đúng dạng `items.<slug>.<field>`; đối chiếu mục 3.3 |
| **Gõ `items[0].glass_thick`** | Gợi ý dạng chỉ số có trong autocomplete nhưng regex của rule **không nhận** | Đổi sang dạng có slug |
| Chọn mã "mỏng nhất" dù kính dày | `glass_thick = 0` (chưa chọn kính) ⇒ THRESHOLD khớp dải `[0, …]` thấp nhất | Xem `glass_thick` của dòng kính trên Preview; chọn kính trước khi tính (mục 4.3) |
| **`glass_type` không khớp chuỗi LOOKUP** | Rule ghi tên hiển thị (`Kính Low-E`) hoặc sai hoa/thường, trong khi `glass_type` lưu **mã** (`LOWE`) | Mở `AL Glass Master` xem `glass_type`; rule `LOOKUP` phải ghi đúng mã |
| **Dòng Rule để sẵn `item_code`** | Engine **chỉ ghi đè** khi rule resolve được; rule trượt ⇒ dùng `item_code` khai sẵn (có thể là mã **sai** cho kính hiện tại) | Kiểm mã thực tế trên kết quả; ⛔ đừng coi `item_code` khai sẵn là "vô hại" |
| Đổi kính mà nẹp không đổi | **Đã vá** (cache theo cặp `(rule_code, input)`). Nếu vẫn gặp: kiểm 2 dòng nẹp có cùng `rule_input_expr` trỏ về **cùng** slug kính không | So `rule_input_expr` của các dòng nẹp/keo |
| Rule không khớp dòng nào | Dải THRESHOLD có **khe hở** (vd `10.38–10.39`, `16–16.01` trong seed) | Mở rule → cảnh báo "Threshold có KHE HỞ"; khai liền `to` = `from` dải sau |
| Kính chưa chọn ⇒ rule trả `None` | `LOOKUP` với input rỗng trả `None`; `THRESHOLD` mà dải thấp nhất > 0 cũng vậy | Chọn kính; xem mục 4.3 |

### 9.2 Thiếu giá

| Triệu chứng | Nguyên nhân | Kiểm |
|---|---|---|
| Giá thấp hơn mong đợi, không cảnh báo | `price_base_item` trống ⇒ lùi về `item_code`, **mất phụ phí composite** | Xem dòng có `price_base_item` không; so giá 2 mã |
| Giá 0 + cảnh báo "không tìm được dòng Item Price" | Không có dòng Item Price nào trong bảng giá đang dùng, hoặc dòng đã **hết hiệu lực** / **khác tiền tệ** | Kiểm bảng giá đang dùng (binding → `price_list`, nếu không có → Selling Settings); kiểm `valid_from/valid_upto`, `currency` |
| Giá 0 riêng dòng Rule | Mã resolve ra không có Item Price | Batch #6 có cảnh báo riêng; xem `errors.bom_items` |
| **Dòng kính ra giá 0 (và trọng lượng 0) khi kính lấy theo `default_glass_master`** | **Đã vá Pha 3** — mã kính mặc định giờ tra giá ở batch #2b (mục 4.6). Nếu vẫn 0: mã kính chưa có dòng `Item Price` trong bảng giá | Xem cảnh báo `thieu_gia_item:<mã kính>` trong `errors.bom_items`; thêm dòng Item Price cho mã kính |
| `multiplier_chain` ra giá lạ | Không có dòng giá **"trần"** ⇒ lấy dòng đầu làm giá gốc (đã gồm phụ phí) rồi nhân tiếp | Cảnh báo `gia_goc_thieu_dong_tran`; thêm 1 dòng Item Price **không set** dimension nào |

### 9.3 Dòng không vào bucket

- **Dấu hiệu:** tổng vật liệu nhỏ hơn tổng các dòng, hoặc `TONG_VL` lệch.
- **Nguyên nhân:** `cost_bucket` trống. B5 **bỏ qua im lặng** (`if not bk: continue`).
- **Kiểm:** mở `al_bom_result` → `lines` → xem `cost_bucket` từng dòng; `buckets` chỉ có Nhóm khác.
- **Sửa:** gán `cost_bucket` cho dòng. ⛔ Không cần sửa công thức cost template.

### 9.4 `is_active = 0` nhưng vẫn/không thấy dòng

| Triệu chứng | Nguyên nhân |
|---|---|
| Đã tắt dòng, kết quả **vẫn có** dòng | BOM Version đang dùng còn **snapshot cũ**. Snapshot chỉ chụp lại khi tạo version mới / xuất bản version mới |
| Dòng **biến mất** không dấu vết | `is_active = 0` bị loại **ngay khi chụp snapshot** — engine chưa từng thấy dòng đó |
| Gợi ý chéo dòng **vẫn hiện** cho dòng đã tắt | Gợi ý đọc các dòng của chứng từ, ⛔ không lọc `is_active` (mục 5.4b) |

Kiểm: mở `AL BOM Version` → xem `bom_set_snapshot` (JSON) có dòng đó không.

### 9.5 `show_condition` không ẩn dòng

- **Đúng như mã đang chạy:** field được tính ra `{slug}__show_condition` nhưng **không nơi nào đọc**.
- Muốn bỏ dòng khỏi kết quả: dùng `is_active` (+ xuất bản lại version), hoặc xoá dòng khỏi Bom Set.

### 9.6 Dòng ra giá 0 do `calc_pattern` trống / sai

- `calc_pattern` trống ⇒ `lookup_calc_pattern("")` lỗi ⇒ `unit_qty = 0` ⇒ `line_total = 0` (có lỗi
  cho dòng trong `errors.bom_items`).
- Kiểm: đối chiếu `calc_pattern` với nhóm của category (nhôm → LENGTH/AREA_TO_WEIGHT; kính → AREA;
  phụ kiện → COUNT). Danh sách gợi ý: `get_available_patterns()` (`formula_handlers.py:302`).

### 9.7 Cách kiểm tổng quát — 2 chỗ

**a) `al_bom_result` trên Quotation Item** (field JSON, `custom_fields.py:34`). Cấu trúc:

```json
{
  "buckets": { "VL_NHOM": 0, "VL_KINH": 0, "VL_VTP": 0, "VL_PK": 0 },
  "cost_template": { "TONG_VL": 0, "GIA_THANH": 0, "GIA_BAN": 0, "GIA_VAT": 0 },
  "cost_template_trace": { "TONG_VL": "…" },
  "lines": [ { "slug", "item_code", "width", "height", "qty",
               "unit_qty", "total_qty", "unit_price", "line_total",
               "cost_bucket", "unit", "weight_per_unit",
               "trace", "color", "supplier_location", "install_position",
               "cut_angle", "note",
               "rule_trace", "price_trace", "calc_pattern", "scrap_pct",
               "glass_master", "total_thick_mm", "glass_type", "max_area_m2" } ],
  "gia_vat": 0, "gia_ban": 0,
  "errors": { "bom_items": { }, "cost_template": { } }
}
```

- `errors.bom_items` — lỗi/cảnh báo của bước chọn mã, tra giá, công thức dòng, diện tích kính.
- `errors.cost_template` — lỗi ở cost template (vd `lookup_rule` thiếu mã).
- `lines[].trace` — công thức width/height/qty đã thay số, đọc được "vì sao ra số này".

**b) Dialog Preview** — gọi `alumglass.api.get_result_display(quotation_item_name)`
(`api/__init__.py:1616`) để lấy dạng hiển thị: `summary`, `lines` (kèm nhãn slug + tên bucket),
`buckets`, `cost_template` (kèm `trace`), `errors`.

> API này trả **toàn bộ giá thành + công thức** ⇒ cần quyền `read` trên Quotation cha.

**Thứ tự soi khi số sai:**

1. `lines` có đủ dòng mong đợi không? → nếu thiếu: `is_active` / snapshot.
2. Dòng có `item_code` không, và mã đó có **đúng** với kính hiện tại không? → mục 9.1.
3. `unit_qty`/`total_qty` có hợp lý không? → `calc_pattern`, `width/height/qty`, `input_vars`.
4. `unit_price` có đúng bảng giá/composite không? → `price_base_item`, dimension, dòng "trần".
5. `cost_bucket` có giá trị không? → bucket.
6. `buckets` → `cost_template` → `GIA_VAT`.

---

## 10. Căn cứ tính giá — `rule_trace`, `price_trace`, `explain_bom_line`

Mỗi dòng kết quả tính giá nay mang theo **vết tra cứu** để trả lời "vì sao ra mã này / giá này"
mà ⛔ không phải đọc log hay đoán lại cấu hình.

### 10.1 Hai tầng vết trong mỗi dòng `al_bom_result.lines`

Do `b4_calculate_bom_items` ghi (additive — dòng kết quả cũ thiếu key thì client bỏ qua).
**Tách đôi theo người đọc:**

| Khoá | Cho ai | Nội dung |
|---|---|---|
| `rule_trace` | Người dùng | Câu tiếng Việt, **nhãn nghiệp vụ**: `Quy tắc "Nẹp theo độ dày kính": độ dày kính của dòng "Kính trên" = 8 mm → chọn mã "Nẹp 8" (NEP-8).` Dòng Fixed → `""` |
| `price_trace` | Người dùng | `Bảng giá "Standard Selling" · Màu sắc: Trắng · Độ dày kính: 8 mm · khớp theo Màu sắc, Độ dày kính · giá 50.000 đ`. Dòng khai `price_base_item` → thêm `Giá tra theo mã đại diện "<tên item>"`. Rơi về dòng giá gốc → `không có dòng giá khớp đủ tiêu chí — dùng dòng giá gốc của mã`. `multiplier_chain` → `giá gốc … × hệ số 1,3 = …`. Giá nhập tay → `Giá nhập tay: 50.000 đ`. Giá trị dimension `0`/rỗng bị bỏ; giá trị nhiều dòng → `Xuất xứ: nhiều lựa chọn`. **Không tra được dòng giá** → `Bảng giá "…" · Chưa tìm được dòng giá cho mã này — đang tạm tính 0 đ, thành tiền chưa đúng. Kiểm tra bảng giá "…" hoặc báo quản trị.` (không có bảng giá thì câu cuối là `Báo quản trị để bổ sung giá.`) — câu CẢNH BÁO, ⛔ không phải `giá 0 đ` trần |
| `lookup_facts` | API | Sự thật tra cứu: `code_source`, `price_match`, `match_dims`, `glass_used` (xem 10.1b) — `explain_bom_line` dựng bước từ đây |
| `rule_trace_raw` | Support | Bản **kỹ thuật** giữ nguyên `items.<slug>.<field> = 8 → RULE-NEP → NEP-8` |
| `price_trace_raw` | Support | Bản kỹ thuật: mã tra giá, docname `Item Price`, giá thô |

🔴 **Luật hiển thị (UX1 chốt):** chuỗi `rule_trace` / `price_trace` và mọi `detail` của
`explain_bom_line` **⛔ KHÔNG chứa** mã rule (`RULE-…`), docname `Item Price` (`IP-…`),
biểu thức `items.…`, slug (`kinh_tren`), mã enum (`LENGTH_ONLY`, `WHITE`). Nhãn được resolve
**tại biên** (engine/API) — JSON vẫn giữ dữ liệu kỹ thuật cho support, nhưng client chỉ hiển thị
tầng người đọc. Test âm `test_display_strings_have_no_technical_codes` chặn tái phát.

To `explain_bom_line` giải thích được **nguồn giá trị kính**, dòng kết quả còn lưu thêm:
`line_label` (tên dòng hiển thị: `line_name` → `item_name` → `glass_name`), `item_name`,
`glass_master` + `glass_master_name`, `glass_type_name`, `glass_thick` (alias cũ) +
`total_thick_mm`, `glass_type`, `max_area_m2`, `calc_pattern` + `calc_pattern_name`, `scrap_pct`,
`rule_name`, `rule_match`, `rule_input_missing`, `price_base_item`, và cờ `is_glass_row`
(1 = dòng kính — API dùng để không nói sai "không dùng dữ liệu kính" khi dòng kính chưa chọn kính).
Tất cả là **dữ liệu đã dùng lúc tính**, ⛔ không phải suy lại. Nhãn (`*_name`) lấy từ batch query
sẵn có ở B2 nên **không phát sinh N+1**: `item_name` được nạp cho **mọi** mã dòng có thể hiển thị —
mã của chính dòng (`lit.item_code`, gồm cả mã Rule đã resolve) và `price_base_item` (batch #1),
cộng mã kính lấy `glass_name` từ batch `AL Glass Master` (#3) — nhờ vậy bước 1 và câu "giá tra theo
mã đại diện" ra `"<tên vật tư>" (<mã>)` thay vì mã trần.

### 10.1b `lookup_facts` — sự thật tra cứu của từng dòng

Mỗi dòng kết quả mang thêm khoá `lookup_facts` (additive — client cũ bỏ qua). Đây là **nguồn duy
nhất** để `explain_bom_line` dựng câu giải thích: câu trả lời phải kể **đúng việc engine đã làm cho
dòng đó**, ⛔ không dựng theo khuôn "6 bước cố định" (dòng nhôm không có bước kính, dòng mã cố định
không có bước quy tắc).

| Khoá | Giá trị | Ý nghĩa |
|---|---|---|
| `code_source` | `rule` · `price_base_item` · `item_code` · `manual_price` | Mã dùng để tra giá đến từ đâu (đúng thứ tự `_price_code_for_trace`, giá nhập tay xét trước) |
| `price_match` | `composite` · `base_row` · `multiplier_chain` · `plain_row` · `none` | Nhánh tra giá **thật đã chạy**: khớp đủ tiêu chí dimension = `composite`; rơi về dòng giá "trần"/không đủ tiêu chí = `base_row`; nhân hệ số = `multiplier_chain`; chỉ có 1 dòng giá (hoặc category không khai dimension) = `plain_row`; không chọn được dòng nào = `none` |
| `match_dims` | `[{label, display, matched}]` | Dimension của **dòng giá đã chọn**, nhãn + giá trị đã resolve. `matched = true` khi tiêu chí đó **được dùng để khớp** (giá trị dòng = composite key lúc tra); `false` khi nó chỉ là thuộc tính của dòng giá (dòng gốc / dòng duy nhất). ⛔ Không suy đoán ngoài dữ liệu đã so |
| `glass_used` | bool | Dòng có **thật sự** đọc dữ liệu kính không (dòng kính, hoặc rule đọc `items.<slug>.<field>` của dòng kính) |
| `price_base_item` / `price_base_item_name` | str | Mã đại diện + tên hiển thị (cho câu bước chọn mã) |

`price_match` được phân loại tại **đúng nơi tra giá** (`_classify_price_match` gọi ngay sau
`best_partial_match_row`), ⛔ không đoán lại từ cấu hình. `match_dims.matched` cũng lấy từ composite
key đã dùng (`match_inputs`), không phải suy từ chữ nghĩa của `price_trace`.

Câu giá (`price_trace`) dựng từ các sự thật trên: `Bảng giá "…"` · các dimension của dòng giá đã chọn
· câu khớp (`khớp theo <tiêu chí>` / `không có dòng giá khớp đủ tiêu chí — dùng dòng giá gốc của mã`
/ `giá gốc X × hệ số Y`) · `giá Z`. Quy tắc dimension:
- Giá trị `0`/rỗng ⇒ **bỏ** (0 = không dùng tiêu chí đó, ⛔ không phải thông số thật).
- Giá trị **nhiều dòng** (`"IMPORT\nDOMESTIC"`, `"POWDER_COATED\nANODIZED\nWOOD_GRAIN"`) = dòng giá
  áp cho **nhiều lựa chọn** ⇒ in `Xuất xứ: nhiều lựa chọn`. ⛔ Không cắt còn 1 giá trị (đó là bịa),
  ⛔ không in chuỗi thô.
- Dimension Link: resolve tên người đọc; không resolve được ⇒ bỏ.

Câu cảnh báo "tạm tính 0 đ" dùng **cùng một hằng** `ZERO_PRICE_TRACE_PREFIX` khai ở
`engine/bom_orchestrator.py`; `api.explain_bom_line` so khớp đúng tiền tố này để đánh dấu **bước tra giá**
(xem 10.2) — ⛔ không có bản sao chuỗi thứ hai.

Dòng `Item Price` khớp được lấy từ `engine/composite_pricing.best_partial_match_row()`
(hàm chọn dòng tách ra từ `best_partial_match`; tham số `return_row` mặc định **False** nên
`fb_handlers` và các nhánh tra giá giữ nguyên hành vi).

### 10.2 API `alumglass.api.explain_bom_line(quotation_item_name, slug)`

- **Quyền:** dùng CHUNG `_require_quotation_item_permission` với `get_result_display`
  (cần `read` trên Quotation cha).
- **Nguồn dữ liệu:** đọc `al_bom_result` **đã lưu** — ⛔ KHÔNG chạy lại engine. Nhờ vậy phần
  giải thích luôn khớp đúng con số người dùng đang thấy.
- **Trả về:**

```json
{
  "success": true, "slug": "nep_moi", "label": "Nẹp trên",
  "item_code": "NEP-8", "line_total": 50000,
  "steps": [
    {"step": 1, "key": "item_code", "title": "Chọn mã vật tư", "detail": "…"},
    {"step": 4, "key": "price", "title": "Tra giá",
     "detail": "… tạm tính 0 đ …", "severity": "warning"},
    "… mỗi bước có key ổn định; SỐ bước tuỳ dòng (4–6)"
  ],
  "missing": [],
  "warn_zero_price": true,
  "hint": "Báo giá này được tính trước khi có phần giải thích. Bấm nút \"Tính giá\" để cập nhật căn cứ."
}
```

`severity` **chỉ có mặt** ở bước có số liệu CHƯA ĐÚNG nhưng KHÔNG phải "chưa lưu dữ liệu": hiện
dùng cho bước tra giá (`price`) khi engine rơi nhánh **tạm tính 0 đ** (câu `price_trace` bắt đầu/ chứa
`Chưa tìm được dòng giá cho mã này`). Bước này ⛔ **KHÔNG** vào `missing` — `missing` giữ nghĩa
"chưa lưu dữ liệu" (client tô xám), còn `severity: "warning"` client tô hổ phách + `⚠`.

`warn_zero_price: true` **chỉ khi** `line_total == 0` VÀ có ít nhất 1 bước `severity: "warning"`
(chính là bước tra giá). Client đọc **cờ này** để in banner "Dòng này đang thiếu giá — đừng chốt báo giá.",
⛔ không tự dò chuỗi tiếng Việt. Lưu ý phân biệt: `line_total == 0` do **số lượng = 0** (vd dòng
kính chưa chọn kính) ⛔ **không** bật cờ này — đó không phải thiếu giá, và việc cần làm đã nêu ở
bước 2.

`hint` **chỉ có mặt khi `missing` khác rỗng VÀ dòng là dữ liệu cũ** (`is_legacy`: không có
`rule_trace`, `price_trace` lẫn `*_raw`) — client in 1 lần ở đầu dialog (⛔ không lặp ở từng
bước). Báo giá **mới** thiếu dữ liệu (vd dòng kính chưa chọn kính) thì **không** có `hint`:
câu "tính trước khi có phần giải thích" khi đó sai nguyên nhân và bấm "Tính giá" cũng không
đổi gì — phần thiếu đã được nói đúng ngay ở `detail` của bước tương ứng.

Sáu bước, nhưng **bước 2 và 3 là TUỲ CHỌN theo dòng** — hộp giải thích chỉ dựng bước **áp dụng
thật** với dòng đang xem (dữ liệu lấy từ `lookup_facts`, xem 10.1b). `step` đánh số lại liên tục
`1..N` theo đúng thứ tự thực tế; `key` giữ nguyên bộ giá trị để client tô xám (`missing` chứa chính
các `key` này):

| Bước | `key` | Tiêu đề | Có khi nào | Nội dung |
|---|---|---|---|---|
| 1 | `item_code` | Chọn mã vật tư | luôn có, **trừ** dòng nhập giá tay | Theo `lookup_facts.code_source`: `rule` → `rule_trace` (đã là câu người đọc); `price_base_item` → `Giá tra theo mã đại diện "<tên>" (<mã>).`; `item_code` → `Dùng mã cố định "<tên>" (<mã>)`; `manual_price` → **không dựng bước này**. Rule mà chưa khai `rule_input_expr` → `Dòng này chưa khai báo quy tắc chọn mã.` + `missing` |
| 2 | `glass_source` | Nguồn giá trị kính | **CHỈ khi `lookup_facts.glass_used = true`** (dòng kính, hoặc rule đọc thông số dòng kính) | `Dòng này dùng Kính "Kính trắng 8 mm" (mã GM-01) · Kính trong · dày 8 mm`. Dòng khác đọc **dòng kính mà rule trỏ tới** (slug lấy từ `rule_trace_raw`, đọc cùng JSON) → `Giá trị lấy từ dòng "Kính trên" — … Giá trị dùng để chọn mã: Độ dày kính = 8 mm.` (fallback `glass_thick` ↔ `total_thick_mm`). Báo giá **cũ** (không cờ, không căn cứ) → ⛔ **không dựng bước** (không biết dòng có dùng kính hay không; ⛔ không dám nói "không áp dụng"). Dòng kính chưa chọn kính → `Dòng kính chưa chọn kính nên chưa tính được khối lượng — mở "Tham số BOM" → mục "Kính theo vị trí" để chọn kính, rồi bấm "Tính giá".` + `missing`. **Dòng nhôm/phụ kiện → bỏ hẳn bước** |
| 3 | `rule` | Quy tắc khớp → mã vật tư | **CHỈ khi `lookup_facts.code_source = "rule"`** | Nêu **KẾT QUẢ khớp** (`Quy tắc "<tên>": dải 6 – 10 → chọn mã "<tên>"`) — ⛔ không nhắc lại biểu thức đầu vào. Rule chưa đặt tên → nhãn chung `Quy tắc chọn mã` (⛔ không rơi về mã rule). Báo giá cũ chưa lưu căn cứ → `missing`. **Dòng dùng mã cố định / mã đại diện / giá nhập tay → bỏ hẳn bước** (⛔ không in "không dùng quy tắc…") |
| 4 | `price` | Tra giá | luôn có | `price_trace` (đã resolve nhãn bảng giá / dimension / câu khớp — xem 10.1b). Rơi nhánh **tạm tính 0 đ** → step có thêm `severity: "warning"` (⛔ KHÔNG vào `missing`) |
| 5 | `quantity` | Tính số lượng | luôn có | `calc_pattern_name` (⛔ không mã `LENGTH_ONLY`), width/height/qty, hao hụt → `unit_qty` / `total_qty` |
| 6 | `line_total` | Thành tiền và Nhóm chi phí | luôn có | `unit_price × total_qty = line_total` (định dạng `50.000 đ`) + tên Nhóm; Nhóm không resolve được tên → `nhóm chưa đặt tên` (⛔ không phơi mã Nhóm) |

Ví dụ số bước theo dòng:
- Dòng kính + rule (đọc thông số kính): **6 bước** `item_code → glass_source → rule → price → quantity → line_total`.
- Dòng nhôm dùng mã đại diện, không dùng kính: **4 bước** `item_code → price → quantity → line_total`.
- Dòng nhập giá tay: **3 bước** `price → quantity → line_total`.

- Bước nào thiếu dữ liệu: vẫn `success: true`, `detail` nói rõ thiếu gì, và `key` của bước đó
  được ghi vào `missing` — **`missing` chứa đúng các `key` xuất hiện trong `steps`**, để client
  tô xám đúng bước.
- Bước có số nhưng CHƯA ĐÚNG (tạm tính 0 đ) → `severity: "warning"`, ⛔ **không** vào `missing`;
  nếu `line_total == 0` thì kèm cờ tổng `warn_zero_price: true` (xem 10.3).
- ⛔ **Không câu nào mô tả bước không xảy ra** ("Dòng này không dùng dữ liệu kính (không áp dụng)",
  "Dòng này không dùng quy tắc…") — bước không tồn tại thì bỏ hẳn khỏi danh sách.
- Không tìm thấy slug → `{"success": false, "message": "Không tìm thấy dòng vật tư trong kết quả
  tính giá của báo giá này."}`. Câu **chung**, ⛔ không echo slug người dùng gõ (slug chỉ vào
  `frappe.logger` để support tra).
- Quyền: `_require_quotation_item_permission` ném `PermissionError` — client bắt riêng, hiện câu
  xin quyền, ⛔ không hiện `r.exc`, ⛔ không retry.

### 10.3 UI đọc ở đâu

- `alumglass.api.get_result_display` trả thêm `rule_trace` / `price_trace` cho **từng dòng**
  (pass-through, data cũ → `""`), kèm `line_label` để client không phải tự ghép tên dòng.
- Nút mở giải thích trên dòng báo giá là **icon `?` 16 px màu xám**, tooltip/`aria-label`
  "Vì sao ra số này?". Dialog hiện các bước từ `explain_bom_line` — **số bước tuỳ dòng** (4–6,
  xem 10.2); client chỉ render, ⛔ không tự ghép lại chuỗi từ nhiều field, ⛔ không giả định
  đủ 6 bước. Không còn khối "Căn cứ" inline trên lưới (tránh lặp thông tin + nặng form).
- Lỗi khi gọi API:
  - `PermissionError` / HTTP 401–403 → câu xin quyền, ⛔ không hiện `r.exc`, ⛔ không retry.
  - Có `hint` → in **một lần** ở đầu dialog (nền hổ phách nhạt `#fffbeb`).
  - `warn_zero_price: true` → banner **trên cùng** (trước cả `hint`), nền đỏ nhạt `#fef2f2`,
    viền trái hổ phách đậm `#b45309`, chữ đậm `#991b1b`: `⚠ Dòng này đang thiếu giá — đừng chốt
    báo giá.` Client đọc **cờ**, ⛔ không tự dò chuỗi `price_trace`.
  - Bước có `severity: "warning"` → tiêu đề màu `#b45309`, phần detail nền `#fffbeb` + viền
    `#fde68a` + tiền tố `⚠`. Bước thiếu dữ liệu (`missing`) vẫn tô xám như cũ.
  - `success: false` kèm `message` → hiện nguyên câu server trả.

---

## 11. Phụ lục — bảng tra file/hàm & điểm chưa kiểm

### 11.1 Bảng tra nhanh

| Việc | File · hàm · dòng |
|---|---|
| Khai báo field | `al_bom_engine/doctype/al_bom_item/al_bom_item.json` |
| Validate khi lưu dòng | `al_bom_item.py:84` `ALBomItem.validate()` |
| Backfill `input_vars` | `al_bom_item.py:47` `backfill_input_vars()`; hook `hooks.py:70` |
| Validate công thức khi lưu Bom Set | `al_bom_set/al_bom_set.py:91` `_validate_child_formulas()` |
| Cảnh báo `rule_input_expr` | `al_bom_set.py:118` `_warn_rule_input_expr()`; `al_bom_engine/formula_validate.py:95` `validate_rule_input_expr()` |
| Rule chọn mã (THRESHOLD/LOOKUP) | `al_formula_rules/doctype/al_dynamic_item_rule/al_dynamic_item_rule.py` `resolve()` |
| Chụp snapshot (loại `is_active=0`) | `al_bom_version/al_bom_version.py:108` `_take_snapshots()` |
| Chuỗi 7 bước | `engine/bom_orchestrator.py:309` `run()` |
| B0 version pinning | `bom_orchestrator.py:323` |
| B1 gom biến | `bom_orchestrator.py:380`; chuẩn hoá % `:557` |
| B2 6 batch + glass_data + row_literals | `bom_orchestrator.py:1016`; accessories `:883`; **batch #2b** (giá mã kính mặc định) `:1164` |
| Resolve input cho rule | `bom_orchestrator.py:2061` `_resolve_rule_input_for_item()` |
| Gọi AL Rule (chọn mã) | `bom_orchestrator.py:2101` `_resolve_dynamic_item()` |
| Override kính / màu | `bom_orchestrator.py:2197` / `:2237` |
| Ngữ cảnh tra giá cho dialog (b0+b1+snapshot) | `bom_orchestrator.py:956` `prepare_price_context()` |
| Tra giá 1 mã đúng đường batch #2 | `bom_orchestrator.py:978` `price_for_code()`; dòng giá thô `:998` `raw_price_row()` |
| Giá kính cho dialog (khớp engine) | `api/__init__.py:1158` `_resolve_glass_price()`; `:1230` `get_glass_master_price()` |
| Hợp đồng `glass_groups` cho dialog | `api/__init__.py:1267` `get_variable_set_for_bom()` (mục 3b/3c `:1469`, `:1557`) |
| Khoá "vị trí" kính | `al_bom_engine/glass_group_resolver.py` `glass_group_rep()` |
| B3 dựng công thức | `bom_orchestrator.py:2122`; chuẩn hoá `items.X.Y` `:2306` |
| `lookup_calc_pattern` | `formula_handlers.py:209`; bảng built-in `:28` |
| B4 tính + validate diện tích | `bom_orchestrator.py:2417`; `:2533` |
| B5 gom bucket | `bom_orchestrator.py:2568` |
| B6 cost template | `bom_orchestrator.py:2694` |
| Thuật toán tra giá composite | `engine/composite_pricing.py:25` `best_partial_match_row()` |
| Hai `pricing_mode` | `fb_handlers.py:82` `aluminum_price_composite()`; nhánh nhanh `bom_orchestrator.py:1597`, `:1685` |
| Ghi kết quả | `bom_orchestrator.py:2850` `b7_save_results()` |
| Vết chọn mã / tra giá (B4) | `bom_orchestrator.py` `_build_rule_trace()` / `_build_price_trace()` / `_price_match_sentence()` |
| Sự thật tra cứu mỗi dòng (`lookup_facts`) | `bom_orchestrator.py` `_classify_price_match()` (phân loại nhánh tra giá) · `_code_source()` · `_matched_dim_entries()` · `_build_lookup_facts()` |
| Chọn dòng Item Price (trả cả dòng) | `engine/composite_pricing.py` `best_partial_match_row()` |
| Dạng hiển thị cho Preview | `api/__init__.py:1616` `get_result_display()` |
| Giải thích 1 dòng (bước theo dòng) | `api/__init__.py` `explain_bom_line()` |
| Nguồn của biến (một chỗ duy nhất) | `variable_sources/field_provenance.py` `ROW_LITERAL_SOURCES` |
| Đồng bộ dữ liệu alias trên site cũ | `patches/v28_15/sync_variable_sources_and_fields.py` |
| Gợi ý chéo dòng | `variable_sources/adapters.py:840` `build_references()`; `:794` `_append_references()` |
| Profile mặc định của Bom Set | `patches/v28_14/seed_bom_profile.py` — `P_BOM_DEFAULT`, `CROSS_ROW_FIELDS` (dòng 70) |
| Bộ mẫu 2C | `setup/seed_demo_data.py` `_bom_items_and_set()` (~dòng 328-341) |

### 11.2 Điểm **chưa kiểm được** (ghi rõ để người sau không đoán)

1. **Chưa chạy engine trên site.** Số ở mục 7 là tính tay. Tài liệu `docs/quotation-pricing-flow.md`
   ghi alumglass **chưa được cài trên site nào**, nên ⛔ không có chỗ chạy đối chứng. Cần kiểm lại
   bằng `run_test` khi có site.
2. **`get_category_requirements()` không có nơi gọi trong repo.** Hàm trả `default_calc_pattern`,
   `default_cost_bucket`, các cờ `requires_*` (`al_bom_item.py:190-205`) — dùng cho client tự điền.
   `grep` `.js` **không** thấy chỗ gọi. ⇒ **Cần kiểm trên site** xem form có tự điền bucket/pattern từ
   category hay không (có thể qua custom script ngoài repo).
3. **`show_condition` "không có consumer"** — kết luận từ `grep` toàn repo `alumglass`. Nếu có app
   ngoài repo đọc field/biến này thì phải sửa lại kết luận.
4. **`rule_input_expr` trỏ vào field không phải field kính** — đọc mã cho thấy input sẽ ra `0` tại
   thời điểm resolve rule (vì `row_literals` dựng sau). **Chưa chạy thực tế** để xác nhận toàn bộ hệ
   quả (dòng sau đó có thể không có mã, hoặc khớp dải `0` như mục 4.3).
5. **Chú thích `validate_rule_input_expr` lệch mã chạy** (mục 3.3): chú thích nói có fallback về
   `glass_thick`/`glass_type` của chính dòng khi không có ref; hàm đang chạy trả `None` ⇒ bỏ qua.
   Hành vi fallback thuộc hàm cũ `_resolve_rule_input()` **không có nơi gọi**. Cần DEV xác nhận đây
   là chú thích cũ cần sửa, ⛔ không phải đường chạy.
6. **Gợi ý dạng chỉ số `items[0].<field>`** — có sinh trong autocomplete (`include_index_form = 1`)
   nhưng: (a) regex của `rule_input_expr` **không nhận** dạng này; (b) `normalize_global` của
   Formula Builder (`formula_builder/table_formula_builder.py:77-89`, regex `\w+\.(\w[\w-]*)\.(\w+)`)
   cũng **không** khớp dạng có `[0]`. Suy ra: chèn dạng chỉ số vào field công thức thường cũng
   **gần như chắc chắn ra 0**. **Chưa chạy để xác nhận** — nếu dùng UI thật thấy chèn được, cần đo lại.
7. **`price_type` = `Rule` / `Fixed`** — mã ghi rõ "2 giá trị chưa từng có mã nào xử lý"; tôi xác
   nhận engine không đọc, nhưng **chưa** kiểm xem có custom client script nào chặn/đổi hành vi không.
8. **Đường chậm `_fetch_composite_prices_via_fb_slow`** (khi 0 hoặc >1 binding pricing) — đã đọc mã,
   chưa đo khác biệt kết quả so với đường nhanh trên dữ liệu thật.
9. **Gợi ý chéo dòng** — mục 5 đọc từ `build_references`/`_append_references` và patch seed; **chưa
   mở form thật** để đối chiếu danh sách gợi ý hiển thị. Nếu site đã sửa `cross_row.fields` khác
   `P_BOM_DEFAULT` thì danh sách thực tế sẽ khác.
