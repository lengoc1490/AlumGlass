# Nguồn biến theo DocType — setting ở đâu, lấy từ đâu, runtime dùng ở bước nào

> **Mốc code tài liệu này mô tả**
>
> | | |
> |---|---|
> | App | `alumglass` — nhánh `main` (2026-11-13), **working tree có thay đổi v28_14 chưa commit** |
> | Phạm vi | Từng DocType của hệ biến: nơi khai, adapter đọc, điều kiện lọc, bước runtime dùng |
> | Đối tượng | Người cấu hình BOM (BOM Manager) và người bảo trì mã (DEV) |
> | ⛔ Ngoài phạm vi | Thao tác bấm trên form (xem [huong-dan-setting-bien.md](huong-dan-setting-bien.md)); shape API (xem [api-reference.md](api-reference.md)) |
> | Ngày soạn | 2026-11-13 |
>
> **Mức kiểm chứng:** ⛔ **chưa chạy `bench migrate`, chưa mở form trên site nào**. Mọi khẳng định
> dưới đây đọc từ mã trong working tree: `alumglass/variable_sources/*`, `alumglass/api/*`,
> `alumglass/engine/bom_orchestrator.py`, JSON DocType và patch `v28_14/seed_variable_catalog.py`.
> Chỗ nào suy ra từ mã mà chưa chạy thật, ghi rõ **"theo mã"**.

> 🔴 **Bốn câu hỏi của mọi mục DocType** — mỗi mục đều trả lời đúng thứ tự này:
> **1.** Setting ở đâu (form nào, field nào) · **2.** Gợi ý lấy từ đâu (adapter nào) ·
> **3.** Theo điều kiện gì (cờ nào, lọc gì) · **4.** Runtime có dùng không, bước nào (B0–B7).

**Đọc nhanh:**

| Bạn cần | Mục |
|---|---|
| Xem mọi DocType trong một bảng | §1 |
| `AL Bom Set` / `AL Bom Item` | §2.1 |
| `AL Accessory Set` / `AL Accessory Item` | §2.2 |
| `AL Cost Template` / Item | §2.3 |
| Profile · Rule · Cross Row · Settings | §3.1 · §3.2 |
| Library · Variable Set · Cost Bucket | §3.3 · §3.4 · §3.5 |
| Global Variable · Binding · Formula Field | §3.6 · §3.7 · §3.8 |
| Nguồn biến → điều kiện lọc | §5 |
| Luồng runtime B0–B7 | §6 |
| Bốn ví dụ "biến này từ đâu ra" | §8 |
| Bảng tra nhanh tên biến | §9 |

---

## 0. Cách đọc — hai mặt phẳng, đừng lẫn

Hệ biến của AlumGlass có **hai mặt phẳng tách rời**. Lẫn hai mặt phẳng này là nguồn gốc của gần
như mọi hiểu nhầm về "setting xong mà giá không đổi":

| | Mặt phẳng GỢI Ý (design-time) | Mặt phẳng RUNTIME (tính giá) |
|---|---|---|
| Ai chạy | `alumglass/variable_sources/*` + `alumglass/api/*` | `alumglass/engine/bom_orchestrator.py` |
| Đọc gì | `AL Variable Profile` (rule, cross-row) | ⛔ **không đọc profile** |
| Kết quả | danh sách biến người dùng thấy khi gõ công thức | giá trị số trong `al_bom_result` |
| Đổi có ra tiền không | **⛔ không** | **có** |

Điểm nối duy nhất giữa hai mặt phẳng là **dữ liệu nền**: `AL Variable Library`,
`Formula Global Variable`, `Formula Variable Binding`, `AL Variable Set`, `AL Cost Bucket`,
`AL Profile System`, `AL Product Type`, `AL Variable Settings` (row literal / common var).
Sửa mấy bảng này đổi **cả** gợi ý **lẫn** giá trị tính.

Ký hiệu bước runtime dùng xuyên suốt tài liệu:

```
B0 version pinning · B1 gom inputs · B2 prefetch master data · B3 dựng công thức
B4 tính dòng vật tư · B5 gom cost bucket · B6 tính cost template · B7 ghi kết quả
```

---

## 1. Bảng tổng — mỗi DocType một dòng

Cột **"Bước runtime dùng"** chỉ ghi bước **thật sự đọc dữ liệu của DocType đó**. Ô `—` nghĩa là
engine B0–B7 ⛔ không đọc; DocType chỉ tồn tại cho mặt phẳng gợi ý / validate.

| DocType | Vai trò trong hệ biến | Nơi chứa cấu hình (chính) | Adapter / `source_kind` | Bước runtime dùng | Cần `is_active`? |
|---|---|---|---|---|---|
| `AL Bom Set` | Chứng từ mẹ của BOM; nối tới Profile System, Product Type, Variable Set, bộ phụ kiện | `profile_system`, `product_type`, `variable_set`, `default_accessory_set`, `variable_profile`, `formula_fieldnames`, `apply_scrap_pct` | `variable_set` (nhánh AUTO), `fvb_scope`, `doctype_field` | B1 (profile_system → system var), B2 (`formula_fieldnames`, `default_accessory_set`), B3 (`apply_scrap_pct`) | Có field, **engine ⛔ không đọc** |
| `AL Bom Item` | Một dòng vật tư: chứa **công thức** `width/height/qty/show_condition` và các literal của dòng | `slug`, `width`, `height`, `qty`, `show_condition`, `item_condition_formula`, `rule_input_expr`, `calc_pattern`, `input_vars`, `cost_bucket`, `ctx_inject_prefix` | `slug_reference` (references `items.<slug>.<field>`), `ct_*` (qua B3) | B3 (dựng `{slug}__*`), B4 (DAG), B5 (`cost_bucket`) | Có — **lọc lúc chốt BOM Version** |
| `AL Accessory Set` | Bộ phụ kiện nạp thêm vào BOM dưới bucket `VL_PK` | `variable_set`, `variable_profile`, `items` | `variable_set` (nhánh a), `slug_reference` | B2 (`_load_accessories`) | Có field, **engine ⛔ không đọc** |
| `AL Accessory Item` | Một dòng phụ kiện: `qty_formula` là **công thức**, không phải biến | `slug`, `qty`, `qty_formula`, `unit_price`, `calc_pattern`, `cost_bucket` | `slug_reference` | B2 (literal), B3 (`qty_formula` → `{slug}__qty`) | Không có field |
| `AL Cost Template` | Bảng giá thành: các dòng `line_code` nối bucket → giá bán | `variable_profile`, `items` | `cost_template_line` (nhánh sửa `items`) | B6 (đọc **snapshot** của version) | Có field, **engine ⛔ không đọc** |
| `AL Cost Template Item` | Một dòng giá thành: `line_code`, `calc_formula`, cờ giá cuối | `line_code`, `calc_formula`, `cost_bucket`, `is_final_price`, `is_pre_vat_price` | `cost_template_line` | B6 | Không có field |
| `AL Cost Bucket` | Mã bucket **là một biến** nhận giá trị sau B5 | `bucket_code`, `bucket_role`, `source_type`, `source_config` | `cost_bucket` | B5 (đọc `source_type`/`source_config`), B6 (giá trị bucket) | Adapter lọc `1`; **B5 ⛔ không lọc** |
| `AL Variable Profile` | Bộ lọc gợi ý theo ngữ cảnh | `default_action`, `rules`, `cross_row`, `is_active` | (điều khiển adapter, không sinh biến) | **⛔ không dùng** | Có — catalog bỏ profile tắt |
| `AL Variable Profile Rule` | Một luật Include/Exclude (13 cột) | `action`, `source_kind`, `source_ref`, `only_fields`… | (điều khiển lọc) | **⛔ không dùng** | Có (mặc định bật) |
| `AL Variable Cross Row` | Khai bảng/field được gợi ý chéo dòng | `table_field`, `id_field`, `fields`, `enabled` | (điều khiển `references`) | **⛔ không dùng** | Dùng `enabled` |
| `AL Variable Settings` | Single: profile mặc định, doctype xem trước, danh sách biến dùng chung | `default_profile`, `preview_doctype`, `common_variables`, `row_literals` | `common_var`, `row_literal` | **⛔ không dùng** (chỉ validate đọc tên row literal) | Single không có |
| `AL Common Variable` | Một biến người dùng nhập (W_mm, H_mm…) | `var_name`, `var_type`, `is_active` | `common_var` | ⛔ không dùng — giá trị đến từ `al_bom_vars` | Có (dòng) |
| `AL Row Literal` | Một field engine inject theo dòng (unit_price, glass_thick…) | `var_name`, `var_type`, `is_active` | `row_literal` | ⛔ không dùng — B3 inject theo danh sách cứng | Có (dòng) |
| `AL Variable Library` | Từ điển biến: system var (auto resolve) và user var (default) | `is_system`, `source_doctype`, `source_field`, `source_link_field`, `default_value` | `variable_library_system`, `variable_library_user` | B1 (1.3 fallback, 1.6 default) | Không có field |
| `AL Variable Set` | Bộ biến của một sản phẩm, đổ vào dialog "Tham số BOM" | `set_code`, `product_type`, `is_active`, `items` | `variable_set` | ⛔ không dùng — chỉ nuôi dialog | Có — chỉ nhánh `product_type` lọc |
| `AL Variable Set Item` | Một biến trong bộ | `variable`, `default_value`, `sort_order` | (qua `variable_set`) | ⛔ không dùng | Không có field |
| `AL Profile System` | Hệ nhôm: các `offset_*` + bảng `system_variables` | `offset_frame/glass/fixed/crossbar`, `system_variables` | `variable_library_system`, `fvb_scope` | B1 (1.3/1.4/1.5c resolve system var) | Có field, resolver ⛔ không kiểm |
| `AL Profile System Variable` | Override giá trị biến hệ cho một hệ nhôm | `variable`, `value`, `is_active` | (qua resolver) | B1 (1.4b) | **Có** — dòng tắt bị bỏ |
| `Formula Global Variable` | Hằng số toàn cục | `var_name`, `value_source`, `constant_value`, `is_active` | `formula_global` | B1 (1.2) | **Có** — B1 lọc `1` |
| `Formula Variable Binding` | Binding sinh giá trị theo scope doctype/field | `variable_name`, `source_type`, `applies_to_doctype`, `applies_to_field`, `is_active` | `fvb_scope` | B1 (1.4 get_live_context), B2 (binding giá) | **Có** — scope API lọc `1` |
| `AL Formula Field` | Sổ đăng ký field nào có autocomplete công thức | `target_doctype`, `child_table`, `fieldname`, `id_field` | (điều khiển client) | ⛔ không dùng | **Có** — API lọc `1` |
| `AL Slug Library` | Danh mục slug dòng + nhóm hiển thị | `slug`, `label`, `category`, `group_tag` | `slug_reference` (dò field định danh) | ⛔ không dùng (engine dùng `slug` trên dòng) | Có field, query references ⛔ không lọc |
| `AL Quantity Calc Method` | Pattern số lượng: `calc_fn`, `input_vars`, `output_unit` | `calc_pattern_code`, `input_vars`, `calc_fn`, `output_unit` | — | B3 (`input_vars`), B4 (`lookup_calc_pattern`, `output_unit`) | Không có field |
| `AL Calculation Rule` | Rule CONSTANT/THRESHOLD/LOOKUP cho `lookup_rule()` | `rule_code`, `rule_type`, `constant_value`, bảng ngưỡng/tra | — | B1 (fallback CONSTANT), B4 + B6 (`lookup_rule`) | Có field, `_lookup_rule` ⛔ không kiểm |
| `AL Product Type` | Loại sản phẩm + % nhân công/lợi nhuận | `nc_pct`, `nc_ld_rate`, `profit_margin` | `variable_library_system` (nguồn resolve) | B1 (1.3/1.4 resolve system var) | Không có field |
| `AL Material Category` | Nhóm vật tư + `default_scrap_pct`, `has_weight` | `default_scrap_pct`, `has_weight`, `default_cost_bucket` | — | B2 (batch #4), B3 (`apply_scrap_pct`) | Có field, B2 ⛔ không lọc |
| `AL Pricing Dimension` | Một chiều giá (màu, độ dày…) | `dimension_code`, `custom_fieldname`, `represents_color` | — | B2 (composite key), snapshot lúc publish | **Có** — snapshot lọc `1` |
| `AL Variable Dimension Mapping` | Biến ↔ chiều giá + `price_multiplier` | `variable_name`, `pricing_dimension`, `material_category`, `price_multiplier` | — | B2 (composite key) | **Có** — cả snapshot và live đều lọc |
| `AL Alert Config` | Cấu hình cảnh báo, có field công thức `trigger_condition` | `trigger_condition`, `variable_profile`, `is_active` | — | **⛔ không dùng** (chưa có engine cảnh báo) | Có field, ⛔ không ai đọc |

---

## 2. Nhóm chứng từ nghiệp vụ

### 2.1 `AL Bom Set` (+ `AL Bom Item`)

**Vai trò:** chứng từ mẹ. `AL Bom Item` là nơi chứa **công thức**, và engine biến mỗi dòng thành
một nhóm biến `{slug}__{field}`.

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `AL Bom Set`: `profile_system`, `product_type`, `variable_set`, `default_accessory_set`, `variable_profile`, `formula_fieldnames`, `apply_scrap_pct`. `AL Bom Item`: `width`, `height`, `qty`, `show_condition`, `item_condition_formula`, `rule_input_expr`, `calc_pattern`, `input_vars`, `cost_bucket` |
| **Gợi ý lấy từ đâu (adapter)** | `variable_set` (nhánh AUTO dò field Link), `fvb_scope` (binding scope `AL Bom Set` + `AL Bom Item`), `doctype_field` (field vô hướng của chính dòng). Biến chéo dòng do `build_references` sinh từ `AL Variable Cross Row` |
| **Điều kiện gì** | Profile đang gán phải `is_active=1`; rule phải `is_active=1`; `only_fields` là **cổng mức rule**; `AL Bom Item.is_active` **chỉ lọc lúc chốt BOM Version** |
| **Runtime dùng không** | **B1** `profile_system` → resolve system var. **B2** `formula_fieldnames`, `default_accessory_set`. **B3** `apply_scrap_pct`, dựng `{slug}__*`. **B4** tính DAG. **B5** đọc `cost_bucket` từng dòng |

> **Profile mẫu `P_BOM_DEFAULT`** (patch `seed_bom_profile`): 6 rule Include
> (`variable_library_system`, `variable_set` AUTO, `common_var`, `formula_global`, `fvb_scope` AUTO,
> `slug_reference items`) + cross-row `items` 12 field. ⛔ Cố ý không có `cost_bucket` (chỉ sinh ở
> B5, công thức Bom Item chạy B4), `row_literal` trần (`unit_price`… không tồn tại trong namespace
> B4 — dùng `items.<slug>.unit_price`) và `cost_template_line` (chỉ có ở B6).

#### Field công thức — cái nào tham gia runtime

`FORMULA_FIELDS = ("width", "height", "qty", "show_condition")` — `al_bom_item.py:11`.
Engine dựng công thức cho **mọi** field có mặt trong `formula_fieldnames` của Bom Set, không có
thì dùng `DEFAULT_FORMULA_FIELDS` (`bom_orchestrator.py:239-240`):
`width`, `height`, `qty`, `show_condition`, `item_condition_formula`, `rule_input_expr`.

| Field | Sinh biến | Runtime dùng kết quả không |
|---|---|---|
| `width` | `{slug}__width` | **Có** — vào `unit_qty` và `bom_result.width` |
| `height` | `{slug}__height` | **Có** — vào `unit_qty` và `bom_result.height` |
| `qty` | `{slug}__qty` | **Có** — vào `total_qty` |
| `show_condition` | `{slug}__show_condition` | **⛔ Không.** Chỉ được tính ra một giá trị; B4/B5 ⛔ không đọc lại để loại dòng — mọi dòng trong snapshot đều thành 1 dòng kết quả |
| `item_condition_formula` | `{slug}__item_condition_formula` | **⛔ Không** — cùng lý do |
| `rule_input_expr` | `{slug}__rule_input_expr` | **⛔ Không đọc kết quả.** B2 đọc **chuỗi gốc** bằng regex `items.<slug>.<field>` (`bom_orchestrator.py:1961-1968`) |
| `panel_count_formula`, `qty_per_panel_formula` | không sinh | **⛔ Không** — cố ý không đăng ký ở `AL Formula Field` (xem chú thích `formula_setup.js:228-230`) |
| `ctx_inject_prefix` | không sinh | **⛔ Không** — engine B0–B7 không đọc field này; chỉ dùng cho validate (`al_bom_item.py:130`) |
| `formula_set` | không sinh | **⛔ Không** — chưa có chỗ đọc trong engine |

#### Namespace `{slug}__{field}` — engine inject gì cho mỗi dòng

B3 (`b3_build_formulas`) chạy đúng thứ tự sau cho **từng** dòng:

| Nhóm | Khoá được ghi vào `inputs` | Nguồn |
|---|---|---|
| 6 literal | `{slug}__weight_per_unit`, `__unit_price`, `__calc_pattern`, `__glass_thick`, `__glass_type`, `__scrap_pct` | `row_literals[slug]` dựng ở B2 |
| Mặc định 0 | `{slug}__width`, `__height`, `__qty`, `__weight_per_unit`, `__unit_price`, `__scrap_pct`; `__calc_pattern` = `""` | đặt trước để công thức không `NameError` |
| Biến phụ của pattern | `{slug}__{tên}` cho từng tên trong `AL Quantity Calc Method.input_vars` | ưu tiên: `AL Bom Item.input_vars` → user input → `row_literals` → `0` |
| Synthetic (luôn có) | `{slug}__unit_qty` = `lookup_calc_pattern(calc_pattern, width, height, weight_per_unit[, extra])`; `{slug}__total_qty` = `unit_qty × qty` (× `1 + scrap_pct/100` nếu bật `apply_scrap_pct`); `{slug}__line_total` = `total_qty × unit_price` | B3 |
| Dict lồng | `inputs["items"]` = `{slug: {field: value}}` | dựng từ chính các khoá `{slug}__{field}` ở trên |

> ⚠️ **`items` là dict theo slug, ⛔ không phải list.** Dòng mã `self.inputs["items"] =
> dict(nested_items)` (`bom_orchestrator.py:2162`) khoá theo slug. Vì vậy dạng `items[0].width`
> **không** lấy được dòng — xem mục 7(c).

**Những field KHÔNG được inject** (dù có trong `AL Variable Settings.row_literals`):
`has_weight`, `color`, `supplier_location`, `install_position`, `cut_angle`, `note`,
`max_area_m2`. Chúng chỉ nằm trong `row_literals[slug]` để hiển thị Preview, ⛔ không thành
`{slug}__<field>`.

#### Validate khi lưu (`AL Bom Set`)

| Việc | Hàm | Điều kiện |
|---|---|---|
| Duy nhất slug | `_validate_slug_uniqueness` | trùng slug ⇒ `throw` |
| Công thức | `_validate_child_formulas` → `check_formula_fields(item, FORMULA_FIELDS, known_names, allow_cross_row=True)` | sai cú pháp / biến lạ ⇒ `throw` |
| `rule_input_expr` | `_warn_rule_input_expr` | chỉ `msgprint` cam, ⛔ không chặn |
| Universe cross-row | `_cross_row_known_fields()` = `FORMULA_FIELDS` ∪ `ENGINE_SYNTHETIC_FIELDS` ∪ tên row literal đang bật | superset **chỉ nới validate** |

`ENGINE_SYNTHETIC_FIELDS = ("unit_qty", "total_qty", "line_total")` — `al_bom_item.py:18`.

> 🔴 **Superset ⛔ không làm field lạ có giá trị lúc runtime.** Khai `items.x.max_area_m2` vào
> `cross_row.fields` thì validate cho qua (vì `max_area_m2` là row literal đang bật), nhưng B3
> ⛔ không tạo `x__max_area_m2` ⇒ công thức ra `0`. Ngược lại `has_weight`/`color` **không** nằm
> trong superset ⇒ Lưu bị chặn "Biến chưa khai báo".

### 2.2 `AL Accessory Set` (+ `AL Accessory Item`)

**Vai trò:** bộ phụ kiện (tay nắm, khoá, bản lề…) được nạp **thêm** vào danh sách dòng BOM, mặc
định vào bucket `VL_PK`.

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `AL Accessory Set`: `variable_set`, `variable_profile`, `items`. `AL Accessory Item`: `slug`, `qty`, `qty_formula`, `unit_price`, `calc_pattern`, `cost_bucket` |
| **Gợi ý lấy từ đâu** | `variable_set` (nhánh a: field Link trực tiếp), `variable_set` (nhánh AUTO), `slug_reference` sinh `items.<slug>.<field>` |
| **Điều kiện gì** | Bộ phụ kiện được chọn theo `al_bom_vars.accessory_set` (ưu tiên) hoặc `AL Bom Set.default_accessory_set`. `is_active` của bộ **⛔ không được kiểm** |
| **Runtime dùng không** | **B2** `_load_accessories` — append từng dòng thành một `bom_items` row; `qty_formula` trở thành `qty`; `unit_price` dương thì ghi đè literal. **B3/B4/B5** xử lý y như dòng BOM thường |

#### Vì sao `qty_formula` ⛔ **không phải** biến

| Sự thật | Chỗ kiểm |
|---|---|
| `qty_formula` là **chuỗi công thức**, engine không tạo `{slug}__qty_formula` | `_load_accessories` đặt `"qty": qty_formula if qty_formula else (qty or 1)` (B2) |
| B3 chỉ có `{slug}__qty` (kết quả), `__unit_price`, `__calc_pattern`, `__total_qty`, `__line_total` | `b3_build_formulas` |
| Vì vậy `cross_row.fields` của profile mẫu **cố ý bỏ** `qty_formula` | `seed_variable_catalog.py:226-234` |

Bảng literal của dòng phụ kiện (`row_literals[slug]`), dựng ở B2:

| Field | Giá trị lấy từ |
|---|---|
| `item_code` | `AL Accessory Item.item_code` |
| `unit_price` | `AL Accessory Item.unit_price` nếu khác `None/""/0`; ngược lại theo giá tra được |
| `calc_pattern` | `AL Accessory Item.calc_pattern`, mặc định `"COUNT"` |
| `weight_per_unit` | `Item.weight_per_unit` (batch #1) |
| `scrap_pct`, `has_weight` | `AL Material Category` của dòng (dòng phụ kiện để `category=""` ⇒ 0) |
| `color` | resolve theo `default_color` nếu dòng tham gia nhóm màu |

Validate: `ACCESSORY_FORMULA_FIELDS = ("qty_formula",)`; `cross_row_fields` lấy **mọi field vô
hướng** của `AL Accessory Item` theo meta rồi **hợp** `ENGINE_SYNTHETIC_FIELDS` (`unit_qty`,
`total_qty`, `line_total`) — permissive có chủ đích, `al_accessory_set.py:_cross_row_fields`.
Ba field tổng hợp do engine B3 sinh, ⛔ không có trong meta; trước bản vá 2026-11-13 chúng bị
**chặn oan** khi Lưu dù runtime có giá trị. Test: `test_accessory_cross_row_known_fields.py` 9/9.

### 2.3 `AL Cost Template` (+ `AL Cost Template Item`)

**Vai trò:** bảng giá thành. Mỗi dòng có `line_code` và `calc_formula`; dòng có
`is_final_price=1` là giá bán cuối.

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `AL Cost Template`: `variable_profile`, `items`. `AL Cost Template Item`: `line_code`, `line_label`, `calc_formula`, `cost_bucket`, `is_final_price`, `is_pre_vat_price` |
| **Gợi ý lấy từ đâu** | `cost_template_line` (các `line_code`), `cost_bucket`, `variable_library_system`, `formula_global`, `fvb_scope`, `common_var` (profile mẫu `P_COST_TEMPLATE_DEFAULT`) |
| **Điều kiện gì** | `cost_template_line` **chỉ lọc dòng trước** dòng đang sửa khi API có `row_index`; profile tắt (`is_active=0`) ⇒ rơi về legacy |
| **Runtime dùng không** | **B6** — đọc `cost_template_snapshot` của BOM Version (hoặc doc live khi có `_cost_template` override) |

#### Nguồn biến của B6 là `inputs ⊕ buckets`

```
extra_context = dict(self.inputs)     # biến toàn cục, system var, user var, row literal...
extra_context.update(self.buckets)    # giá trị bucket đã gom ở B5
engine.calculate({**extra_context, **self.inputs})   # inputs thắng nếu trùng tên
```

Hệ quả phải nhớ:

| Hệ quả | Vì sao |
|---|---|
| ⛔ **Không có** `{slug}__*` trong B6 | B6 không nhận `items` dict của B4; công thức dùng `items.x.y` sẽ ra 0/lỗi |
| ⛔ **Không có cross-row** | Cùng lý do — nên profile mẫu ⛔ gợi ý `slug_reference` cho `AL Cost Template`. ⚠️ Thấy `items.*` không có nghĩa profile này khai slug: xem [al-variable-profile.md](al-variable-profile.md) §7.2.1 (nhánh `INCLUDE_ALL`, hoặc bản ghi chưa resolve được profile ⇒ đường legacy) |
| Bucket chỉ **có giá trị sau B5** | Trước B5 mọi `bucket_code` đều chưa có trong `self.buckets` |
| Biến trùng tên bucket ⇒ **input thắng** | Lớp `self.inputs` được trải sau cùng |
| `line_code` chỉ dùng được khi **đứng trước** | B6 tính tuần tự theo bảng; tham chiếu dòng sau = tham chiếu vòng |

#### `cost_template_line` — vì sao chỉ là gợi ý "một nửa"

| Đường gọi | Có `row_index`? | Adapter cắt dòng trước? |
|---|---|---|
| Preview trong form (nút Xem trước) | **⛔ Không** — dialog chỉ có 4 ô: doctype, bản ghi, bảng con, field | ⛔ Không |
| Autocomplete bulk (`formula_setup.js`) | **⛔ Không** — chỉ gửi `doctype`, `docname`, `child_table` | ⛔ Không |
| Validate `AL Cost Template` (`_lineCodesBefore`) | Client tự cắt theo vị trí rồi mới validate | Có (phía client) |
| Gọi API trực tiếp có `row_index` | Có | **Có** — `rows[:ctx.row_index]` |

Vì vậy: khi sửa dòng thứ `n`, autocomplete **có thể hiện cả dòng sau**; tham chiếu dòng sau vẫn
ra 0/None lúc tính.

#### Cờ giá — không hardcode tên dòng

`_resolve_final_price()` dò dòng `is_final_price=1`, không có thì fallback `cost_result["GIA_VAT"]`.
`_resolve_pre_vat_price()` tương tự với `is_pre_vat_price=1` / `GIA_BAN`.
`AL Cost Template.product_type` **có trên form nhưng engine ⛔ không đọc** — chọn template đi qua
`AL BOM.default_cost_template`.

---

## 3. Nhóm cấu hình biến

### 3.1 `AL Variable Profile` + `AL Variable Profile Rule` + `AL Variable Cross Row`

**Vai trò:** quyết định **người dùng thấy biến nào**. ⛔ Không tham gia tính tiền.

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `AL Variable Profile`: `profile_code`, `default_action`, `rules`, `cross_row`, `is_active`. Gán cho chứng từ qua field `variable_profile` (có trên `AL Bom Set`, `AL Accessory Set`, `AL Cost Template`, `AL Alert Config`) |
| **Gợi ý lấy từ đâu** | Chính profile **điều khiển** adapter nào chạy: `active_source_kinds()` |
| **Điều kiện gì** | `is_active=1`; rule `is_active=1`; `default_action` = `INCLUDE_ALL` / `EXCLUDE_ALL` |
| **Runtime dùng không** | **⛔ Không.** `bom_orchestrator.py` ⛔ không đọc `variable_profile` ở bất kỳ bước nào |

#### Cấu trúc rule — đúng **13 cột**

`AL Variable Profile Rule` (`al_variable_profile_rule.json`):

| # | Field | Nhận gì | Ghi chú dễ sai |
|---|---|---|---|
| 1 | `action` | `Include` / `Exclude` | **Exclude luôn thắng Include** |
| 2 | `source_kind` | 11 giá trị (10 adapter + `slug_reference`) | chọn sai ⇒ rule không khớp gì |
| 3 | `source_ref` | `*` / rỗng / `AUTO` / danh sách ngăn `\|` | nghĩa khác nhau theo từng nguồn — xem mục 5 |
| 4 | `group_label` | tên nhóm hiện trong autocomplete | |
| 5 | `sort_order` | số nguyên (mặc định 100) | nhóm nhỏ đứng trước |
| 6 | `is_active` | bật/tắt rule | |
| 7 | `name_prefix` | danh sách tiền tố ngăn `\|` | **phân biệt hoa thường** |
| 8 | `name_regex` | regex Python, `re.search` | regex hỏng ⇒ coi như không khớp |
| 9 | `category_tag` | so với `category` hoặc `group` của biến | không phân biệt hoa thường |
| 10 | `var_type` | `Float`…`Percent` | so khớp **chính xác** |
| 11 | `source_type` | `source_type` của FVB (vd `custom_function`) | chỉ có tác dụng với `fvb_scope` |
| 12 | `only_fields` | **JSON list** tên field | `[]`/trống = **không giới hạn** |
| 13 | `require_value` | chỉ hiện khi có giá trị thật | cổng **toàn cục** cho biến đó |

> 🔴 **`only_fields` là cổng mức RULE, ⛔ không phải allowlist từng biến.**
> Nhiều rule cùng khớp một biến ⇒ phạm vi là **hợp**; một rule không giới hạn ⇒ biến không giới
> hạn (`_merge_only_fields`, `rules.py:229-245`). Muốn mỗi field một danh sách riêng thì **tách
> biến giữa các rule** bằng `source_ref` / `name_prefix`.
>
> ⛔ Rule **không có** `bucket_role`; ⛔ không có cú pháp `var_name in [...]`; ⛔ không có
> `variable_profile_override` theo dòng.

#### `default_action`

| Chọn | Kết quả | Adapter nào chạy |
|---|---|---|
| `INCLUDE_ALL` | mọi candidate trừ biến khớp Exclude | có rule Include ⇒ chỉ các nguồn đó; **không có rule Include ⇒ chạy tất cả** |
| `EXCLUDE_ALL` | **chỉ** candidate khớp ít nhất một Include | chỉ các nguồn có rule Include |

#### `hide_all` — khái niệm nội bộ, ⛔ không phải field

Phạm vi field của một biến = **giao** của phạm vi do *nguồn* khai (vd FVB `applies_to_field`) và
phạm vi do *rule* khai. Giao **rỗng** ⇒ `hide_all=true` (ẩn ở mọi field). Khác hẳn
`only_fields=[]` (không giới hạn) — `rules.py:208-226`.

#### `AL Variable Cross Row` — 6 cột

| Field | Ý nghĩa |
|---|---|
| `table_field` | **tên field bảng con** trên doctype mẹ (vd `items`) |
| `id_field` | field định danh dòng (mặc định tự dò `custom_slug` → `line_ref` → `*_slug` → `slug`) |
| `label_field` | field nhãn; không có thì tự dò `line_name` → `item_code` |
| `fields` | **JSON list** field được gợi ý chéo; trống = mọi field vô hướng |
| `include_index_form` | sinh thêm dạng `items[n].field` |
| `enabled` | tắt dòng mà không xoá |

### 3.2 `AL Variable Settings` (Single) + `AL Common Variable` + `AL Row Literal`

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | Desk → `AL Variable Settings`. 4 field: `default_profile`, `preview_doctype`, `common_variables`, `row_literals` |
| **Gợi ý lấy từ đâu** | `common_var` adapter đọc `common_variables`; `row_literal` adapter đọc `row_literals`. Legacy path cũng đọc 2 bảng này thay cho tuple cứng |
| **Điều kiện gì** | Dòng con phải `is_active` (thiếu field ⇒ coi như bật, `api/__init__.py:476-484`) |
| **Runtime dùng không** | **⛔ Engine không đọc.** Ngoại lệ: validate `AL Bom Set` đọc **tên** row literal (`get_row_literal_names`) để nới `known_names`; ⛔ không đọc giá trị |

| Field | Nghĩa | Ai đọc |
|---|---|---|
| `default_profile` | profile dùng khi bản ghi để trống field `variable_profile` | `_resolve_profile_doc` — **chỉ** khi doctype đã khai field Link tới `AL Variable Profile` |
| `preview_doctype` | doctype mặc định trong dialog Xem trước | JS `al_variable_profile.js:62` |
| `common_variables` | biến người dùng nhập (W_mm, H_mm, TONG_M2…) | `common_var` adapter + legacy path |
| `row_literals` | field engine inject theo dòng (unit_price, glass_thick…) | `row_literal` adapter + legacy path + `get_row_literal_names` |

> 🔴 **Thêm một dòng vào `row_literals` ⛔ KHÔNG làm engine inject biến mới.** B3 chỉ inject 6
> khoá cố định + biến phụ của `calc_pattern`. Dòng mới chỉ **hiện trong gợi ý** và **nới
> validate**. Muốn engine thật sự inject thì phải sửa B2/B3.

Danh sách seed (patch `v28_14`): 8 common var, 10 row literal (thêm `max_area_m2` chỉ để cảnh
báo `rule_input_expr` không báo oan).

### 3.3 `AL Variable Library` (+ `AL Profile System` / `AL Profile System Variable`)

**Vai trò:** từ điển biến duy nhất. `is_system=1` ⇒ resolve tự động; `is_system=0` ⇒ người dùng
nhập, có `default_value`.

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `AL Variable Library`. System var: `source_doctype` + `source_field` (+ `source_link_field` nếu cần khai tường minh). User var: `default_value` |
| **Gợi ý lấy từ đâu** | `variable_library_system` / `variable_library_user`; giá trị system var lấy qua `CatalogContext.resolve_doc_values()` — **cùng module** với engine (`system_variable_resolver`) |
| **Điều kiện gì** | `is_system` quyết định adapter; resolve system var cần tìm được bản ghi nguồn qua field Link trên doctype đang mở |
| **Runtime dùng không** | **B1** bước 1.3 (fallback, chỉ điền khi thiếu) và 1.6 (default cho user var) |

#### Chuỗi resolve một system var

```
AL Variable Library (is_system=1, source_doctype, source_field)
  → resolve_source_record_names(doctype, docname)
      · ưu tiên AL Variable Library.source_link_field (khai tường minh)
      · nếu không: field Link ĐẦU TIÊN trên doctype trỏ tới source_doctype
  → resolve_system_variable_values(source_records)
      · db.get_value(source_doctype, record, source_field)
      · rồi OVERRIDE bằng AL Profile System.system_variables (dòng is_active)
```

| Field | Dùng để |
|---|---|
| `var_name` | **tên biến trong công thức** (khoá của `inputs`) |
| `var_label` | nhãn người đọc (tooltip autocomplete, cảnh báo % mơ hồ) |
| `var_type` | kiểu; `Percent` ⇒ **luôn** chuẩn hoá % ở B1 1.7 |
| `is_system` | 1 = auto resolve / 0 = user nhập + default |
| `source_doctype` | doctype nguồn (vd `AL Profile System`, `AL Product Type`) |
| `source_field` | field trên doctype nguồn |
| `source_link_field` | **tùy chọn** — khai tay field Link trên doctype ngữ cảnh; cần khi có nhiều field Link cùng trỏ một đích |
| `default_value` | fallback khi resolve hụt / default cho user var |

`AL Profile System` và `AL Profile System Variable`:

| Field | Vai trò |
|---|---|
| `offset_frame`, `offset_glass`, `offset_fixed`, `offset_crossbar` | nguồn của `OFFSET_*` qua `source_field` |
| `system_variables` (bảng con) | **override tường minh** theo hệ nhôm; thắng giá trị resolve từ field |
| `AL Profile System Variable.is_active` | dòng tắt ⇒ **bị bỏ** (`system_variable_resolver.py:198-199`) |
| `AL Profile System.is_active` | có field nhưng resolver ⛔ không kiểm |

### 3.4 `AL Variable Set` (+ `AL Variable Set Item`)

**Vai trò:** bộ biến của một sản phẩm — nuôi **dialog "Tham số BOM"**, nơi người dùng nhập giá trị
rồi lưu vào `Quotation Item.al_bom_vars`.

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `AL Variable Set` (`set_code`, `product_type`, `is_active`) + bảng `items` (`variable`, `default_value`, `sort_order`, `is_required`) |
| **Gợi ý lấy từ đâu** | `variable_set` adapter, `source_ref = AUTO` |
| **Điều kiện gì** | `AUTO` phải **VIẾT HOA**; dò 3 nhánh bên dưới |
| **Runtime dùng không** | **⛔ Engine không đọc bảng này.** Giá trị vào runtime chỉ qua `al_bom_vars` do dialog ghi |

#### `AUTO` dò 3 nhánh (`resolve_variable_set_names`)

| Nhánh | Điều kiện | Lấy gì |
|---|---|---|
| a | doctype có field **Link → `AL Variable Set`** | giá trị field đó (vd `AL Accessory Set.variable_set`) — ⛔ không kiểm `is_active` |
| b | không có (a), có field **Link → `AL Bom Set`** | đi 1 hop: `AL Bom Set.variable_set` |
| c | **luôn chạy thêm** khi doctype có field `product_type` (Link `AL Product Type`) và field có giá trị — độc lập với (a)/(b) | `AL Variable Set` có `product_type` khớp và `is_active=1`, `order_by="modified desc"` |

> Catalog và API legacy khác nhau một điểm: adapter lấy **(a hoặc b) cộng thêm (c)** — nhánh (c)
> vẫn chạy dù đã khớp (a)/(b), nên có thể ra **nhiều bộ**; `_resolve_variable_set_name` của API
> legacy **dừng ở nhánh đầu tiên khớp**.

### 3.5 `AL Cost Bucket`

**Vai trò:** `bucket_code` **chính là một biến**. Giá trị chỉ tồn tại **sau B5**.

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `AL Cost Bucket`: `bucket_code`, `bucket_role`, `source_type`, `source_config`, `is_active` |
| **Gợi ý lấy từ đâu** | `cost_bucket` adapter — mọi bucket `is_active=1`; giá trị lấy từ `ctx.resolved` (thường `None` ⇒ hiện `—`, vì giá trị chỉ có sau khi engine chạy) |
| **Điều kiện gì** | Gợi ý: `is_active=1`. Runtime B5: **⛔ không lọc `is_active`**, chỉ lọc theo `bucket_code` của các dòng BOM |
| **Runtime dùng không** | **B5** đọc `source_type`/`source_config`; **B6** nhận giá trị qua `buckets` |

| Field | Dùng thật không |
|---|---|
| `bucket_code` | **Có** — khoá của biến và của `buckets` |
| `bucket_role` (`LEAF`/`AGGREGATE`) | **Chỉ hiển thị.** B5 có select field này nhưng ⛔ không rẽ nhánh theo nó |
| `parent_bucket` | **⛔ Không ai đọc** trong mã hiện tại |
| `source_type` | B5 chỉ xử lý `aggregate_from_items`; giá trị khác ⇒ cảnh báo + fallback cộng `line_total` |
| `source_config` | B5 dùng khi `source_type=aggregate_from_items` và config **không rỗng**; rỗng ⇒ fallback cộng Python |
| `report_group`, `sort_order` | Chỉ dùng cho gợi ý / hiển thị |

Đường B5:

```
có source_type=aggregate_from_items + source_config hợp lệ
  → binding {variable_name: bucket_code, source_type, source_config, default_value}
  → resolve_all_bindings_batch(bindings, doc=QI, pre_resolved={**inputs, "rows": [...]})
không có → buckets[bucket_code] += line_total của mọi dòng có cost_bucket đó
```

`pre_resolved["rows"]` chỉ chứa `cost_bucket` và `line_total` — `source_config.sum_field` phải trỏ
tới `line_total` (cột duy nhất có số tiền trong túi `rows`).

### 3.6 `Formula Global Variable`

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `Formula Global Variable`: `var_name`, `value_source`, `constant_value`, `is_active` |
| **Gợi ý lấy từ đâu** | `formula_global` adapter — `is_active=1`; giá trị = `constant_value` **khi** `value_source=CONSTANT` |
| **Điều kiện gì** | `is_active=1` |
| **Runtime dùng không** | **B1 bước 1.2** — ghi **mọi** record `is_active=1` vào `inputs` |

> 🔴 **B1 chỉ đọc `constant_value`.**
> `value_source = FORMULA` / `DB_QUERY` ⛔ **không được tính** ở đường AlumGlass — record vẫn được
> ghi vào `inputs` (với `constant_value` rỗng ⇒ `None`/chuỗi rỗng), rồi các bước 1.4/1.5 có thể
> ghi đè. Đừng dựa vào `formula_expr` của bảng này để tính giá.
>
> Đọc qua cache Redis, TTL **60 giây**; `frappe.db.set_value` ⛔ không xoá cache (phải chờ TTL
> hoặc gọi `invalidate_global_variable_cache()`).

### 3.7 `Formula Variable Binding`

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `Formula Variable Binding`: `variable_name`, `source_type`, `source_config`, `applies_to_doctype`, `applies_to_field`, `is_global`, `default_value`, `is_active` |
| **Gợi ý lấy từ đâu** | `fvb_scope` adapter — `get_scope_bindings_multi([doctype cha, doctype dòng con], field)` |
| **Điều kiện gì** | `is_active=1`; scope doctype khớp; `applies_to_field` là **phạm vi field của nguồn** (giao với `only_fields` của rule) |
| **Runtime dùng không** | **B1 1.4** `get_live_context` (scope `AL Bom Set` khi có Bom Set, ngược lại `Quotation Item`); **B2** binding giá (`composite_key_lookup`, `aluminum_price_composite`) |

| Field | Nghĩa chính xác |
|---|---|
| `variable_name` | **tên biến** — cũng là `source_ref` của candidate `fvb_scope` |
| `applies_to_doctype` | rỗng = **chỉ** global khi `applies_to_field` **cũng rỗng**. ⛔ Rỗng doctype + có field ⇒ binding **không áp ở đâu** (không thuộc doctype nào) — muốn lọc theo field thì phải khai doctype; muốn global thì để trống cả hai |
| `applies_to_field` | **đúng một** fieldname; rỗng = mọi field của doctype. So khớp **nguyên chuỗi** (`width` khớp `width`; `width\|height` ⛔ **không** khớp field nào). Muốn nhiều field: tạo nhiều binding, hoặc để trống rồi lọc ở client bằng `only_fields` |
| `is_global` | chỉ đổi **nhóm hiển thị** (`Bindings · FB (global)`) và `source` của candidate |
| `resolve_priority` | thứ tự resolve trong FB; B2 dùng `order_by="resolve_priority asc"` |
| `default_value` | fallback khi handler trả `None` |

> ⚠️ Scope của `fvb_scope` **⛔ không lọc theo doctype bằng `source_ref`** — `source_ref` là **tên
> biến**. Muốn giới hạn theo doctype/loại nguồn, dùng `source_type` / `name_prefix` / `name_regex`.

### 3.8 `AL Formula Field`

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `AL Formula Field`: `target_doctype`, `child_table`, `fieldname`, `id_field`, `editor_opts`, `is_active` |
| **Gợi ý lấy từ đâu** | Không sinh biến — quyết định **field nào được gắn autocomplete** khi mở form |
| **Điều kiện gì** | `is_active=1`; bộ ba `(target_doctype, child_table, fieldname)` phải **không trùng** |
| **Runtime dùng không** | **⛔ Không** — thuần client/UI |

> 🔴 **`child_table` là TÊN FIELD bảng, ⛔ không phải tên doctype con.**
> Đúng: `items`. Sai: `AL Bom Item`. Sai thì `frm.fields_dict["AL Bom Item"]` không tồn tại ⇒ JS bỏ
> qua im lặng (`formula_setup.js:315-317`).
>
> `target_doctype` là fieldname thật trong DB; `doctype` là từ khoá dành riêng của Frappe nên
> ⛔ không dùng làm fieldname.

### 3.9 `AL Slug Library`

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `AL Slug Library`: `slug`, `label`, `category`, `group_tag`, `is_active` |
| **Gợi ý lấy từ đâu** | Gián tiếp: `AL Bom Item.slug` là Link tới bảng này; `build_references` đọc **slug trên dòng** (không đọc bảng này) |
| **Điều kiện gì** | `slug` phải **duy nhất trong một Bom Set** (validate `AL Bom Set`) |
| **Runtime dùng không** | **⛔ Không.** Engine dùng giá trị `slug` trên dòng. Bảng này chỉ nuôi dropdown + `before_save` tự điền `category`/`line_name` |

---

## 4. Nhóm engine phụ trợ

### 4.1 `AL Quantity Calc Method`

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `calc_pattern_code`, `input_vars` (JSON **list** tên biến phụ), `calc_fn`, `output_unit`, `calc_formula` |
| **Lấy từ đâu** | Biến `{slug}__{tên}` lấy từ `AL Bom Item.input_vars` → user input → `row_literals` → `0` |
| **Điều kiện gì** | `calc_pattern` của dòng phải khớp `calc_pattern_code` |
| **Runtime dùng không** | **B3** đọc `input_vars` để inject biến phụ; **B4** `lookup_calc_pattern(...)`; `output_unit` lấy cho cột ĐVT kết quả |

### 4.2 `AL Calculation Rule`

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `rule_code`, `rule_type` (`CONSTANT`/`THRESHOLD`/`LOOKUP`), `constant_value`, bảng ngưỡng/tra |
| **Lấy từ đâu** | Gọi trực tiếp trong công thức: `lookup_rule('RULE-...', input)` |
| **Điều kiện gì** | Theo `rule_type`. `is_active` **có field nhưng `_lookup_rule` ⛔ không kiểm** |
| **Runtime dùng không** | **B4 + B6** (cùng một `_lookup_rule` trong `safe_funcs`); **B1** fallback `CONSTANT` khi system var chưa có giá trị (`var_name` đổi `_` → `-`) |

Mã rule sai ⇒ **ghi cảnh báo có cấu trúc** + trả `0`, BOM không chết.

### 4.3 `AL Product Type`

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `type_code`, `nc_pct`, `nc_ld_rate`, `profit_margin` |
| **Lấy từ đâu** | Là **nguồn resolve** của system var (`AL Variable Library.source_doctype = AL Product Type`) |
| **Điều kiện gì** | Doctype ngữ cảnh phải có field Link trỏ tới `AL Product Type` và field đó có giá trị |
| **Runtime dùng không** | **B1** 1.3/1.4 resolve system var (`NC_*`, `PROFIT_MARGIN`) |

Không có field `is_active`. Cũng là nguồn cho nhánh (c) của `AUTO` tìm `AL Variable Set`.

### 4.4 `AL Material Category`

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `default_scrap_pct`, `has_weight`, `default_calc_pattern`, `default_cost_bucket`, các cờ `requires_*` |
| **Lấy từ đâu** | B2 batch #4 theo `AL Bom Item.category` |
| **Điều kiện gì** | Dòng phải có `category`; `is_active` **⛔ không được kiểm** ở B2 |
| **Runtime dùng không** | **B2** `scrap_pct` + `has_weight` vào `row_literals`; **B3** nhân hao hụt vào `total_qty` **chỉ khi** `AL Bom Set.apply_scrap_pct = 1` |

`scrap_pct` lưu **phần trăm nguyên** (3 = 3%), B3 chia 100 tại công thức.

### 4.5 `AL Pricing Dimension` + `AL Variable Dimension Mapping`

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `AL Pricing Dimension`: `dimension_code`, `custom_fieldname`, `represents_color`, `is_active`. `AL Variable Dimension Mapping`: `variable_name`, `pricing_dimension`, `material_category`, `price_multiplier`, `is_active` |
| **Lấy từ đâu** | `AL Bom Version.pricing_dimension_snapshot` (chụp lúc publish); fallback query live khi snapshot rỗng |
| **Điều kiện gì** | Snapshot lọc `is_active=1`; mapping live lọc `is_active=1`; dimension live tra theo **tên**, ⛔ không lọc `is_active` |
| **Runtime dùng không** | **B2** tra giá composite — `variable_name` chính là tên biến dùng để match giá (vd màu, độ dày, xuất xứ, bề mặt) |

Đây cũng là nguồn duy nhất của cờ `is_pricing_dimension` trong catalog.

### 4.6 `AL Alert Config`

| Câu hỏi | Trả lời |
|---|---|
| **Setting ở đâu** | `alert_code`, `trigger_condition` (công thức FB), `variable_profile`, `is_active` |
| **Lấy từ đâu** | `doctype_field` + các nguồn chung (không có cross-row) |
| **Điều kiện gì** | `trigger_condition` phải qua `FormulaValidator` khi lưu (dùng universe đầy đủ) |
| **Runtime dùng không** | **⛔ Chưa có engine nào đọc `AL Alert Config`** — hiện chỉ có validate công thức |

> Đừng kỳ vọng cấu hình cảnh báo đã có tác dụng. Theo mã hiện tại, bảng này là **khai báo trước**.

---

## 5. Bảng "nguồn biến → điều kiện"

> ℹ️ Bảng này là **bản tra theo nguồn**. Luồng chi tiết từng bước nằm ở
> [tu-goi-y-den-runtime.md](tu-goi-y-den-runtime.md) §5 — khi sửa một trong hai, đối chiếu bản kia.

10 adapter đăng ký qua decorator (`registry.py:20`), cộng `slug_reference` (⛔ **không phải**
adapter — nó điều khiển `references`).

| `source_kind` | Hàm adapter | Đọc bảng | Lọc gì | `has_value` khi | Giá trị hiển thị lấy ở đâu | `order` |
|---|---|---|---|---|---|---|
| `fvb_scope` | `fvb_scope` | `Formula Variable Binding` | `is_active=1`, scope doctype cha + dòng con, `applies_to_field` | sau khi fallback `default_value`, giá trị khác `None` | resolve binding trên doc/dòng; fallback `default_value` | 10 |
| `cost_bucket` | `cost_bucket` | `AL Cost Bucket` | `is_active=1` | `ctx.resolved` có mã bucket | `CatalogContext.resolved` (thường `None` ⇒ `—`) | 20 |
| `variable_library_system` | `variable_library_system` | `AL Variable Library` | `is_system=1` | resolve được hoặc có `default_value` | resolved từ doc hiện tại; nếu không ⇒ `default_value` | 30 |
| `variable_library_user` | `variable_library_user` | `AL Variable Library` | `is_system=0` | **luôn `False`** (⛔ không resolve) | `—` — giá trị do người dùng nhập | 40 |
| `variable_set` | `variable_set` | `AL Variable Set` + `items` | `source_ref` tường minh + 3 nhánh AUTO; nhánh (c) lọc `is_active=1` | `ctx.resolved` có `var_name` | resolved từ doc hiện tại | 45 |
| `cost_template_line` | `cost_template_line` | `AL Cost Template.items` | chỉ dòng **trước** `row_index` (khi có) | **luôn `False`** | `—` — chỉ có sau B6 | 50 |
| `formula_global` | `formula_global` | `Formula Global Variable` | `is_active=1` | `value_source=CONSTANT` | `constant_value` | 55 |
| `row_literal` | `row_literal` | `AL Variable Settings.row_literals` | dòng `is_active` | giá trị đọc từ dòng/doc khác `None` | dòng hiện tại (hoặc doc) | 60 |
| `common_var` | `common_var` | `AL Variable Settings.common_variables` | dòng `is_active` | `ctx.resolved` có biến | resolved từ doc hiện tại | 70 |
| `doctype_field` | `doctype_field` | meta của doctype cha / doctype dòng | field vô hướng (bỏ layout, Table, JSON, Small Text) | giá trị khác `None` | field của doc / dòng hiện tại | 80 |
| `slug_reference` | **không có** | `AL Variable Cross Row` hoặc meta child table | xem `build_references` | — | chỉ sinh `references` (không có `value`) | — |

Ghi chú đọc bảng:

- `has_value` **quyết định dedupe**: nguồn có giá trị thắng nguồn rỗng cùng tên (`rules.py:372-379`).
- `variable_library_user` và `cost_template_line` **luôn** `has_value=False` ở mặt phẳng gợi ý —
  đây là chủ ý, ⛔ không phải lỗi.
- `doctype_field` loại **Small Text**: trên `AL Bom Item`, `width/height/qty` là Small Text chứa
  **công thức**, gợi ý chúng như biến số sẽ sai nghĩa (`context.py:184-208`).

### `source_ref` — nghĩa khác nhau theo từng nguồn

| `source_kind` | `source_ref` là gì | Ghi chú |
|---|---|---|
| `fvb_scope` | **tên biến** | ⛔ **không phải** doctype; scope doctype do adapter tự lấy |
| `slug_reference` | **tên bảng con** (vd `items`) | `*` / `AUTO` ⛔ **không** sinh references — rule rơi về nhánh `default_action` |
| `variable_set` | `set_code` hoặc `AUTO` | `AUTO` phải **VIẾT HOA** |
| `cost_template_line` | `line_code` hoặc `AUTO` | `AUTO` = mọi dòng (đã cắt theo `row_index` nếu có) |
| `cost_bucket` | `bucket_code` | |
| `variable_library_system` / `variable_library_user` | `var_name` | |
| `formula_global` | `var_name` | |
| `row_literal` / `common_var` | `var_name` | |
| `doctype_field` | `fieldname` | |

Ở mọi nguồn trừ `slug_reference`: `*`, chuỗi rỗng và `AUTO` đều nghĩa là **không lọc thêm** —
tập candidate vẫn đúng bằng những gì adapter của ngữ cảnh sinh ra. Riêng `variable_set`, tập đó là
**set gắn với bản ghi** (nhánh a/b/c dưới đây), ⛔ **không** phải quét cả bảng.

### Cache phía client

| Cache | TTL | Khoá | Chỗ khai |
|---|---|---|---|
| Danh sách biến (`alumglass.FormulaContext`) | **300 000 ms = 5 phút** | `doctype::docname::childTable` | `formula_setup.js:28` |
| Registry `AL Formula Field` (`alumglass.FormulaFields`) | **60 000 ms = 60 giây** | `doctype` | `formula_setup.js:241` |

Sửa profile/rule xong mà form chưa đổi ⇒ còn trong 5 phút. Sửa `AL Formula Field` ⇒ tối đa 60 giây.

### Dedupe khi trùng tên

| Ưu tiên | Tiêu chí |
|---|---|
| 1 | `has_value = True` thắng `False` |
| 2 | `sort_order` nhỏ hơn |
| 3 | `adapter_order` nhỏ hơn (adapter đăng ký trước) |
| 4 | thứ tự xuất hiện |

Phạm vi field sau dedupe = **hợp** phạm vi của mọi nguồn cùng tên (`_merge_entry_field_scopes`).
Mọi lần loại đều ghi vào `meta.duplicates` — ⛔ không bỏ im lặng.

### `build_references` — 4 nhánh quyết định

| Thứ tự | Điều kiện | Kết quả |
|---|---|---|
| 1 | Có `cross_row` (và `enabled`) | đúng cấu hình; giao với rule Include `slug_reference` nếu có |
| 2 | Không có `cross_row`, **có** rule Include `slug_reference` | chỉ các bảng được rule trỏ tới |
| 3 | Không có cả hai + `default_action=INCLUDE_ALL` | **mọi** child table (hành vi cũ) |
| 4 | `EXCLUDE_ALL` và không khai gì | ⛔ không gợi ý chéo dòng |

Rule Exclude `slug_reference` **luôn** loại bảng tương ứng ở mọi nhánh.

> 🔴 Bảng trên **chỉ chạy khi profile resolve được** (`meta.profile_code` có giá trị). Nếu bản ghi
> chưa có profile (record mới, field trống + `default_profile` trống, profile tắt) thì hệ thống đi
> đường **legacy** và **luôn** thêm `items.<slug>.{field}` từ `AL Slug Library` — danh sách slug
> toàn cục, ⛔ không liên quan rule `slug_reference`. Đây là lý do phổ biến nhất khiến "bỏ
> `slug_reference` mà vẫn thấy `items.*`"; xem [al-variable-profile.md](al-variable-profile.md) §7.2.1.

---

## 6. Runtime chi tiết B0–B7

> ℹ️ Đây là **bản tra theo bước** (đọc bảng nào, ghi biến nào). Bản kể đầy đủ có ví dụ và chỗ đứt
> gãy là [tu-goi-y-den-runtime.md](tu-goi-y-den-runtime.md) §10; sửa bước nào thì cập nhật cả hai.

Hàm chạy tuần tự trong `BomOrchestrator.run()` (`bom_orchestrator.py:301-310`). Không bước nào
đọc `AL Variable Profile`.

### B0 — Version pinning · `b0_version_pinning()`

| | |
|---|---|
| **Đầu vào** | `Quotation Item.al_bom_version` hoặc `al_bom` |
| **Biến ghi/đọc** | không ghi biến nào |
| **Điều kiện** | có `al_bom_version` ⇒ dùng; không ⇒ lấy `AL BOM.current_version`; vẫn không ⇒ version **mới nhất theo `creation DESC`** |
| **Thiếu thì sao** | ⛔ không có version nào ⇒ `frappe.throw` "chưa có phiên bản nào" |

**Quan trọng:** `bom_set_snapshot` và `cost_template_snapshot` được **chốt lúc tạo version**.
`AL Bom Item.is_active` được lọc **đúng lúc đó** (`al_bom_version.py:120-122`) — tắt dòng sau khi
publish ⛔ không bỏ dòng khỏi lần tính.

### B1 — Gom inputs · `b1_gather_inputs()`

Đây là bước quan trọng nhất. **Thứ tự GHI** dưới đây là thứ tự thật trong mã; lớp ghi sau thắng
lớp ghi trước (trừ các lớp "chỉ điền khi thiếu").

| Thứ tự | Mã | Lớp | Ghi gì | Điều kiện |
|---|---|---|---|---|
| 1.1 | `:383-397` | `al_bom_vars.extra_vars` | `inputs[var] = value` | JSON trên `Quotation Item`; ghi sớm rồi **áp lại** ở 1.5 |
| 1.2 | `:399-413` | `Formula Global Variable` | `inputs[gv.var_name] = constant_value` | `is_active=1`; ép `float` được thì ép |
| 1.4 | `:415-424` | FB `get_live_context` | mọi cặp scalar | scope `AL Bom Set` nếu có Bom Set, ngược lại `Quotation Item`. **Bỏ** `None`, dict/list, chuỗi rỗng |
| 1.3 | `:426-432` | `AL Variable Library` (system) | `inputs.update(resolved)` | **chỉ biến chưa có trong `inputs`** (`fill_missing_only=True`) + fallback `default_value` + fallback `AL Calculation Rule` CONSTANT |
| 1.4b | `:434-439` | `AL Profile System.system_variables` | `inputs[var] = value` | dòng `is_active`, `value` khác rỗng |
| 1.5 | `:441-453` | `al_bom_vars` (top-level + `extra_vars`) | `inputs[var] = value` | mọi key trừ `extra_vars`, `accessory_set`, `glass_master` |
| 1.5b | `:455-486` | override config | `accessory_set_code`, `glass_master(_map)`, `color(_map)`, `profile_system_override`, `cost_template_override` | key có mặt trong `al_bom_vars` (opt-in) |
| 1.5c | `:488-506` | resolve **lại** system var | ghi đè toàn bộ | **chỉ khi** có `_profile_system` override; snapshot giá trị user rồi **áp lại** ngay sau |
| 1.6 | `:508-512` | user var default | `inputs[var] = default_value` | `is_system=0`, biến chưa có trong `inputs`, `default_value` khác rỗng |
| 1.7 | `:514-519` | chuẩn hoá % | `inputs[var] = val / 100` | biến `var_type=Percent` **hoặc** hậu tố `_PCT`/`_MARGIN`/`_RATE`; `abs(val) > 1`; `val` là số |

Ba chi tiết dễ hiểu sai:

1. **1.4 chạy TRƯỚC 1.3** (dù số thứ tự ngược). Đây là "Phase 3a FLIP" — FB là nguồn chính, 1.3
   chỉ lấp chỗ trống.
2. **1.5c có thể đè biến người dùng vừa sửa**; vì vậy mã snapshot `_user_provided` trước rồi áp
   lại ngay sau `_resolve_system_variables()`. Hợp đồng: **user input luôn thắng profile**.
3. **1.7 chạy SAU CÙNG** nên cover mọi nguồn resolve. Giá trị đúng bằng `1` là ca mơ hồ ⇒ **giữ
   nguyên** + ghi cảnh báo (1% hay 100%).

### B2 — Prefetch master data · `b2_prefetch_master_data()`

| | |
|---|---|
| **Đầu vào** | `bom_version.bom_set_snapshot`; `AL Bom Set` **live** (qua `_get_bom_set`) |
| **Biến ghi** | `self.row_literals[slug]`, `self._glass_data[slug]`, `self._formula_fieldnames`, `self._glass_categories` |
| **Lỗi/thiếu** | snapshot rỗng ⇒ `throw` "BOM Version không có snapshot"; thiếu giá ⇒ literal `0` + cảnh báo |

Việc theo thứ tự:

| # | Việc | Đọc từ | Điều kiện |
|---|---|---|---|
| 1 | nạp phụ kiện | `AL Accessory Set` (theo `accessory_set` override → `Bom Set.default_accessory_set`) | có mã bộ |
| 2 | gom `item_code`, `price_base_item`, `default_glass_master`, rule | snapshot | |
| 3 | batch #1 weight | `Item.weight_per_unit` | |
| 4 | batch #2 giá | FB binding giá → fallback `Item Price` theo composite key | |
| 5 | batch #3 kính | `AL Glass Master` (`total_thick_mm`, `glass_type`, `max_area_m2`) | |
| 6 | batch #4 nhóm vật tư | `AL Material Category` (`default_scrap_pct`, `has_weight`) | |
| 7 | batch #5 rule động | `AL Dynamic Item Rule` theo **từng dòng** (cache theo `(rule_code, rule_input)`) | mode `Rule` |
| 8 | batch #6 weight/giá mã đã resolve | `Item`, `Item Price` | ⛔ không ghi đè mã đã có giá ở batch #2 |
| 9 | dựng `row_literals` | các kết quả trên | |
| 10 | đọc `formula_fieldnames` | `AL Bom Set` (live) | JSON hợp lệ |

`row_literals[slug]` gồm: `weight_per_unit`, `unit_price`, `calc_pattern`, `glass_thick`,
`glass_type`, `item_code`, `scrap_pct`, `has_weight`, `color`, `supplier_location`,
`install_position`, `cut_angle`, `note`.

> ⚠️ B2 đọc **`AL Bom Set` live** cho `default_accessory_set`, `formula_fieldnames`,
> `apply_scrap_pct`, `profile_system` — không lấy từ snapshot. Sửa mấy field này **có** tác dụng
> ngay lần tính kế tiếp, khác với sửa `items` (đã đóng băng trong snapshot).

### B3 — Dựng danh sách công thức · `b3_build_formulas()`

| | |
|---|---|
| **Đầu vào** | `self.bom_items`, `self.row_literals`, `self.inputs` |
| **Biến ghi** | `{slug}__*` (mục 2.1), `inputs["items"]` |
| **Lỗi/thiếu** | đặt sẵn `0` cho 7 field để công thức không `NameError` |

Trình tự mỗi dòng: inject 6 literal → đặt default 0 → resolve biến phụ `calc_pattern` → build
formula cho từng field trong `formula_fieldnames` → build 3 synthetic.

**Cross-row được xử lý ở đây:** mọi `items.X.Y` trong công thức đi qua `_normalize_items_ref`
(`:2181-2212`) để thành `X__Y` **trước khi** vào danh sách formula.

### B4 — Tính dòng vật tư · `b4_calculate_bom_items()`

| | |
|---|---|
| **Đầu vào** | `bom_formulas` + `inputs` |
| **Cơ chế** | `FormulaEngine(... on_error="default", default_value=0, deterministic=True)`, cache theo **nội dung công thức** |
| **Biến đọc** | mọi `{slug}__*` theo DAG (topo sort tự động) |
| **Biến ghi** | `self.inputs.update(result)`; `self.bom_result` từng dòng |
| **Lỗi** | `engine.last_errors` → `self.bom_engine_errors`; **đột biến/thừa hưởng lỗi một dòng ⛔ không làm chết cả BOM** |

Giá trị 0 khi thiếu biến: `on_error="default", default_value=0` + default đặt sẵn ở B3. Cảnh báo
phát sinh trong lúc tính (`lookup_rule` thiếu mã…) được hút về túi lỗi ngay sau `calculate`.
Validate bổ sung: diện tích kính > `max_area_m2` ⇒ **cảnh báo**, ⛔ không throw.

### B5 — Gom bucket · `b5_aggregate_cost_buckets()`

| | |
|---|---|
| **Đầu vào** | `bom_result[].cost_bucket`, `bom_result[].line_total` |
| **Biến ghi** | `self.buckets` |
| **Điều kiện** | bucket có `source_type=aggregate_from_items` **và** `source_config` không rỗng ⇒ resolve qua FB; ngược lại cộng Python |
| **Thiếu** | dòng không có `cost_bucket` ⇒ bị bỏ qua; bucket chưa có giá trị ⇒ **không có khoá** trong `buckets` |

`is_active` của `AL Cost Bucket` **⛔ không được kiểm** ở bước này.

### B6 — Tính cost template · `b6_calculate_cost_template()`

| | |
|---|---|
| **Đầu vào** | `bom_version.cost_template_snapshot` (hoặc `AL Cost Template` live khi `_cost_template` override) |
| **Context** | `extra_context = inputs ⊕ buckets`; thêm `0.0` cho mã được công thức tham chiếu; gọi `engine.calculate({**extra_context, **self.inputs})` |
| **Biến ghi** | `self.cost_result`, `self.gia_vat`, `self.cost_template_trace` |
| **Lỗi** | `engine.last_errors` → `self.cost_engine_errors` |
| **Thiếu** | biến không có ⇒ `0` theo `on_error="default"` + ghi lỗi có cấu trúc |

Redis/không: engine được cache theo nội dung `global_formulas`. Trace build **tại lúc tính** với
context đầy đủ.

### B7 — Ghi kết quả · `b7_save_results()`

| | |
|---|---|
| **Ghi vào `Quotation Item`** | `al_gia_vat`, `al_gia_ban`, `al_bom_result`, `rate` |
| **Nội dung `al_bom_result`** | `buckets`, `cost_template`, `cost_template_trace`, `lines`, `gia_vat`, `gia_ban`, `errors.{bom_items, cost_template}` |
| **Chốt an toàn** | `assert_quotation_item_editable` sát lệnh ghi — báo giá đã submit/huỷ ⇒ `throw` |
| **Tổng tiền** | tính lại Quotation cha, ghi bằng `set_value(update_modified=False)`, **⛔ không save cha** |
| **Commit** | **một** commit duy nhất |

---

## 7. Ba cầu nối gợi ý ↔ runtime

### (a) Profile ⛔ không vào runtime; validate dùng universe đầy đủ

| Khẳng định | Chỗ kiểm |
|---|---|
| `bom_orchestrator.py` ⛔ không đọc `variable_profile` / `AL Variable Profile` | grep toàn `alumglass/engine/` |
| Validate `AL Cost Template` gọi `get_formula_context(..., include_all_sources=True)` | `al_cost_template.py:81-88` |
| Validate `AL Bom Set` / `AL Accessory Set` / `AL Alert Config` dùng `build_known_names` → cũng `include_all_sources=True` | `formula_validate.py:70-79` |
| Client tách hẳn 2 cache: `fetchContext` (gợi ý) và `fetchValidationContext` (`include_all_sources: 1`) | `cost_template.js:196-256` |

Hệ quả: bật profile **không** làm công thức cũ bị chặn oan; nhưng cũng **không** ngăn được người
dùng gõ biến ngoài profile.

### (b) Cùng tên biến, khác nguồn ở hai mặt phẳng

Một tên biến có thể đến từ nhiều nguồn. **Dedupe chỉ tồn tại ở mặt phẳng gợi ý** — runtime là
"lớp ghi sau thắng" của B1, không phải dedupe của catalog.

| Tình huống | Gợi ý hiển thị | Runtime dùng |
|---|---|---|
| `unit_price` vừa là row literal vừa là field của `AL Accessory Item` | một biến, nguồn thắng theo dedupe (có giá trị thắng) | `lit["unit_price"]` của B2 (giá tra được, hoặc `AL Accessory Item.unit_price` nếu > 0) |
| `NC_SX_PCT` vừa là `Formula Global Variable` vừa là system var | phụ thuộc `has_value` + `adapter_order` | **1.2 Global ghi trước**, rồi 1.4 FB, rồi 1.3 (chỉ điền thiếu) — nếu 1.2 có giá trị thì 1.3 **không** ghi đè |
| Bucket `VL_NHOM` vừa là `cost_bucket` vừa là dòng cost template | `cost_bucket` order 20 thắng `cost_template_line` order 50 khi hoà | B5 ghi `buckets`, B6 đọc `buckets`; nếu trùng tên với input thì **input thắng** ở lớp trải cuối |

Khi nghi một biến "hiện một đằng, tính một nẻo": gọi `explain_variable` để thấy **mọi** nguồn cùng
tên + nguồn đang thắng.

### (c) Cross-row `items.<slug>.<field>` được normalize thế nào

| Dạng người dùng gõ | B3 làm gì | Kết quả runtime |
|---|---|---|
| `items.kinh_tren.width` | `_normalize_items_ref` → `normalize_global` → **`kinh_tren__width`** | DAG tính `kinh_tren__width` trước (nếu có công thức), rồi dùng giá trị |
| `items.kinh_tren.<field>` với field **không** được B3 inject | chuỗi vẫn được normalize | `kinh_tren__<field>` không tồn tại ⇒ `0` + lỗi engine có cấu trúc |
| `items.tên_sai.width` | vẫn normalize | `tên_sai__width` không tồn tại ⇒ `0` |
| `items[0].width` (dạng index) | **⛔ không khớp** — `_normalize_items_ref` thoát sớm vì chuỗi không chứa `items.`; regex `normalize_global` chỉ khớp **3 đoạn** cách nhau bằng dấu chấm | Không lấy được dòng: `inputs["items"]` là **dict theo slug**, ⛔ không phải list ⇒ `0` |

Thêm hai điểm:

1. **`items[n]` còn bị validate chặn.** FormulaValidator chỉ cho `.get/.keys/.values/.items/.to_dict`
   (`formula_builder/formula_utils/security.py:41-47`); `.width` không nằm trong danh sách ⇒ lỗi
   "Attribute access '.width' is not allowed". Nghĩa là gợi ý dạng index **có mà dùng không được**
   trên `AL Bom Set` / `AL Accessory Set`.
2. **Field engine không inject thì ra 0**, kể cả khi validate đã cho qua nhờ superset
   (`FORMULA_FIELDS` ∪ `ENGINE_SYNTHETIC_FIELDS` ∪ row literal đang bật).

---

## 8. Bốn ví dụ: setting ở đâu → lấy từ đâu → điều kiện gì

### 8.1 `VL_NHOM` — bucket, giá trị chỉ có sau B5

| | |
|---|---|
| **Record cấu hình** | `AL Cost Bucket` có `bucket_code = VL_NHOM`, `bucket_name = Vật liệu nhôm`, `bucket_role = LEAF`, `is_active = 1` |
| **Field quyết định** | `bucket_code` (tên biến), `source_type`, `source_config`, `is_active` |
| **Điều kiện lọc** | Gợi ý: `is_active = 1`. Runtime: dòng BOM phải có `cost_bucket = VL_NHOM` |
| **Giá trị lúc gợi ý** | `—` (adapter lấy `ctx.resolved.get("VL_NHOM")`, gần như luôn `None`) |
| **Giá trị lúc runtime** | B5: nếu có `source_type=aggregate_from_items` + `source_config` ⇒ resolve qua FB; ngược lại `Σ line_total` của các dòng bucket này |
| **Vì sao lệch** | Gợi ý chạy trên **chứng từ nháp**, chưa có B4/B5. Runtime có giá trị thật, phụ thuộc giá tra được ở B2 |
| **Bẫy** | Đổi `is_active = 0` **không** làm bucket ngừng tính ở B5 — chỉ biến mất khỏi gợi ý |

### 8.2 `unit_price` — row literal ở gợi ý, giá tra được ở runtime

| | |
|---|---|
| **Record cấu hình** | `AL Variable Settings.row_literals` có dòng `var_name = unit_price`, `var_type = Float`, `is_active = 1` |
| **Field quyết định** | `var_name` (tên biến), `is_active` (dòng) |
| **Điều kiện lọc** | Dòng phải `is_active`; gợi ý chỉ hiện khi rule của profile Include `row_literal` (hoặc `only_fields` cho phép field đang sửa) |
| **Giá trị lúc gợi ý** | Adapter đọc field cùng tên trên **dòng hiện tại**. Trên `AL Bom Set`, `AL Bom Item` **không có** field `unit_price` ⇒ `—`. Trên `AL Accessory Set`, `AL Accessory Item` **có** `unit_price` ⇒ hiện đúng số |
| **Giá trị lúc runtime** | `row_literals[slug]["unit_price"]` từ B2: `Item Price` theo `price_base_item`/`item_code` + composite key (màu/độ dày/xuất xứ/bề mặt). Dòng phụ kiện có `unit_price > 0` thì **ghi đè** |
| **Vì sao lệch** | Gợi ý `—` vì doc nháp chưa có giá; runtime phụ thuộc bảng giá, tiền tệ, hiệu lực, và `price_base_item` có khai hay không |
| **Bẫy** | Thêm dòng `unit_price` mới vào Settings ⛔ không đổi runtime — B3 đã inject `unit_price` theo danh sách cứng |

### 8.3 `NC_PCT` — system var + chuẩn hoá phần trăm

> **Tên biến:** tài liệu ví dụ dùng `NC_PCT`. Bản seed trong mã dùng `NC_SX_PCT` / `NC_LD_PCT` /
> `PROFIT_MARGIN` / `VAT_RATE` (`seed_demo_data.py:232-237`). Cơ chế **giống hệt**; dưới đây gọi
> chung là biến phần trăm system.

| | |
|---|---|
| **Record cấu hình** | `AL Variable Library`: `var_name = NC_PCT` (hoặc `NC_SX_PCT`), `is_system = 1`, `source_doctype = AL Product Type`, `source_field = nc_pct`, `default_value = "5"` (Data), `var_type = Float` (hoặc `Percent`) |
| **Field quyết định** | `is_system`, `source_doctype`, `source_field`, `source_link_field` (tùy chọn), `default_value`, `var_type` |
| **Điều kiện lọc** | `is_system=1`; doctype ngữ cảnh phải có field Link trỏ `AL Product Type` và field đó có giá trị |
| **Giá trị lúc gợi ý** | **Số nguyên thô**: resolve được ⇒ `AL Product Type.nc_pct` (vd `8`); resolve hụt ⇒ `default_value` (vd `5`). ⛔ Chưa chia 100 |
| **Giá trị lúc runtime** | B1 1.4 (FB) hoặc 1.3 (fallback, cùng chuỗi resolve + `default_value`) lấy `8` hoặc `5`, rồi **1.7 chia 100 ⇒ `0.08` / `0.05`** trước khi vào công thức |
| **Vì sao lệch** | Lệch đúng **100 lần**. Nhìn gợi ý thấy `8` rồi tự nhân trong công thức là sai; engine đã chia sẵn |
| **Bẫy** | Giá trị đúng bằng `1` ⇒ hệ thống hiểu là **100%** và ghi cảnh báo (muốn 1% thì nhập `0.01`) |

### 8.4 `items.kinh_tren.width` — cross-row

| | |
|---|---|
| **Record cấu hình** | `AL Variable Profile.cross_row`: `table_field = items`, `id_field = slug`, `label_field = line_name`, `fields = ["width","height","qty","glass_thick","glass_type","unit_price","line_total"]`, `include_index_form = 1` |
| **Field quyết định** | `table_field`, `id_field`, `fields`, `enabled` |
| **Điều kiện lọc** | Profile phải được gán cho `AL Bom Set`; dòng `cross_row.enabled`; rule Exclude `slug_reference` có thể loại cả bảng |
| **Giá trị lúc gợi ý** | **Không có giá trị** — reference chỉ có `name`, `label`, `insert`. Nhãn: "Chiều rộng — kính trên" |
| **Giá trị lúc runtime** | B3 đổi thành `kinh_tren__width`; FormulaEngine tính theo DAG (dòng `kinh_tren` phải có công thức `width`, nếu không thì nhận default `0`), rồi dùng giá trị |
| **Vì sao lệch** | Gợi ý chỉ là **tên**, không phải số. Sai slug / sai field / dòng bị tắt lúc publish ⇒ `0` |
| **Bẫy** | `cross_row.fields` khai field mà B3 ⛔ không inject: `max_area_m2` (row literal đang bật) ⇒ **validate cho qua nhưng runtime ra `0`**; `has_weight`, `color` (không thuộc superset) ⇒ **chặn lưu** |

---

## 9. Bảng tra nhanh "biến này từ đâu ra?"

| Tên biến (ví dụ) | Nguồn | Bảng cấu hình | Bước runtime |
|---|---|---|---|
| `VL_NHOM`, `VL_KINH`, `TONG_VL`, `GIA_VAT`… | `cost_bucket` | `AL Cost Bucket` | B5 (LEAF) → B6 (đọc qua `buckets`) |
| `OFFSET_FRAME`, `OFFSET_DO_NGANG` | `variable_library_system` | `AL Variable Library` + `AL Profile System.offset_*` | B1 1.3/1.4 |
| `NC_SX_PCT`, `NC_LD_PCT`, `PROFIT_MARGIN` | `variable_library_system` | `AL Variable Library` + `AL Product Type` | B1 1.3/1.4 → 1.7 (÷100) |
| `VAT_RATE`, `OH_VC_PCT` | `variable_library_system` hoặc `formula_global` | `AL Variable Library` / `Formula Global Variable` | B1 1.2/1.3 → 1.7 (÷100) |
| `W_mm`, `H_mm`, `n_panel`, `TONG_M2` | `common_var` | `AL Variable Settings.common_variables` + `Quotation Item.al_bom_vars` | B1 1.5 (user nhập) |
| `unit_price`, `glass_thick`, `glass_type`, `scrap_pct`, `calc_pattern` | `row_literal` | `AL Variable Settings.row_literals` (tên) + B2 (giá trị) | B3 inject `{slug}__*` |
| `weight_per_unit` | `row_literal` | `Item.weight_per_unit` | B2 batch #1 → B3 |
| `{slug}__width`, `__height`, `__qty` | field công thức của dòng | `AL Bom Set.items[].width/height/qty` | B3 → B4 |
| `{slug}__unit_qty`, `__total_qty`, `__line_total` | synthetic engine | hợp đồng engine, ⛔ không phải cấu hình | B3 → B4 |
| `items.<slug>.<field>` | `slug_reference` | `AL Variable Profile.cross_row` | B3 (`_normalize_items_ref`) → B4 |
| `{slug}__{biến phụ}` | `input_vars` của pattern | `AL Quantity Calc Method.input_vars` + `AL Bom Item.input_vars` | B3 → B4 |
| `line_code` của template | `cost_template_line` | `AL Cost Template.items` | B6 (chỉ gợi ý; giá trị do chính dòng đó tính) |
| biến binding (`OFFSET_*` nếu đã seed FVB) | `fvb_scope` | `Formula Variable Binding` | B1 1.4 (`get_live_context`) |
| `customer`, `description`… | `doctype_field` | meta của doctype | ⛔ không có ở runtime (chỉ gợi ý), trừ khi cũng là input |
| `RULE-...` (mã rule) | — | `AL Calculation Rule` | B4/B6 qua `lookup_rule()` |

---

## 10. Đọc tiếp

- Cách bấm và setting trên form: [huong-dan-setting-bien.md](huong-dan-setting-bien.md)
- Ví dụ setting đầy đủ 13 cột + cách tắt/chỉ hiện biến: [vi-du-setting-day-du.md](vi-du-setting-day-du.md)
- Ví dụ A→Z có số liệu: [vi-du-a-z.md](vi-du-a-z.md)
- Đi từ gõ gợi ý đến ra giá trị: [tu-goi-y-den-runtime.md](tu-goi-y-den-runtime.md)
- Shape API và tham số: [api-reference.md](api-reference.md)
- Triệu chứng và cách chẩn đoán: [troubleshooting.md](troubleshooting.md)
- Thay đổi của bản vá v28_14: [CHANGELOG-v28_14.md](CHANGELOG-v28_14.md)
- Tổng quan bộ tài liệu: [README.md](README.md)
