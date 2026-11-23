# Tài liệu tính giá thành AlumGlass × Formula Builder

*Nguồn: github.com/lengoc1490/AlumGlass (HEAD `eb22946`) và github.com/lengoc1490/Formula-Builder (HEAD `6b3e5b4`), đọc ngày 24/10/2026. Phương pháp: đọc mã nguồn, đối chiếu với tài liệu có sẵn trong repo, rồi tự tính lại hai ví dụ bằng một script Python độc lập từ công thức và giá trong `seed_demo_data.py`. Chưa chạy trên site Frappe thật.*

## 0. Tóm tắt và các điểm cần đính chính

Tính giá một dòng báo giá gồm 8 bước B0→B7 do `BomOrchestrator` điều phối (`alumglass/engine/bom_orchestrator.py`). Engine không chứa nghiệp vụ cửa nhôm kính: hình học, số lượng, giá, hệ số đều nằm trong DB. Engine chỉ dựng chuỗi công thức rồi giao cho `FormulaEngine` của Formula Builder tính theo đồ thị phụ thuộc (DAG).

**Kết quả kiểm chứng.** Ví dụ 2C ra 22.717.299 đ (golden ghi 22.717.289 đ, lệch 10 đ do người ghi golden làm tròn từng bước; test chấp nhận lệch dưới 1.000 đ). Ví dụ 4C ra 47.430.808 đ, khớp golden đến từng đồng.

**Bảy điểm tài liệu cũ trong repo (`docs/huong-dan-tinh-gia-full-flow.md`) nói chưa đúng hoặc chưa nói:**

| # | Điểm | Thực tế trong mã |
| --- | --- | --- |
| 1 | `DON_GIA_M2` | Seed dùng `safe_div(GIA_BAN, TONG_M2, 0)` (patch `v28_13`), không phải phép chia trần như §11.2 mục 4 của tài liệu cũ. |
| 2 | Bản vá cache engine | Tài liệu cũ ghi "chưa commit". HEAD hiện tại đã có `engine/engine_cache.py`, B4 và B6 đã dùng cache. |
| 3 | Biên rule THRESHOLD | Quy ước nửa mở \[from, to), thêm lưới "bằng đúng biên trên vẫn khớp". Khe hở giữa hai dải (vd 10 → 10.1) trả `None`, `lookup_rule` đổi thành 0 nên NC\_LD = 0 mà không báo lỗi. |
| 4 | Item chỉ có 1 dòng giá | `best_partial_match` trả thẳng dòng đó, không kiểm tra dimension có khớp hay không. |
| 5 | Dòng chọn mã bằng Rule (nẹp, keo) | Giá lấy thô ở batch #6 theo mã đã resolve, bỏ qua composite key và bỏ qua `multiplier_chain`. |
| 6 | `price_type` trên AL Bom Item | Engine không đọc. Giá luôn tra theo `price_base_item`, nếu trống thì theo `item_code`. |
| 7 | Thứ tự dòng Cost Template | B6 sắp theo DAG nên thứ tự dòng vô hại. Nhưng nút Preview (`preview_cost_template`) chạy tuần tự theo thứ tự dòng. |

## 1. Bức tranh tổng thể

```
Quotation Item: al_bom, al_bom_version, al_bom_vars (JSON)
   │
   ▼  alumglass.api.calculate_bom(quotation_item_name)
   │   ≤ ASYNC_BOM_THRESHOLD (mặc định 150 dòng BOM): chạy đồng bộ
   │   >  ngưỡng: job nền (queue long, timeout 600 s)
   ▼
BomOrchestrator.run()
   B0 chốt AL BOM Version (snapshot bất biến)
   B1 gom biến đầu vào (user + hệ thống + hằng số)
   B2 nạp master data, TRA GIÁ composite key, giải Rule chọn mã
   B3 dựng danh sách công thức {slug}__{field}
   B4 tính dòng vật tư          ← FormulaEngine #1 (DAG)
   B5 gom line_total theo cost bucket
   B6 chạy Cost Template        ← FormulaEngine #2 (DAG)
   B7 ghi kết quả, 1 commit
   ▼
Quotation Item: al_gia_vat, al_gia_ban, al_bom_result, rate
Quotation (cha): 13 trường tổng tiền được tính lại
```

Ba nguyên tắc cần nhớ:

1. **Công thức nằm trong DB.** `width`, `height`, `qty` của mỗi dòng BOM là chuỗi công thức (vd `W_mm - 2*OFFSET_FRAME`), không phải số cứng.
2. **Giá không nằm trong công thức.** Giá được tra ở B2 rồi nhét vào context dưới dạng biến `{slug}__unit_price`.
3. **Bất biến nhờ snapshot.** Hình học, cost template và định nghĩa pricing dimension đều lấy từ ba snapshot của `AL BOM Version` đang ghim. Sửa Bom Set hôm nay không làm đổi giá báo giá đã tính. Ngoại lệ: các override `_cost_template`, `_profile_system`, `_accessory_set` trong `al_bom_vars` đọc doc sống.

- ## 2. Các DocType liên quan

**Đầu vào / đầu ra**

| DocType | Nội dung | Bước dùng |
| --- | --- | --- |
| Quotation Item (custom field) | `al_bom`, `al_bom_version`, `al_bom_vars` (JSON biến nhập + override); ghi ra `al_gia_ban` (trước VAT), `al_gia_vat` (có VAT), `al_bom_result` (JSON), `al_calc_status`, `rate` | B0, B1 đọc; B7 ghi |
| Quotation | 13 trường tổng tiền (`total`, `net_total`, `grand_total`, `rounded_total`, `in_words`…) | B7 tính lại |

**Cấu trúc sản phẩm**

| DocType | Field engine dùng | Bước |
| --- | --- | --- |
| AL BOM | `current_version`, `bom_set`, `default_cost_template` | B0 |
| AL BOM Version | `bom_set_snapshot`, `cost_template_snapshot`, `pricing_dimension_snapshot` (bất biến sau khi Published) | B0, B2, B6 |
| AL Bom Set | `profile_system`, `product_type`, `variable_set`, `default_accessory_set`, `formula_fieldnames`, `apply_scrap_pct` | B1, B2, B3 |
| AL Bom Item | `slug`, `item_code`, `price_base_item`, `category`, `calc_pattern`, `cost_bucket`, `width`/`height`/`qty` (công thức), `item_selection_mode`, `item_rule`, `rule_input_expr`, `default_glass_master`, `default_color` | B2 → B5 |
| AL Accessory Set / Item | `slug`, `item_code`, `qty`, `qty_formula`, `unit_price`, `calc_pattern` (mặc định COUNT), `cost_bucket` (mặc định VL\_PK) | B2 |

**Biến**

| DocType | Vai trò |
| --- | --- |
| AL Variable Library, AL Variable Set | Khai báo biến, mặc định, biến hệ thống lấy từ `source_doctype.source_field` |
| AL Profile System | `offset_frame`, `offset_glass`, `offset_fixed`, `offset_crossbar` → `OFFSET_FRAME/GLASS/FIXED/DO_NGANG` |
| AL Product Type | `nc_pct`, `nc_ld_rate`, `profit_margin` → `NC_SX_PCT`, `NC_LD_PCT`, `PROFIT_MARGIN` |
| Formula Global Variable | `VAT_RATE`, `OH_VC_PCT`, `OH_QLY_PCT`, `ASYNC_BOM_THRESHOLD` |
| Formula Variable Binding | "Lấy giá trị thế nào": biến hệ thống và binding giá composite |

**Master vật tư và giá**

| DocType | Vai trò |
| --- | --- |
| Item | `weight_per_unit` (kg/m) |
| Item Price | `price_list_rate`, `price_list`, `valid_from/upto`, `currency`, các field `custom_pd_*` (dimension) |
| AL Pricing Dimension, AL Variable Dimension Mapping | Định nghĩa chiều của composite key và ánh xạ biến → dimension → `material_category`, kèm `price_multiplier` |
| AL Color Standard | Mã màu; `price_multiplier` chỉ có tác dụng ở chế độ `multiplier_chain` |
| AL Material Category | `default_scrap_pct`, `has_weight`, `requires_glass_master`, `default_calc_pattern` |
| AL Glass Master | `total_thick_mm`, `glass_type`, `max_area_m2` |

**Quy tắc và giá thành**

| DocType | Vai trò |
| --- | --- |
| AL Quantity Calc Method | Cách tính `unit_qty` (`calc_fn` dạng lambda, `input_vars`, `output_unit`) |
| AL Rule (`result_type = NUMBER`) | Bảng tra CONSTANT / THRESHOLD / LOOKUP, gọi bằng `lookup_rule(mã, giá_trị)` |
| AL Rule (`result_type = ITEM`) | Chọn mã vật tư theo thuộc tính (độ dày kính → mã nẹp, loại kính → mã keo) |
| AL Cost Bucket | Nhóm chi phí LEAF/AGGREGATE (VL\_NHOM, VL\_KINH, VL\_VTP, VL\_PK, TONG\_VL…) |
| AL Cost Template + Item | `line_code`, `calc_formula`, `is_subtotal`, `is_final_price`, `is_pre_vat_price` |
| ConfigSnapshot | Chỉ tạo khi submit Quotation, không tạo mỗi lần tính |

## 3. Engine tính toán từng bước

### 3.1 B0 → B7

**B0 – Chốt phiên bản** (`bom_orchestrator.py:311`). Thứ tự: `Quotation Item.al_bom_version` → `AL BOM.current_version` → version mới nhất theo `creation DESC`. BOM chưa có version nào thì `frappe.throw` yêu cầu người dùng tự tạo và xuất bản; đường tính giá cố ý không tự tạo version.

**B1 – Gom biến** (`:368`). Thứ tự quyết định giá trị cuối, bước sau ghi đè bước trước:

| Bước | Nguồn |
| --- | --- |
| 1.1 | `al_bom_vars.extra_vars` |
| 1.2 | `Formula Global Variable` (cache Redis 60 s) |
| 1.4 | Formula Builder `get_live_context`, scope `AL Bom Set` (chạy trước 1.3 để biến đã seed khỏi resolve hai lần) |
| 1.3 | Resolver cũ từ `AL Variable Library`, chỉ điền biến còn thiếu |
| 1.4b | `system_variables` của AL Profile System (cấu hình tường minh theo profile) |
| 1.5 | Biến người dùng nhập trong `al_bom_vars` (thắng tất cả nguồn trên) |
| 1.5b/c | Bắt override `_accessory_set`, `glass_master`, `glass_master_map`, `color_master_map`, `_profile_system`, `_cost_template`; có `_profile_system` thì resolve lại biến hệ thống |
| 1.6 | Giá trị mặc định cho biến người dùng chưa nhập (vd `installation_height_m = 3`) |
| 1.7 | **Chuẩn hoá phần trăm**, chạy cuối cùng |

Chuẩn hoá phần trăm (`_normalize_percent_inputs`): biến có tên kết thúc `_PCT`, `_MARGIN`, `_RATE` hoặc khai `var_type = Percent` mà `|giá trị| > 1` thì chia 100 (`8 → 0.08`, `10 → 0.10`). Giá trị đúng bằng 1 giữ nguyên (hiểu là 100%) và sinh cảnh báo `phan_tram_mo_ho_bang_1__warn:<tên>`.

**B2 – Nạp master data và tra giá** (`:857`):

1. Nạp phụ kiện (`_load_accessories`): bộ phụ kiện từ `al_bom_vars._accessory_set` hoặc `Bom Set.default_accessory_set`; mỗi dòng được append vào `bom_items` như một dòng BOM thường (`calc_pattern = COUNT`, `cost_bucket = VL_PK`; `qty` lấy `qty_formula` nếu có).
2. Sáu batch query: (1) `Item.weight_per_unit`; (2) `Item Price` theo composite key; (3) `AL Glass Master`; (4) `AL Material Category`; (5) `AL Rule` (rule chọn mã) giải mã vật tư động; (6) `Item` + `Item Price` của mã vừa resolve ở (5).
3. Dựng `row_literals[slug]`: `weight_per_unit`, `unit_price`, `calc_pattern`, `glass_thick`, `glass_type`, `scrap_pct`, `has_weight`, `color`… Giá khai tay `AL Accessory Item.unit_price > 0` thắng giá tra tự động.

Chi tiết tra giá ở mục 4.

**B3 – Dựng công thức** (`:1967`). Mỗi dòng BOM sinh các công thức tên `{slug}__{field}` cho `width`, `height`, `qty`, `show_condition`… (danh sách field lấy từ `formula_fieldnames`), cộng ba công thức tổng hợp luôn có:

```
{slug}__unit_qty  = lookup_calc_pattern({slug}__calc_pattern, {slug}__width,
                       {slug}__height, {slug}__weight_per_unit [, {biến phụ}])
{slug}__total_qty = {slug}__unit_qty * {slug}__qty
                    # khi Bom Set bật apply_scrap_pct:
                    # ({slug}__unit_qty * {slug}__qty) * (1 + {slug}__scrap_pct/100)
{slug}__line_total = {slug}__total_qty * {slug}__unit_price
```

Biểu thức tham chiếu chéo dòng `items.kinh_tren.width` được `normalize_global` của Formula Builder đổi thành `kinh_tren__width`, tức trỏ tới kết quả công thức (tạo cạnh phụ thuộc trong DAG). Cố ý không dùng `DotToSubscriptTransformer`, vì nó sẽ đọc dict literal chưa có kết quả và làm nẹp/keo/gioăng ra 0.

**B4 – Tính dòng vật tư** (`:2181`). Dựng `FormulaEngine(formulas=bom_formulas, safe_funcs=…, on_error="default", default_value=0, deterministic=True)` (có cache theo vân tay nội dung công thức), gọi `engine.calculate(inputs)`, rồi dựng `lines[]` (slug, item\_code, width, height, qty, unit\_qty, total\_qty, unit\_price, line\_total, cost\_bucket, trace…). Sau đó cảnh báo diện tích kính vượt `max_area_m2` (chỉ cảnh báo, không chặn).

**B5 – Gom cost bucket** (`:2315`). Cộng `line_total` theo `cost_bucket` của từng dòng. Bucket LEAF khai `source_type = aggregate_from_items` kèm `source_config` hợp lệ thì giao cho Formula Builder; còn lại cộng bằng Python. Seed hiện chưa có `source_config` nên đường Python là đường đang chạy.

**B6 – Cost Template** (`:2432`). Công thức lấy từ `cost_template_snapshot` của version (hoặc doc sống nếu có `_cost_template`). Mỗi dòng thành một công thức tên `line_code`. Context = giá trị bucket + biến đầu vào + kết quả B4. Mã bucket được công thức nhắc tới mà không có giá trị thì mặc định 0. Dòng giá cuối chọn theo **cờ**: `is_final_price = 1` → `al_gia_vat`, `is_pre_vat_price = 1` → `al_gia_ban`; không dòng nào có cờ thì fallback theo tên `GIA_VAT` / `GIA_BAN` (seed hiện đi đường fallback này).

**B7 – Ghi kết quả** (`:2588`). `frappe.db.set_value` cho `al_gia_vat`, `al_gia_ban`, `al_bom_result`, `rate` (= giá trước VAT), tính lại tổng của Quotation cha bằng `set_value(update_modified=False)` (không `save()` cha để tránh `TimestampMismatchError`), rồi 1 commit. Trước khi ghi, `assert_quotation_item_editable` chặn báo giá đã submit hoặc huỷ.

### 3.2 Formula Builder làm gì bên dưới

- **Khởi tạo** (`FormulaEngineCore.__init__`, `engine_core.py:192`): gỡ HTML entity, parse + biên dịch từng công thức, dựng `DependencyGraph`, sắp xếp topo (Kahn).
- **Dò phụ thuộc** (`topo.py: extract_identifiers`): bỏ chuỗi literal, bỏ phần `.field`, lấy mọi định danh còn lại. Cạnh chỉ sinh khi định danh trùng **tên một công thức khác**. Hệ quả: thứ tự dòng không quan trọng, nhưng gõ sai tên thì mất cạnh và biến rơi về giá trị mặc định 0 mà không báo lỗi. Hai công thức trùng tên thì dòng sau đè dòng trước (`_original_expr` là dict theo tên).
- **Tính** (`calculate`, `:861`): duyệt `_topo_order`, mỗi công thức `eval` trên bytecode đã biên dịch. Kết quả trả về chỉ gồm các công thức, không gồm đầu vào, nên B4 phải `self.inputs.update(result)` để B6 thấy được `{slug}__…`.
- **Lỗi**: `on_error="default"` gán 0 cho công thức lỗi và ghi `last_errors`, một dòng hỏng không giết cả BOM. Riêng **chia cho 0** theo chính sách mặc định `raise` ném `FormulaZeroDivisionError`, chết cả lần tính; vì vậy seed dùng `safe_div`.
- **Hàm**: `BASE_FUNCS` của Formula Builder (có `safe_div`, `IF`, `min`, `max`, `round`…) được copy rồi `update(safe_funcs)`. AlumGlass truyền ba hàm: `lookup_calc_pattern`, `lookup_rule`, `roundup`. `roundup` của AlumGlass làm tròn ra xa 0 như Excel và đè bản của Formula Builder (bản đó dùng `ceil`, sai với số âm).
- **Bảo mật**: `calc_fn` lưu trong DB được biên dịch qua `compile_expression` (whitelist AST, globals rỗng), không `eval` trần.
- **Cache engine** (`engine/engine_cache.py`): khoá là vân tay `(tên, công thức)`; cùng một BOM hay cùng Cost Template chỉ biên dịch DAG một lần (mặc định giữ 16 engine mỗi cache, chỉnh bằng `alumglass_engine_cache_size`). Sửa công thức thì vân tay đổi, tự dựng engine mới.
- **Binding source type** AlumGlass dùng: `constant`, `linked_doctype_field`, `composite_key_lookup`, `aggregate_from_items` (có sẵn của Formula Builder) và hai type tự đăng ký `aluminum_price_composite`, `glass_master_data` (`fb_handlers.py`). B6 không còn dùng `FlexibleFormulaEngine`.

## 4. Tra cứu giá cụ thể

### 4.1 Giá của một dòng lấy từ đâu

| Loại dòng | Mã dùng để tra giá | Ghi chú |
| --- | --- | --- |
| Nhôm (khung, đố, cánh) | `price_base_item` = `NHOM-XINGFA`, tra theo composite key | Mọi dòng nhôm Fixed dùng chung một mã đại diện nên cùng đơn giá/kg. Khối lượng lấy theo `weight_per_unit` của `item_code` của dòng (khác mã giá). |
| Kính | Mã kính đã resolve theo vị trí: `glass_master_map[rep]` → `glass_master` toàn BOM → `default_glass_master` của dòng | Mã giữ chỗ (vd `KINH-01`) thường không có giá; chưa chọn kính thật thì giá = 0 kèm cảnh báo. |
| Nẹp, keo (`item_selection_mode = Rule`) | Mã do AL Rule (result_type = ITEM) chọn | Giá và khối lượng lấy theo mã đã chọn (batch #6), **không** theo composite key. |
| Phụ kiện | `Item Price` theo `item_code` | Nếu `AL Accessory Item.unit_price > 0` thì giá khai tay thắng. |

Thứ tự gán `unit_price` trong `row_literals`: `prices[price_base_item]` nếu dòng có `price_base_item`, không thì `prices[item_code]`; dòng Rule ghi đè bằng giá của mã đã resolve; cuối cùng giá khai tay của phụ kiện ghi đè tất cả.

### 4.2 Bảng giá trong seed (Standard Selling, VND)

| Item | Nhóm | Đơn giá | Đơn vị giá | kg/m |
| --- | --- | --- | --- | --- |
| NHOM-XINGFA (mã đại diện) | Nhôm | 113.000 | kg | 0 |
| XF55-KB-20 (khung bao) | Nhôm | 113.000 | kg | 1,257 |
| XF55-CANH-20 (cánh) | Nhôm | 113.000 | kg | 1,350 |
| C3211-20 (nẹp kính > 16 mm) | Nhôm | 113.000 | kg | 0,312 |
| C3210-20 (nẹp 11–16 mm) | Nhôm | 113.000 | kg | 0,245 |
| C3209-20 (nẹp ≤ 10,38 mm) | Nhôm | 113.000 | kg | 0,198 |
| KINH-LOWE-24 | Kính | 1.150.000 | m² | – |
| KINH-DON-8 | Kính | 550.000 | m² | – |
| KEO-TT-01 (keo cho kính LOWE) | Vật tư phụ | 45.000 | m | – |
| KEO-TT-02 (keo cho kính DON) | Vật tư phụ | 30.000 | m | – |
| GIO-EPDM-55 | Vật tư phụ | 1.250 | m | – |
| VIT-TK-35X16 | Vật tư phụ | 850 | cái | – |
| KL-MZS20 (tay nắm) | Phụ kiện | 210.000 | cái | – |
| KL-KHOA-01 (khóa) | Phụ kiện | 350.000 | cái | – |
| KL-T-MJ06 (bản lề) | Phụ kiện | 180.000 | cái | – |

Nhôm tính theo kg: khối lượng một thanh = chiều dài (m) × kg/m, rồi nhân đơn giá kg. Mỗi item trong seed chỉ có **đúng một** dòng Item Price và dòng đó không gắn dimension nào (`custom_pd_*` trống).

### 4.3 Thuật toán chọn dòng Item Price

1. **Bảng giá**: `Selling Settings.selling_price_list`, dự phòng `Standard Selling`. Binding `COMPOSITE_MATERIAL_PRICE` được seed lại mỗi lần migrate với đúng bảng giá này, nên hai đường tra giá (Formula Builder và Python dự phòng) không lệch nhau.
2. **Lọc hiệu lực**: giữ dòng có `valid_from ≤ hôm nay ≤ valid_upto` (NULL được chấp nhận) và đúng `currency` (dòng chưa khai currency vẫn giữ). Nếu bảng giá khác tiền tệ báo giá thì không lọc tiền tệ và ghi Error Log.
3. **Xác định dimension áp dụng** cho dòng đang tra: lấy từ `pricing_dimension_snapshot` của BOM Version (version cũ chưa có snapshot thì đọc cấu hình sống), lọc theo `material_category` của dòng BOM. Seed có 4 mapping cho NHOM: `aluminum_color→MAU_SAC`, `aluminum_origin→XUAT_XU`, `aluminum_thickness→DO_DAY`, `aluminum_surface→BE_MAT`.
4. **`best_partial_match`** (`engine/composite_pricing.py`):
   - 0 dòng → `None`. **Đúng 1 dòng → trả luôn dòng đó**, không kiểm dimension.
   - Từ 2 dòng trở lên: với mỗi dòng, field dimension trống thì bỏ qua; có giá trị nhưng khác input thì loại dòng; khớp thì cộng 1 điểm. Chọn điểm cao nhất (hòa thì dòng đứng trước).
   - Không dòng nào sống sót thì lấy dòng "trần" (không gắn dimension); không có dòng trần thì `None`.
5. **Không tìm thấy**: nhánh binding (`allow_missing=True`) trả 0 và ghi cảnh báo `thieu_gia_item:<mã>`; nhánh Python dự phòng `frappe.throw("Không tìm được Item Price khớp…")`.

**Ví dụ minh hoạ (không phải dữ liệu seed).** Giả sử `NHOM-XINGFA` có 3 dòng giá: (a) trần 113.000; (b) màu DARK 122.000; (c) màu WHITE + bề mặt POWDER\_COATED 115.000. Input WHITE + POWDER\_COATED: (a) 0 điểm, (b) bị loại vì DARK ≠ WHITE, (c) 2 điểm → chọn **115.000**. Input GRAY: (b) và (c) đều bị loại → rơi về dòng trần **113.000**.

### 4.4 Màu theo vị trí

Dialog cho chọn màu từng nhóm vị trí, lưu `color_master_map = {rep: mã màu}`. `_compute_color_price_overrides` thay giá trị màu trong context khi tra giá cho `item_code` / `price_base_item` của dòng đó, nên ở `exact_match` màu chỉ dùng để **chọn dòng giá**. Giới hạn đã biết: hai dòng khác nhóm màu mà dùng chung một mã giá thì dòng xử lý sau đè dòng trước; muốn tách giá thì cho mỗi nhóm một `price_base_item` riêng.

### 4.5 Hai chế độ `pricing_mode`

- **`exact_match`** (seed đang dùng): như mục 4.3. `AL Color Standard.price_multiplier` **không** được nhân. Vì seed không gắn dimension nên DARK và WHITE ra cùng một giá.
- **`multiplier_chain`**: giá = giá gốc (dòng trần) × tích các hệ số. Với dimension kiểu Link, hệ số là `price_multiplier` của bản ghi được link (`AL Color Standard`: WHITE 1,00; DARK 1,08; GRAY 1,05; GO 1,20); nếu bản ghi không khai thì dùng `price_multiplier` trên `AL Variable Dimension Mapping` (seed đều 1,0). Chỉ áp cho mapping cùng `material_category`. Màu theo vị trí không tham gia (hàm đọc thẳng `self.inputs`). Thiếu dòng trần thì lấy dòng đầu và cảnh báo `gia_goc_thieu_dong_tran`, có thể nhân trùng phụ phí.
- **Cách bật**: đổi `pricing_mode` trong hằng số `COMPOSITE_PRICING_BINDING` ở `setup/install_fb_bindings.py`. Sửa trên form `Formula Variable Binding` sẽ bị ghi đè lại ở lần migrate kế tiếp, vì hàm `install_composite_pricing_binding` đặt lại mọi field khác với khai báo trong code.
- Dòng chọn mã bằng Rule (nẹp, keo) không chịu ảnh hưởng của chế độ này (điểm 5 ở mục 0).

### 4.6 Các rule tra bảng trong seed

| Rule | Loại | Dải → kết quả | Dùng ở |
| --- | --- | --- | --- |
| `RULE-BANLE-QTY` | THRESHOLD | \[0; 2100) → 2; \[2101; 2700) → 4; \[2701; 99999) → 4 | `qty_formula` bản lả: `lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel` |
| `RULE-HEIGHT-MULT` | THRESHOLD | \[0; 10) → 1,0; \[10,1; 30) → 1,2; \[30,1; 60) → 1,5; \[60,1; 999) → 2,0 | dòng `NC_LD` với `installation_height_m` |
| `OFFSET-FRAME/GLASS/FIXED/DO-NGANG` | CONSTANT | 48 / 90 / 50 / 48 | tương thích ngược; giá trị thật đọc từ `AL Profile System` |
| `RULE-NEP-GLASSTHICK` (AL Rule, ITEM) | THRESHOLD | \[0; 10,38) → C3209-20; \[10,39; 16) → C3210-20; \[16,01; 999) → C3211-20 | chọn nẹp theo `items.<kính>.glass_thick` |
| `RULE-KEO-GLASSTYPE` (AL Rule, ITEM) | LOOKUP | LOWE → KEO-TT-01; DON → KEO-TT-02 | chọn keo theo `glass_type` |

Quy ước biên của `AL Rule.resolve` (dùng chung `rule_engine.resolve_threshold`): duyệt dải theo `from_value` tăng dần và khớp khi `from ≤ x < to`; nếu không dải nào khớp thì thử lại "x == to" của một dải. Kết quả mô phỏng lại đúng thuật toán đó trên dữ liệu seed:

| Tra | Kết quả | Giải thích |
| --- | --- | --- |
| `HEIGHT-MULT(3)` | 1,0 | nằm trong \[0; 10) |
| `HEIGHT-MULT(10)` | 1,0 | rơi khe, cứu nhờ lưới "bằng biên trên" |
| `HEIGHT-MULT(10,05)` | `None` → **0** | rơi vào khe 10 → 10,1; `NC_LD` = 0 mà không báo lỗi |
| `HEIGHT-MULT(15)` | 1,2 | \[10,1; 30) |
| `HEIGHT-MULT(30)` | 1,2 | cứu bằng biên trên |
| `BANLE-QTY(2600)` | 4 | \[2101; 2700) |
| `BANLE-QTY(3200)` | 4 | \[2701; 99999) |
| `BANLE-QTY(2100,5)` | `None` → **0** | rơi khe 2100 → 2101 |

Khe hở chỉ lộ ra với số lẻ. Khi khai rule mới nên nối liền: dải sau bắt đầu đúng bằng `to` của dải trước (code có `msgprint` cảnh báo khe hở lúc lưu).

### 4.7 Các calc pattern (cách tính `unit_qty`)

`lookup_calc_pattern` tra theo thứ tự: cache → `AL Quantity Calc Method.calc_fn` trong DB (biên dịch qua `safe_eval`) → `PATTERN_FORMULAS` tích hợp sẵn → `ValueError`. Trong công thức, `w`, `h` là mm, `tlr` là kg/m.

| Pattern | `unit_qty` | ĐVT | Seed dùng cho |
| --- | --- | --- | --- |
| `LENGTH_TO_WEIGHT` | `(w/1000) * tlr` | kg | nhôm, nẹp |
| `AREA` (≡ `AREA_M2`) | `(w/1000) * (h/1000)` | m² | kính |
| `LENGTH_ONLY` (≡ `LENGTH_M`) | `w/1000` | m | keo, gioăng |
| `COUNT`, `SET` | `1` | cái, bộ | vít, phụ kiện |
| `HEIGHT_M` | `h/1000` | m | – |
| `LENGTH_TO_PIECES` | `(w/1000) / piece_length` | cái | – |
| `AREA_TO_WEIGHT` | `(w/1000)*(h/1000)*tlr` | kg | – |
| `PERIMETER_M` | `2*(w+h)/1000` | m | – |
| `VOLUME_M3` | `(w/1000)*(h/1000)*depth/1000` | m³ | – |
| `COUNT_PER_LENGTH` | `(w/1000) / spacing` | cái | – |
| `COUNT_PER_AREA` | `(w/1000)*(h/1000) / area_per_piece` | cái | – |

Biến phụ (`piece_length`, `spacing`, `depth`, `area_per_piece`) khai trong `input_vars` của pattern; B3 lấy theo thứ tự `input_vars` của dòng → biến người dùng → `row_literals` → 0 và truyền dưới dạng dict ở tham số thứ 5. Phân biệt: `unit_qty` là số lượng của **một** linh kiện; `qty` là số linh kiện; `total_qty = unit_qty × qty`.

### 4.8 Khi thiếu giá hoặc có lỗi: túi `errors`

Mọi cảnh báo đi vào `al_bom_result.errors.bom_items` (B2, B4) hoặc `.cost_template` (B6). Một dòng lỗi nhận 0 chứ không dừng cả BOM, nên **giá 0 có thể là "không tìm thấy giá"**, không phải miễn phí.

| Khoá | Nghĩa là |
| --- | --- |
| `thieu_gia_item:<mã>` | Không có dòng Item Price hợp lệ cho mã, tạm tính 0 |
| `thieu_gia_goc:<mã>`, `gia_goc_thieu_dong_tran:<mã>` | `multiplier_chain` thiếu giá gốc / dòng trần |
| `gia_nhieu_dong_rule_item:<mã>` | Mã do Rule chọn có nhiều dòng giá, tạm lấy dòng đầu |
| `lookup_rule_thieu_ma:<rule>` | Công thức gọi mã `AL Rule` không tồn tại |
| `lookup_rule_sai_loai:<rule>` | Công thức gọi rule chọn mã (`result_type = ITEM`) |
| `<slug>__max_area_exceeded` | Diện tích tấm kính vượt `max_area_m2` |
| `bucket_source_type_chua_ho_tro:<mã>` | Cost Bucket khai `source_type` mà engine chưa chạy |
| `phan_tram_mo_ho_bang_1__warn:<biến>` | Biến % đúng bằng 1, mơ hồ 1% hay 100% |

## 5. Cost Template `CT-01-STANDARD`

Mỗi dòng là một công thức tên `line_code`. Các biến `VL_NHOM`…`VL_PK` là bucket từ B5; `NC_SX_PCT`, `NC_LD_PCT`, `PROFIT_MARGIN`, `OH_VC_PCT`, `OH_QLY_PCT`, `VAT_RATE` là biến đã chuẩn hoá sang thập phân ở B1.

| # | `line_code` | Công thức |
| --- | --- | --- |
| 1 | `TONG_VL` | `VL_NHOM + VL_KINH + VL_VTP + VL_PK` |
| 2 | `TONG_M2` | `(W_mm/1000) * (H_mm/1000)` |
| 3 | `NC_SX` | `NC_SX_PCT * TONG_VL` |
| 4 | `NC_LD` | `NC_LD_PCT * TONG_VL * lookup_rule('RULE-HEIGHT-MULT', installation_height_m)` |
| 5 | `TONG_NC` | `NC_SX + NC_LD` |
| 6 | `OH_VC` | `OH_VC_PCT * TONG_VL` |
| 7 | `OH_QLY` | `OH_QLY_PCT * (TONG_VL + TONG_NC)` |
| 8 | `TONG_OH` | `OH_VC + OH_QLY` |
| 9 | `GIA_THANH` | `TONG_VL + TONG_NC + TONG_OH` |
| 10 | `PROFIT` | `PROFIT_MARGIN * GIA_THANH` |
| 11 | `GIA_BAN` | `GIA_THANH + PROFIT` (giá trước VAT → `al_gia_ban`, `rate`) |
| 12 | `DON_GIA_M2` | `safe_div(GIA_BAN, TONG_M2, 0)` |
| 13 | `VAT` | `VAT_RATE * GIA_BAN` |
| 14 | `GIA_VAT` | `GIA_BAN + VAT` (giá có VAT → `al_gia_vat`) |

**Hệ số tổng để kiểm nhanh.** Ghi `h` là hệ số `RULE-HEIGHT-MULT`, ta có `TONG_NC = TONG_VL × (0,08 + 0,12h)`, `TONG_OH = TONG_VL × (0,03 + 0,03 × (1 + 0,08 + 0,12h))`, rồi `GIA_VAT = GIA_THANH × 1,16 × 1,10`. Cho kết quả gọn: `h = 1,0` → `GIA_VAT = TONG_VL × 1,615416`; `h = 1,2` → `GIA_VAT = TONG_VL × 1,646959`. Hai hệ số này khớp với ví dụ 2C và 4C bên dưới.

**Lưu ý khi cấu hình:**

- B6 sắp theo DAG nên `GIA_VAT` đứng trước `GIA_BAN` trong bảng vẫn tính đúng. Rủi ro thật là **tên**: gõ sai `line_code` thì mất cạnh phụ thuộc và rơi về 0; trùng `line_code` thì dòng sau đè dòng trước; cả hai đều im lặng.
- `AL Cost Template.validate` kiểm cú pháp, ngoặc và biến chưa khai báo theo thứ tự dòng; chỉ hiện cảnh báo (`msgprint`), không chặn lưu.
- `preview_cost_template` chạy tuần tự theo thứ tự dòng, nên dòng đứng sau dòng nhắc tới nó sẽ lệch với kết quả B6 thật.
- Seed chưa đặt cờ `is_final_price` / `is_pre_vat_price`, nên engine fallback theo tên `GIA_VAT` / `GIA_BAN`. Đổi tên hai dòng này mà không đặt cờ thì đầu ra về 0.
- Mỗi `line_code` được lưu kèm chuỗi trace đã thay số (`cost_template_trace`) để dialog giải thích con số.

## 6. Ví dụ 1 – Cửa đi 2 cánh `BOM-CDMQ-2C`, tính từng bước

Nguồn dữ liệu: `setup/seed_demo_data.py` và `run_test.py:test_cdmq_2c`. Mọi con số dưới đây do tôi tính lại độc lập từ công thức seed (không chạy Frappe).

### B0 – Chốt phiên bản

`Quotation Item.al_bom = BOM-CDMQ-2C`. Dòng đã có `al_bom_version` thì dùng luôn; không thì lấy `AL BOM.current_version`. Version `v1.0` đã Published, nên đọc `bom_set_snapshot`, `cost_template_snapshot`, `pricing_dimension_snapshot` của nó.

### B1 – Gom biến

| Biến | Nguồn | Giá trị sau chuẩn hoá |
| --- | --- | --- |
| `W_mm`, `H_mm`, `n_panel`, `TransomHeight_mm` | người dùng nhập trong `al_bom_vars` | 2400, 2600, 2, 600 |
| `aluminum_color`, `_origin`, `_thickness`, `_surface` | người dùng nhập | WHITE, IMPORT, 20, POWDER\_COATED |
| `installation_height_m` | không nhập, lấy `default_value` của Variable Library (bước 1.6) | 3 |
| `OFFSET_FRAME/GLASS/FIXED/DO_NGANG` | `AL Profile System` `XINGFA_55` | 48 / 90 / 50 / 48 |
| `NC_SX_PCT`, `NC_LD_PCT`, `PROFIT_MARGIN` | `AL Product Type` `DOOR`: `nc_pct`=8, `nc_ld_rate`=12, `profit_margin`=16 | 0,08 / 0,12 / 0,16 |
| `VAT_RATE`, `OH_VC_PCT`, `OH_QLY_PCT` | `Formula Global Variable` 10 / 3 / 3 | 0,10 / 0,03 / 0,03 |

Bước 1.7 chia 100 các biến tên kết thúc `_PCT`, `_MARGIN`, `_RATE` vì giá trị lớn hơn 1.

### B2 – Tra giá và giải mã động

- Phụ kiện: bộ `ACC-CDMQ-2C` (từ `Bom Set.default_accessory_set`) thêm 3 dòng `tay_nam`, `khoa`, `ban_le` vào danh sách BOM.
- Nhôm: `price_base_item = NHOM-XINGFA`, mỗi mã chỉ có 1 dòng Item Price nên trả **113.000 đ/kg** cho `XF55-KB-20` và `XF55-CANH-20` (khối lượng 1,257 và 1,350 kg/m).
- Kính: `default_glass_master = KINH-LOWE-24` → `glass_thick = 24`, `glass_type = LOWE`, giá **1.150.000 đ/m²**.
- Rule chọn mã: `nep_kinh_*` dùng `RULE-NEP-GLASSTHICK` với input 24 → dải \[16,01; 999) → **C3211-20** (0,312 kg/m, 113.000 đ/kg). `keo_*` dùng `RULE-KEO-GLASSTYPE` với input `LOWE` → **KEO-TT-01** (45.000 đ/m).
- Phụ kiện: tay nắm 210.000, khóa 350.000, bản lề 180.000.

### B3 + B4 – Tính từng dòng vật tư

Mỗi dòng đi qua 5 phép tính: `width`, `height` (công thức khai trên AL Bom Item) → `unit_qty` (theo calc pattern) → `qty` → `total_qty = unit_qty × qty` → `line_total = total_qty × unit_price`.

| slug | mã | width (mm) | height (mm) | `unit_qty` | qty | `total_qty` | đơn giá | `line_total` | bucket |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `khung_ngang_tren` | XF55-KB-20 | `W_mm` = 2400 | – | 2,4×1,257 = 3,0168 | 1 | 3,0168 | 113.000 | 340.898 | VL\_NHOM |
| `khung_ngang_duoi` | XF55-KB-20 | 2400 | – | 3,0168 | 1 | 3,0168 | 113.000 | 340.898 | VL\_NHOM |
| `khung_dung` | XF55-KB-20 | `H_mm` = 2600 | – | 2,6×1,257 = 3,2682 | 2 | 6,5364 | 113.000 | 738.613 | VL\_NHOM |
| `do_ngang` | XF55-KB-20 | `W_mm - 2*OFFSET_DO_NGANG` = 2304 | – | 2,304×1,257 = 2,8961 | 1 | 2,8961 | 113.000 | 327.262 | VL\_NHOM |
| `canh_ngang` | XF55-CANH-20 | `safe_div(W_mm, n_panel, 0) - OFFSET_FRAME` = 1152 | – | 1,152×1,350 = 1,5552 | `2*n_panel` = 4 | 6,2208 | 113.000 | 702.950 | VL\_NHOM |
| `canh_dung` | XF55-CANH-20 | `(H_mm-TransomHeight_mm) - OFFSET_FRAME` = 1952 | – | 1,952×1,350 = 2,6352 | 4 | 10,5408 | 113.000 | 1.191.110 | VL\_NHOM |
| `kinh_tren` | KINH-LOWE-24 | `W_mm - 2*OFFSET_FIXED` = 2300 | `TransomHeight_mm - OFFSET_FIXED` = 550 | 2,3×0,55 = 1,2650 | 1 | 1,2650 | 1.150.000 | 1.454.750 | VL\_KINH |
| `kinh_duoi` | KINH-LOWE-24 | `safe_div(W_mm, n_panel, 0) - OFFSET_GLASS` = 1110 | `(H_mm-TransomHeight_mm) - OFFSET_GLASS` = 1910 | 1,11×1,91 = 2,1201 | `n_panel` = 2 | 4,2402 | 1.150.000 | 4.876.230 | VL\_KINH |
| `nep_kinh_tren` | C3211-20 (Rule) | `2*(items.kinh_tren.width + items.kinh_tren.height)` = 5700 | – | 5,7×0,312 = 1,7784 | 2 | 3,5568 | 113.000 | 401.918 | VL\_NHOM |
| `nep_kinh_duoi` | C3211-20 (Rule) | `2*(1110+1910)` = 6040 | – | 6,04×0,312 = 1,8845 | `2*n_panel` = 4 | 7,5379 | 113.000 | 851.785 | VL\_NHOM |
| `keo_tren` | KEO-TT-01 (Rule) | 5700 | – | 5,7 m | 1 | 5,7 | 45.000 | 256.500 | VL\_VTP |
| `keo_duoi` | KEO-TT-01 (Rule) | 6040 | – | 6,04 m | `n_panel` = 2 | 12,08 | 45.000 | 543.600 | VL\_VTP |
| `gioang` | GIO-EPDM-55 | `kh_ngang_tren.width + kh_ngang_duoi.width + 2*khung_dung.width` = 10000 | – | 10 m | 1 | 10 | 1.250 | 12.500 | VL\_VTP |
| `vit` | VIT-TK-35X16 | – | – | 1 | `10*n_panel + 8` = 28 | 28 | 850 | 23.800 | VL\_VTP |
| `tay_nam` | KL-MZS20 | – | – | 1 | 1 | 1 | 210.000 | 210.000 | VL\_PK |
| `khoa` | KL-KHOA-01 | – | – | 1 | 1 | 1 | 350.000 | 350.000 | VL\_PK |
| `ban_le` | KL-T-MJ06 | – | – | 1 | `lookup_rule('RULE-BANLE-QTY', 2600) * 2` = 4×2 = 8 | 8 | 180.000 | 1.440.000 | VL\_PK |

**Đọc một dòng mẫu** (`do_ngang`): `width = 2400 − 2×48 = 2304` → pattern `LENGTH_TO_WEIGHT` cho `unit_qty = (2304/1000) × 1,257 = 2,896128 kg` → `total_qty = 2,896128 × 1 = 2,896128` → `line_total = 2,896128 × 113.000 = 327.262,5`. Dòng kính dùng pattern `AREA` nên `unit_qty` là m² và đơn giá là đ/m².

Thứ tự tính do DAG quyết định: `nep_kinh_tren__width` trỏ tới `kinh_tren__width` và `kinh_tren__height` nên hai công thức kính chạy trước; `gioang__width` phụ thuộc ba công thức width của khung.

### B5 – Gom bucket

| Bucket | Tổng `line_total` | Gồm |
| --- | --- | --- |
| `VL_NHOM` | 4.895.436,6 | khung, đố, cánh, nẹp |
| `VL_KINH` | 6.330.980,0 | 2 loại tấm kính |
| `VL_VTP` | 836.400,0 | keo, gioăng, vít |
| `VL_PK` | 2.000.000,0 | tay nắm, khóa, bản lề |

### B6 – Cost Template

| `line_code` | Thay số | Kết quả |
| --- | --- | --- |
| `TONG_VL` | 4.895.436,6 + 6.330.980 + 836.400 + 2.000.000 | **14.062.816,6** |
| `TONG_M2` | 2,4 × 2,6 | 6,240 m² |
| `NC_SX` | 0,08 × 14.062.816,6 | 1.125.025,3 |
| `NC_LD` | 0,12 × 14.062.816,6 × `lookup_rule('RULE-HEIGHT-MULT', 3)` = 1,0 | 1.687.538,0 |
| `TONG_NC` | 1.125.025,3 + 1.687.538,0 | 2.812.563,3 |
| `OH_VC` | 0,03 × 14.062.816,6 | 421.884,5 |
| `OH_QLY` | 0,03 × (14.062.816,6 + 2.812.563,3) | 506.261,4 |
| `TONG_OH` | 421.884,5 + 506.261,4 | 928.145,9 |
| `GIA_THANH` | 14.062.816,6 + 2.812.563,3 + 928.145,9 | **17.803.525,8** |
| `PROFIT` | 0,16 × 17.803.525,8 | 2.848.564,1 |
| `GIA_BAN` | 17.803.525,8 + 2.848.564,1 | **20.652.090,0** |
| `DON_GIA_M2` | `safe_div(20.652.090, 6,24, 0)` | 3.309.629,8 đ/m² |
| `VAT` | 0,10 × 20.652.090,0 | 2.065.209,0 |
| `GIA_VAT` | 20.652.090,0 + 2.065.209,0 | **22.717.299,0** |

Kiểm nhanh bằng hệ số tổng: 14.062.816,6 × 1,615416 = 22.717.299.

### B7 – Ghi kết quả

`al_gia_vat = 22.717.299`, `al_gia_ban = 20.652.090`, `rate = 20.652.090` (giá trước VAT), `al_bom_result` chứa JSON đầy đủ (bucket, cost template, trace, lines, errors). Tổng tiền Quotation cha được tính lại.

**Đối chiếu golden.** `run_test.py` kỳ vọng 22.717.289 và chấp nhận lệch dưới 1.000 đ. Lệch 10 đ nguồn từ việc người ghi golden làm tròn `unit_qty` từng dòng (vd 2,8961 thay vì 2,896128) rồi cộng dồn; engine giữ độ chính xác số thực đầy đủ. Khi cộng tay `lines[].line_total` có thể lệch vài đồng so với bucket; số chính thức là bucket và cost template.

## 7. Ví dụ 2 – Cửa 4 cánh + 2 ô kính cố định + vách kính `BOM-CDMQ-4C`

**Đầu vào**: `W_mm = 3600`, `H_mm = 3200`, `n_panel = 4`, `TransomHeightTop = 600`, `TransomHeightBottom = 400`, `SideLiteWidth = 800`, `SideLiteHeight = 2800`, màu `DARK`, `installation_height_m = 15`. Hệ thống giống 2C. Khác biệt quan trọng: `lookup_rule('RULE-HEIGHT-MULT', 15)` = **1,2** và `lookup_rule('RULE-BANLE-QTY', 3200)` = 4 bản lề mỗi cánh.

| slug (nhóm) | width (mm) | height (mm) | `unit_qty` | qty | `total_qty` | `line_total` |
| --- | --- | --- | --- | --- | --- | --- |
| `khung_ngang_tren`, `_duoi` (mỗi dòng) | `W_mm` = 3600 | – | 3,6×1,257 = 4,5252 | 1 | 4,5252 | 511.348 |
| `khung_dung_trai`, `_phai` (mỗi dòng) | `H_mm` = 3200 | – | 4,0224 | 2 | 8,0448 | 909.062 |
| `do_ngang_tren`, `_duoi` (mỗi dòng) | 3600 − 96 = 3504 | – | 4,4045 | 1 | 4,4045 | 497.712 |
| `canh_dung_c1..c4` (mỗi dòng) | `(H-TransomTop-TransomBottom) - OFFSET_FRAME` = 2152 | – | 2,152×1,350 = 2,9052 | 2 | 5,8104 | 656.575 |
| `canh_ngang_c1..c4` (mỗi dòng) | 3600/4 − 48 = 852 | – | 1,1502 | 2 | 2,3004 | 259.945 |
| `kinh_fixed_top` | 3600 − 100 = 3500 | 600 − 50 = 550 | 1,9250 m² | 1 | 1,925 | 2.213.750 |
| `kinh_fixed_bottom` | 3500 | 400 − 50 = 350 | 1,2250 m² | 1 | 1,225 | 1.408.750 |
| `kinh_canh` | 3600/4 − 90 = 810 | 3200−600−400−90 = 2110 | 1,7091 m² | `n_panel` = 4 | 6,8364 | 7.861.860 |
| `kinh_sidelite` | 800 − 100 = 700 | 2800 − 100 = 2700 | 1,8900 m² | 1 | 1,89 | 2.173.500 |
| `nep_kinh_canh` (C3211-20) | 2×(810+2110) = 5840 | – | 5,84×0,312 = 1,8221 | `2*n_panel` = 8 | 14,5766 | 1.647.160 |
| `nep_kinh_sidelite` (C3211-20) | 2×(700+2700) = 6800 | – | 2,1216 | 2 | 4,2432 | 479.482 |
| `keo_canh` (KEO-TT-01) | 5840 | – | 5,84 m | 4 | 23,36 | 1.051.200 |
| `keo_sidelite` (KEO-TT-01) | 6800 | – | 6,8 m | 1 | 6,8 | 306.000 |
| `gioang` | 3600+3600+2×3200 = 13600 | – | 13,6 m | 1 | 13,6 | 17.000 |
| `vit` | – | – | 1 | `15*n_panel + 20` = 80 | 80 | 68.000 |
| `tay_nam` | – | – | 1 | 4 | 4 | 840.000 |
| `khoa` | – | – | 1 | 1 | 1 | 350.000 |
| `ban_le` | – | – | 1 | 4×4 = 16 | 16 | 2.880.000 |

**Bucket**: `VL_NHOM` 9.628.966,9 · `VL_KINH` 13.657.860 · `VL_VTP` 1.442.200 · `VL_PK` 4.070.000 → `TONG_VL` **28.799.026,9**.

**Cost Template** (h = 1,2):

| `line_code` | Thay số | Kết quả |
| --- | --- | --- |
| `TONG_M2` | 3,6 × 3,2 | 11,520 m² |
| `NC_SX` | 0,08 × 28.799.026,9 | 2.303.922,1 |
| `NC_LD` | 0,12 × 28.799.026,9 × 1,2 | 4.147.059,9 |
| `TONG_NC` |  | 6.450.982,0 |
| `OH_VC` | 0,03 × 28.799.026,9 | 863.970,8 |
| `OH_QLY` | 0,03 × (28.799.026,9 + 6.450.982,0) | 1.057.500,3 |
| `TONG_OH` |  | 1.921.471,1 |
| `GIA_THANH` |  | **37.171.479,9** |
| `PROFIT` | 0,16 × 37.171.479,9 | 5.947.436,8 |
| `GIA_BAN` |  | **43.118.916,7** |
| `DON_GIA_M2` | 43.118.916,7 / 11,52 | 3.742.961,5 đ/m² |
| `VAT` | 0,10 × 43.118.916,7 | 4.311.891,7 |
| `GIA_VAT` |  | **47.430.808,4** |

Kiểm nhanh: 28.799.026,9 × 1,646959 = 47.430.808. Đúng golden `47.430.808` (lệch 0).

Bốn điểm đáng chú ý: (1) hai kiểu rule chọn mã cùng dùng, THRESHOLD cho nẹp và LOOKUP cho keo; (2) `lookup_rule` xuất hiện ở hai chỗ khác bản chất, số bản lề và hệ số nhân công; (3) tham chiếu chéo dòng (`gioang`, nẹp, keo); (4) **màu DARK không làm giá tăng 8%** trong ca này, vì binding đang `exact_match` và bảng giá không gắn dimension (xem mục 4.5). Lưu ý `run_test.py` in ra dòng "Price Multiplier: DARK ×1.08" và "Scrap Injection", nhưng hai dòng đó chỉ là chú thích in ra, không phản ánh điều engine đang làm; con số golden khớp khi **không** nhân hệ số màu và **không** cộng hao hụt.

## 8. Hai biến thể để thấy các công tắc ảnh hưởng giá thế nào

Tôi tính từ logic đọc được trong mã, chưa chạy trên Frappe, nên coi là ước lượng cần xác nhận.

**A. Bật hao hụt (`AL Bom Set.apply_scrap_pct = 1`).** `total_qty ×= (1 + scrap_pct/100)` với `scrap_pct` từ `AL Material Category`: NHOM 3, KINH 5, VTP 2, PK 0. Phụ kiện có `category` trống nên không bị áp. Lưu ý vít thuộc VTP nên `28 × 1,02 = 28,56` cái, ra số lẻ.

| Ca | `TONG_VL` gốc → mới | `GIA_VAT` gốc → mới | Chênh |
| --- | --- | --- | --- |
| 2C | 14.062.817 → 14.542.957 | 22.717.299 → 23.492.925 | +775.626 |
| 4C | 28.799.027 → 29.799.633 | 47.430.808 → 49.078.765 | +1.647.957 |

**B. Bật `multiplier_chain` cho 4C (màu DARK ×1,08).** Các dòng nhôm tra qua `price_base_item` được nhân 1,08; hai dòng nẹp (Rule) vẫn giữ 113.000 vì giá lấy thô ở batch #6. `VL_NHOM` tăng từ 9.628.967 lên 10.229.153, `TONG_VL` = 29.399.213, `GIA_VAT` = **48.419.290** (+988.482). Nếu nẹp cũng được nhân (như tài liệu cũ trong repo mô tả "mọi dòng nhôm") thì chênh thêm khoảng 280.000 đ. Để biết đúng, chạy 4C trên site sau khi đổi chế độ và xem `lines[].unit_price` của `nep_kinh_*`. Ca 2C dùng màu WHITE (×1,0) nên không đổi.

Cả hai biến thể đều làm số golden hiện tại sai, nên sau khi bật phải cập nhật giá trị kỳ vọng trong `run_test.py`.

## 9. Checklist cấu hình để một sản phẩm tính được giá

| # | Việc | DocType | Kiểm gì |
| --- | --- | --- | --- |
| 1 | Khai biến | AL Variable Library | `var_name`, `is_system`, `source_doctype.source_field`, `default_value` |
| 2 | Hồ sơ nhôm | AL Profile System | 4 offset |
| 3 | Loại sản phẩm | AL Product Type | `nc_pct`, `nc_ld_rate`, `profit_margin` (lưu số nguyên) |
| 4 | Chiều giá | AL Pricing Dimension + Variable Dimension Mapping | field `custom_pd_*` trên Item Price, `material_category` |
| 5 | Nhóm vật tư | AL Material Category | `default_scrap_pct`, `has_weight` |
| 6 | Kính | AL Glass Master | `total_thick_mm`, `glass_type`, `max_area_m2` |
| 7 | Cách tính số lượng | AL Quantity Calc Method | `calc_fn` hoặc dùng pattern tích hợp sẵn |
| 8 | Rule tra bảng | AL Rule (`result_type = NUMBER`) | dải nối liền, không để khe hở |
| 9 | Rule chọn mã | AL Rule (`result_type = ITEM`) | dải + mã kết quả |
| 10 | Nhóm chi phí | AL Cost Bucket | `bucket_code` khớp `cost_bucket` của mọi dòng BOM |
| 11 | Giá thành | AL Cost Template + Item | tên `line_code` đúng và duy nhất, cờ `is_final_price` / `is_pre_vat_price` |
| 12 | Phụ kiện | AL Accessory Set + Item | `qty_formula`, `unit_price` |
| 13 | Sản phẩm | AL Bom Set + Bom Item | mỗi dòng đủ `slug`, `category`, `calc_pattern`, `cost_bucket`, `price_base_item` (nhôm), công thức `width/height/qty` |
| 14 | Giá | Item Price | mỗi mã có ít nhất 1 dòng còn hiệu lực; nên có 1 dòng trần |
| 15 | Nối BOM | AL BOM | `bom_set`, `default_cost_template` |
| 16 | **Tạo và xuất bản version** | AL BOM Version | bắt buộc, B0 sẽ `throw` nếu chưa có |
| 17 | Gán vào báo giá | Quotation Item | `al_bom`, `al_bom_vars` |

**Sự cố hay gặp**

| Triệu chứng | Nguyên nhân | Cách sửa |
| --- | --- | --- |
| `BOM … chưa có phiên bản nào` | B0 không thấy version | Tạo và xuất bản version trên form BOM |
| Một dòng giá = 0 | Thiếu Item Price, xem `errors.bom_items` | Thêm dòng giá hoặc dòng trần |
| `NC_LD` = 0 | `installation_height_m` rơi vào khe của `RULE-HEIGHT-MULT` | Nối liền dải rule |
| Toàn bộ BOM dừng với lỗi chia cho 0 | `W_mm`, `H_mm` hoặc `n_panel` = 0 | Kiểm đầu vào; dùng `safe_div` trong công thức mới |
| Ô giá cuối = 0 dù các dòng đều đúng | `line_code` gõ sai hoặc đổi tên mà không đặt cờ | Soi tên, đặt `is_final_price` / `is_pre_vat_price` |
| Đổi Bom Set mà giá báo giá cũ không đổi | Đúng thiết kế, đang đọc snapshot | Tạo version mới rồi tính lại |
| Giá trị cấu hình mới chưa áp dụng | Cache `Formula Global Variable` TTL 60 s, hoặc `set_value` không xoá cache | Chờ tối đa 60 s |
| Dòng kẹt `Queued` | Job nền (queue `long`) không chạy | Kiểm worker, Error Log, bấm tính lại |

## 10. Phụ lục

**Cách kiểm lại trên site thật**: `bench --site <site> execute alumglass.run_test.main` (ghi dữ liệu thật vào Quotation, không chạy trên production), cần site đã cài cả `alumglass` và `formula_builder`, đã migrate và đã `seed_all()`.

**Bản đồ mã nguồn chính**

| Tệp | Vai trò |
| --- | --- |
| `alumglass/engine/bom_orchestrator.py` (2.747 dòng) | B0→B7, tra giá composite, rule, roundup |
| `alumglass/engine/composite_pricing.py` | `best_partial_match`, lọc hiệu lực, túi cảnh báo |
| `alumglass/engine/engine_cache.py` | Cache `FormulaEngine` theo vân tay công thức |
| `alumglass/formula_handlers.py` | `lookup_calc_pattern`, 14 pattern tích hợp |
| `alumglass/fb_handlers.py` | Đăng ký `aluminum_price_composite`, `glass_master_data` |
| `alumglass/al_formula_rules/.../al_calculation_rule.py` | `_resolve_threshold` |
| `alumglass/setup/seed_demo_data.py` | Dữ liệu mẫu, giá, rule, cost template |
| `formula_builder/formula_utils/engine_core.py` | DAG, `calculate`, xử lý chia 0 |
| `formula_builder/formula_utils/topo.py` | Dò định danh, sắp xếp topo |

**Giới hạn của bản tài liệu này.** Chưa chạy trên site Frappe nên mọi con số là tính lại độc lập (hai ca gốc khớp golden). Lớp giao diện `quotation.js`, `get_live_context` và `binding_scope` đã được đọc ở mục 11 (đọc mã, chưa chạy giao diện thật); các điểm ở mục 11 bổ sung và đính chính một số chỗ ở mục 1 và mục 3. Hai biến thể ở mục 8 là ước lượng từ mã, cần chạy thử để xác nhận.

## 11. Bổ sung sau khi đọc sâu giao diện và lớp resolve của Formula Builder

Đã đọc `quotation.js` (2.351 dòng), `get_live_context` (`api/formula_builder.py:275`), `binding_scope.py`, `resolve_bindings_with_deps` và `handler linked_doctype_field` (`data_source_registry.py`), cùng các patch seed binding. Phần mô tả giao diện trong `docs/huong-dan-tinh-gia-full-flow.md` khớp mã (cùng số dòng). Dưới đây là những điểm mới hoặc cần đính chính.

### 11.1 Tám phát hiện

| # | Phát hiện | Hệ quả | Chỗ trong mã |
| --- | --- | --- | --- |
| 1 | Hằng số `VAT_RATE`, `OH_VC_PCT`, `OH_QLY_PCT` được patch `v28_9` seed thành binding `constant` mang **bản sao giá trị** (`source_config = {"value": …}`). Không có cơ chế đồng bộ từ `Formula Global Variable` sang binding. B1.4 chạy sau B1.2 và ghi đè | Sửa `VAT_RATE` ở `Formula Global Variable` sau khi đã seed binding không đổi giá. Phải sửa cả binding cùng tên. Kiểm: lọc `Formula Variable Binding` theo `variable_name` | `patches/v28_9/seed_fvb_from_variable_library.py`; `formula_global_variable.py` chỉ xoá cache; thứ tự trong `b1_gather_inputs` |
| 2 | Biến hệ thống `OFFSET_*`, `NC_SX_PCT`, `NC_LD_PCT`, `PROFIT_MARGIN` đọc **sống**: scope là `AL Bom Set` hiện hành (`_get_bom_set` đọc `AL BOM.bom_set`, không dùng snapshot) rồi `frappe.db.get_value` trên `AL Profile System` / `AL Product Type` hiện hành | Đổi offset hoặc % lợi nhuận hôm nay làm đổi kết quả khi tính lại báo giá cũ dù version giữ nguyên. Snapshot chỉ chụp tên `profile_system`, `product_type`, các dòng BOM, cost template, pricing dimension | `_get_bom_set`, `al_bom_version._take_snapshots` |
| 3 | `get_live_context` gọi `assert_read_perm` trên `AL Bom Set`. Thiếu quyền `read` thì `PermissionError` bị bắt ở `except Exception` ngoài cùng, hàm trả `success: False`, `_resolve_fb_context` trả `{}` | Người dùng thiếu quyền đọc Bom Set âm thầm rơi về resolver 1.3 (Variable Library). Hằng số khi đó lấy từ `Formula Global Variable`, người có quyền thì lấy từ binding. Nếu hai nguồn lệch (phát hiện 1) thì hai người có thể ra hai giá. Chỉ có `log_error` "Formula Builder: get\_live\_context" | `_helpers.assert_read_perm`; `get_live_context:417`; `_resolve_fb_context` |
| 4 | `get_live_context` còn trả **mọi field vô hướng của `AL Bom Set`** (`source: field`), và B1.4 gộp hết vào `self.inputs` | Tên field của Bom Set (`set_code`, `profile_system`, `apply_scrap_pct`…) trở thành biến trong context. FB ghi đè `extra_vars` (1.1) và hằng số (1.2); các bước 1.4b, 1.5 ghi đè lại FB | `get_live_context` bước 5; `_resolve_fb_context` |
| 5 | Dialog ghi override `_bom_set`, `_bom_name`, `_brand` vào `al_bom_vars` nhưng engine và API **không đọc** chúng | Đổi Bom Set trong dialog không đổi giá; cấu trúc luôn lấy từ snapshot của version ghim. Ba khoá này chỉ lọt vào `inputs` như biến thừa | grep toàn bộ `.py`; `b1_gather_inputs:442-460` |
| 6 | Nút **Tính giá** cấp form đặt `al_gia_ban = ct.GIA_BAN`, `al_gia_vat = ct.GIA_VAT`, `rate = ct.GIA_BAN` theo **tên** dòng, và \` |  | 0\` khi thiếu. Server B7 chọn dòng theo **cờ** |
| 7 | Hai comment cũ nói đường đồng bộ "chưa có `errors`" (`quotation.js:2206`, docstring `_normalize_bom_response`) | Sai: `_build_response` đã trả `errors`; client đọc qua `collect_calc_errors` | `bom_orchestrator._build_response` |
| 8 | `sales_order.js` (59 dòng) chỉ gắn trình soạn công thức Formula Builder lên `custom_formula…` | Không liên quan đến tính giá AlumGlass | `sales_order.js` |

**Đính chính mục 1, nguyên tắc 3.** Bất biến nhờ snapshot chỉ đúng cho cấu trúc: dòng BOM, công thức, cost template, định nghĩa pricing dimension. Các dữ liệu sau luôn **sống** tại lúc tính: `Item Price`, `Item.weight_per_unit`, `AL Rule`, `AL Glass Master`, `AL Material Category`, `Formula Global Variable`, binding, `AL Profile System`, `AL Product Type`, và `price_multiplier` của `AL Color Standard` (đọc bằng `get_cached_value`). Tính lại một báo giá nháp sau khi đổi giá hoặc tham số sẽ ra số mới.

### 11.2 Luồng B1.4 chi tiết: `get_live_context` và `binding_scope`

1. `_resolve_fb_context` chọn scope: `AL Bom Set` của BOM, nếu không có thì `Quotation Item`. Gọi `get_live_context({current_doctype, current_docname})`.
2. `get_live_context` kiểm quyền `read` trên doc đó, rồi lấy `fieldname` từ scope (rỗng nếu không có).
3. `get_scope_bindings(doctype, field)`: DB lọc `is_active = 1` và `applies_to_doctype ∈ ["", doctype]`, sắp `resolve_priority` tăng dần. Python lọc tiếp theo `binding_matches_scope`: binding global (doctype và field đều rỗng) áp mọi nơi; khớp doctype thì áp nếu binding không set field, hoặc khớp field, hoặc caller không đưa field; binding chỉ set field mà không có doctype thì **không bao giờ** áp. Lỗi truy vấn trả danh sách rỗng, không báo.
4. Nạp doc bằng `get_cached_doc`.
5. `resolve_bindings_with_deps`: đồ thị chỉ có cạnh cho binding `computed` (qua `dependencies`); sắp Kahn; có vòng thì ghi log và sắp theo `resolve_priority`. Mỗi binding gọi handler theo `source_type`. Handler lỗi hoặc trả `None` thì dùng `default_value`; riêng `PermissionError` được ném lên.
6. Dựng danh sách biến: mỗi binding một mục, thêm các field vô hướng của doc, thêm `Formula Global Variable` CONSTANT còn thiếu (chỉ khi chưa có binding cùng tên).
7. AlumGlass lọc kết quả: bỏ `None`, dict, list và chuỗi rỗng; giá trị không phải field thì ép `float` nếu được (vì `linked_doctype_field` có thể trả `Decimal` hoặc chuỗi số).

`linked_doctype_field` gọi `frappe.db.get_value(target_doctype, <tên doc liên kết>, target_field)`. `link_field` để trống thì tự dò field Link đầu tiên trỏ tới `target_doctype`. Không có liên kết thì trả `fallback`. Theo seed, các biến hệ thống ánh xạ như sau:

| Biến | Doc nguồn | Field |
| --- | --- | --- |
| `OFFSET_FRAME`, `OFFSET_GLASS`, `OFFSET_FIXED` | `AL Profile System` (qua `AL Bom Set.profile_system`) | `offset_frame`, `offset_glass`, `offset_fixed` |
| `OFFSET_DO_NGANG` | `AL Profile System` | `offset_crossbar` |
| `NC_SX_PCT`, `NC_LD_PCT`, `PROFIT_MARGIN` | `AL Product Type` (qua `AL Bom Set.product_type`) | `nc_pct`, `nc_ld_rate`, `profit_margin` |

Binding giá `COMPOSITE_MATERIAL_PRICE` cũng là binding global nên `get_live_context` gọi nó khi chưa có dòng BOM nào. Handler `aluminum_price_composite` thấy `price_base_item` rỗng thì trả 0 mà không cảnh báo, và 0 đó đi vào `inputs` như một biến.

**Thứ tự ưu tiên thực tế của một biến sau B1** (bước sau thắng bước trước): `extra_vars` < `Formula Global Variable` < FB (`get_live_context`) < biến hệ thống 1.3 chỉ điền chỗ thiếu < `system_variables` của profile (1.4b) < `al_bom_vars` do người dùng nhập (1.5) < resolve lại theo `_profile_system` (1.5c, nếu có override) < mặc định biến người dùng (1.6, chỉ điền chỗ thiếu) < chuẩn hoá phần trăm (1.7).

### 11.3 Giao diện `quotation.js`

| Việc | Hành vi trong mã |
| --- | --- |
| Nạp | `hooks.py` `doctype_js`: Quotation → `quotation.js`, Sales Order → `sales_order.js`. Không nạp toàn trang |
| Ba chỗ gọi `calculate_bom` | `ItemParamDialog._exec_calculate_bom` (1423), `BOMDialog.calculate` (1751), `_calc_all_items` (2191). Cả ba dẫn tới B7 ghi giá; không có chế độ tính thử không ghi |
| Chỗ chỉ đọc | `get_result_display` (1487, 1853, 2308); nút **Preview giá** cấp form |
| Đồng bộ trước khi tính | `_sync_row_to_db` ghi `al_bom`, `al_bom_version`, `al_bom_vars`, `item_code`, `item_name` bằng `frappe.client.set_value`, vì server đọc từ DB. Dòng mới chưa có trong DB thì `frm.save()` cả báo giá. Sau `set_value`, client cập nhật `frm.doc.modified` để tránh `TimestampMismatchError` |
| Chống dội khi gõ | `_schedule_auto_preview` debounce 700 ms; `_preview_seq` loại kết quả preview cũ về muộn; `_dialog_ready` và `_dialog_open` chặn preview thừa lúc mở và sau khi đóng |
| Job nền | Server đặt `al_calc_status` `Queued → Running → Success/Failed`, publish realtime `alumglass_bom_calc_done` tới đúng người bấm; client lọc theo `job_id` |
| Chặn báo giá đã chốt | Nút **Tính giá** chỉ hiện khi `docstatus = 0`, nhưng chốt thật ở server: `assert_quotation_item_editable` ném lỗi khi docstatus 1 hoặc 2, gọi ở đầu `calculate_bom` và sát lệnh ghi của B7 |

**`al_bom_vars` do dialog ghi** (`_save`): biến từ các control; `glass_master_map` và `color_master_map` (chỉ khi có ít nhất một ô được chọn); `extra_vars` (`Float`/`Int` qua `parseFloat`, NaN thành 0; `Check` thành boolean); các override qua `_collect_overrides` (chỉ ghi khi khác mặc định của BOM). Giá trị rỗng không được ghi, nên biến bị xoá trong dialog biến mất khỏi JSON và engine dùng mặc định. Dialog cũng đặt `item_code` / `item_name` theo `representative_item` của BOM nếu khác giá trị hiện có.

**Khoá trong `al_bom_vars` mà engine thật sự đọc:**

| Khoá | Tác dụng |
| --- | --- |
| `extra_vars` | Gộp vào `inputs` (bước 1.1) |
| mọi khoá phẳng (`W_mm`, `n_panel`, …) | Vào `inputs` (1.5), thắng mọi nguồn khác |
| `_accessory_set` (hoặc `accessory_set`) | Chọn bộ phụ kiện, đọc doc sống |
| `glass_master`, `glass_master_map` | Kính toàn BOM và kính theo vị trí |
| `aluminum_color`, `color_master_map` | Màu toàn BOM và màu theo vị trí |
| `_profile_system` | Resolve lại biến hệ thống theo profile này |
| `_cost_template` | Dùng doc `AL Cost Template` sống thay cho snapshot ở B6 |
| `_bom_set`, `_bom_name`, `_brand` | **Không ai đọc** |

**Tính hàng loạt (`_calc_all_items`).** Lọc dòng thật, kiểm từng dòng có `al_bom`, `al_bom_version`, `al_bom_vars`; thiếu một dòng thì chặn cả lượt và liệt kê lỗi, không tính dòng nào. Sau đó tính tuần tự từng dòng: đồng bộ DB, gọi `calculate_bom`; nếu trả `async` thì đặt `Queued`; nếu đồng bộ thì đặt `Success`, `al_bom_result`, `al_gia_ban`, `al_gia_vat`, `rate`. Cảnh báo của engine được gom vào một popup cuối lượt (có lỗi thì tiêu đề đỏ, chỉ cảnh báo thì cam).

**Việc nên làm sau phát hiện này:** (a) kiểm trên site xem `Formula Variable Binding` có binding `constant` trùng tên `VAT_RATE`, `OH_VC_PCT`, `OH_QLY_PCT` không, và giá trị có khớp `Formula Global Variable` không; (b) cấp quyền `read` trên `AL Bom Set` cho mọi vai trò được tính giá; (c) nếu đổi tên `GIA_BAN` / `GIA_VAT` trong Cost Template thì phải sửa `_calc_all_items` để đọc theo cờ như server.

## 12. Tài liệu A–Z: `quotation.js` và các phần liên quan

Mục này mô tả từng hàm của `alumglass/alumglass/doctype/overrides/quotation.js` (2.351 dòng) theo thứ tự trong file: nó nhận gì, làm gì, trả gì, để làm gì. Số dòng là của HEAD `eb22946`. Phần server liên quan nằm ở 12.9.

### 12.1 Tệp được nạp thế nào và nó dựng những gì

- `hooks.py` khai `doctype_js = {"Quotation": "alumglass/doctype/overrides/quotation.js", "Sales Order": "…/sales_order.js"}`. Frappe chỉ nạp tệp này khi mở form Quotation, không nạp toàn trang.
- Các tệp nạp toàn trang qua `app_include_js` mà `quotation.js` dùng ké: `grid_placeholder.js` (`alumglass.grid_placeholder.set_column`), cùng các tệp `formula_setup.js`, `cost_template.js`, `excel_io.js`, `report/*.js` (không dính tới luồng tính giá của báo giá).
- Tệp dựng ba lớp đối tượng dưới `window.alumglass`:

| Tên | Loại | Vai trò |
| --- | --- | --- |
| `alumglass.render_bom_result_display`, `esc`, `format_trace`, `raw_to_display`, `*_calc_error*` | hàm dùng chung | Vẽ bảng kết quả và xử lý lỗi, dùng chung cho dialog tham số và dialog kết quả |
| `alumglass.quotation._persist_row`, `_sync_row_to_db` | hàm | Ghi dữ liệu dòng xuống DB trước khi server tính |
| `alumglass.quotation.ItemParamDialog` | class | Dialog tham số BOM cho một dòng, kèm preview giá tự động |
| `alumglass.BOMDialog` | class | Dialog xem và tính kết quả cho một dòng đã có BOM |
| `frappe.ui.form.on("Quotation"…)`, `("Quotation Item"…)` | handler sự kiện form | Gắn nút lên dòng, nút cấp form |
| `_attach_row_actions`, `_calc_all_items`, `_preview_all_items`… | hàm module | Tính và xem giá hàng loạt |

**Ranh giới vai trò.** Trình duyệt chỉ gom tham số, gọi API và hiển thị. Mọi phép tính (công thức, tra giá, cost template) nằm ở server; trình duyệt không có công thức nào. Hai API quyết định: `alumglass.api.calculate_bom` (tính và ghi) và `alumglass.api.get_result_display` (chỉ đọc kết quả đã lưu, đã gắn nhãn).

### 12.2 Bộ vẽ kết quả và xử lý lỗi (dòng 35–440)

| Hàm (dòng) | Vào → ra | Mục đích và cách hoạt động |
| --- | --- | --- |
| `render_bom_result_display(display, opts)` (35) | display model → chuỗi HTML | Hàm vẽ duy nhất của kết quả. `opts`: `collapsible` (mặc định có), `show_trace`, `compact` (font 11 px), `title`. Vẽ tuần tự: thanh tóm tắt (nếu `summary.calculated`: giá bán, ô thứ hai in `summary.gia_vat`, số dòng vật tư), bảng **Chi tiết vật tư**, bảng **Tổng theo nhóm chi phí**, bảng **Chi phí chế tạo** (cột Khoản mục, Công thức, Diễn giải, Giá trị, ĐVT). Chưa có dữ liệu thì in "Chưa có kết quả tính giá" |
| (trong bảng vật tư) |  | Cột Trọng lượng chỉ hiện `kg/m` khi dòng có `has_weight` và `weight_per_unit > 0`, còn lại là "—". Cột Số lượng hiện `qty` kèm `(unit_qty/đv)`. Năm cột phụ (màu, nơi cấp vật tư, vị trí lắp, góc cắt, ghi chú) chỉ thêm khi ít nhất một dòng có giá trị, để bảng gọn với BOM đơn giản. Dòng cost template là tổng phụ (`is_subtotal`) thì in đậm, nền vàng nhạt |
| `esc(s)` (204) | chuỗi → chuỗi | Thoát `& < > " '`. Mọi nhãn từ DB đều đi qua hàm này trước khi vào HTML để chống XSS |
| `format_trace(trace)` (215) | chuỗi trace → chuỗi đẹp | Ba bước regex: (1) `TOKEN=0.08` đổi thành `TOKEN(0.08)`; (2) `TOKEN(0.08)` với giá trị trong (0,1) đổi thành `TOKEN(8%)`; (3) số trong ngoặc thêm dấu phân cách nghìn. Chỉ là định dạng hiển thị. Bước (2) áp cho mọi token có giá trị thập phân nhỏ hơn 1, kể cả khi đó không phải phần trăm |
| `is_error_trace(s)` (251) | chuỗi → bool | Nhận diện stack trace Python/JS: cụm `Traceback (most recent call last)`, mẫu `File "…", line N`, mẫu `at hàm (`, hoặc từ 2 dòng bắt đầu bằng `raise`/`File "`/`at` trở lên |
| `sanitize_calc_error(error)` (266) | chuỗi hoặc object → `{message, trace}` | Làm sạch lỗi trước khi hiện. Rút `.message` nếu là object, bỏ `[object Object]`. Là stack trace thì thay bằng câu "Tính giá thất bại. Vui lòng thử lại hoặc báo quản trị." và ghi trace ra `console.error`. Câu ngắn thì giữ nguyên, cắt ở 500 ký tự |
| `is_human_message(text)` (290) | chuỗi → bool | Quyết định câu server có đọc được không. Loại: stack trace; chuỗi chứa `error`, `exception`, `traceback`, `None`, `null`; chuỗi một token hoặc snake\_case. Nhận: câu có dấu tiếng Việt; câu không dấu thì cần từ 20 ký tự và từ 3 từ |
| `calc_error_message(key, raw, group)` (307) | khoá, nội dung, nhóm → câu | Chọn câu hiển thị. Nội dung server đọc được thì dùng nguyên văn (cắt 500). Không thì dịch theo khoá: khoá chứa `__max_area_exceeded` ra câu kính vượt khổ kèm slug. Khoá lạ ra câu chung theo nhóm (`cost_template` hoặc vật tư); khoá kỹ thuật không bao giờ lộ ra màn hình |
| `calc_error_severity(key, raw)` (326) | → `"warning"` hoặc `"error"` | Là `warning` nếu khoá chứa `__max_area_exceeded`, chứa `__warn`, hoặc nội dung bắt đầu bằng "cảnh báo" hay "warning". Mọi trường hợp khác là `error`. Hệ quả: các khoá cảnh báo của engine như `thieu_gia_item:<mã>` không có `__warn` nên hiện màu đỏ như lỗi |
| `collect_calc_errors(errors)` (336) | `errors` → `[{key, message, severity}]` | Chuẩn hoá. Duyệt `errors.bom_items` và `errors.cost_template`: mảng thì khoá là `item_<i>`, object thì mỗi khoá một mục, chuỗi trần thì một mục khoá rỗng. Không có hai nhóm con thì coi mỗi giá trị của object là một mục. Chịu dữ liệu thiếu, không ném lỗi |
| `calc_errors_banner(errors)` (373) | → HTML | Banner dán trên bảng kết quả: đỏ nếu có lỗi, vàng nếu chỉ cảnh báo. Tồn tại sau khi đóng popup nên cảnh báo vượt khổ kính vẫn nhìn thấy |
| `notify_calc_errors(errors, opts)` (393) | → popup | `frappe.msgprint` cam hoặc đỏ. Có `opts.dedupe_key` thì lưu chữ ký (`severity:message` nối bằng `§`) vào `alumglass._calc_err_sig[key]`; chữ ký không đổi thì không hiện lại, trừ khi `opts.force`. Tránh popup lặp mỗi lần auto-preview chạy lại |
| `raw_to_display(raw)` (417) | `al_bom_result` thô → display model tối thiểu | Dự phòng khi `get_result_display` không trả được. Nhãn lấy luôn mã (`label = slug`), không có trace, không có công thức. `summary.gia_ban` đọc `cost_template.GIA_BAN` theo tên, `gia_vat` đọc `raw.gia_vat`. Dòng là tổng phụ nếu mã bắt đầu `TONG_`, `GIA_`, `VAT`, hoặc bằng `PROFIT` (đoán theo tên) |

### 12.3 Ghi dòng xuống DB trước khi tính (dòng 486–549)

**Vấn đề gốc (comment trong mã).** `frappe.model.set_value` chỉ đổi bản sao trong bộ nhớ trình duyệt. `calculate_bom` và `get_result_display` đọc dòng bằng `frappe.get_doc("Quotation Item", name)` từ DB. Không đồng bộ trước thì engine tính theo `al_bom_vars` cũ, nên đổi kính trong dialog mà giá và nẹp không đổi.

| Hàm | Làm gì |
| --- | --- |
| `_persist_row(frm, cdt, cdn, fields)` (486) | Dòng đã có trong DB (tên không bắt đầu `new-` và không `__islocal`): gọi `frappe.client.set_value(doctype, name, fieldname = fields)`. Với child table, Frappe nạp và `save()` cả chứng từ cha nên `modified` của cha trong DB tăng; hàm cập nhật `frm.doc.modified` (và `modified_by`) bằng giá trị server trả, chỉ khi giá trị mới lớn hơn, để lần bấm Save sau không báo `TimestampMismatchError`. Dòng mới chưa lưu thì không có tên thật: gọi `frm.save()` cả báo giá rồi tìm lại dòng theo `name`, nếu không thấy thì theo `idx`. Trả Promise của tên thật |
| `_sync_row_to_db(frm, cdt, cdn)` (536) | Đọc dòng từ bộ nhớ (`frappe.get_doc`) và gọi `_persist_row` với năm field: `al_bom`, `al_bom_version`, `al_bom_vars` (mặc định `"{}"`), `item_code`, `item_name`. Mọi chỗ gọi `calculate_bom` hay mở `BOMDialog` đều đi qua hàm này |

### 12.4 `ItemParamDialog`: dialog tham số BOM cho một dòng (dòng 551–1686)

**Mục đích.** Cho người dùng chọn BOM, version, kính theo vị trí, màu theo vị trí, các biến đầu vào và biến mở rộng của **một** dòng báo giá, xem giá thử ngay trong dialog, rồi ghi tất cả vào `Quotation Item.al_bom_vars` (JSON). Dialog không chứa công thức nào: danh sách biến, nhãn, kiểu, mặc định đều do server trả.

**Trạng thái trong đối tượng (constructor, 552).** `frm`, `child_doc` (dòng đang sửa); `dialog` (đối tượng `frappe.ui.Dialog`); `_var_controls`, `_glass_controls`, `_color_controls` (các control đã tạo, để `_save` đọc lại); `_current_vars`; `_bom_meta` (kết quả `get_variable_set_for_bom`); `_realtime_handler`; `_preview_seq` (số thứ tự preview, chống kết quả về muộn); `_debounced_auto_preview`; hai cờ `_dialog_ready` (đã nạp xong lần đầu) và `_dialog_open` (dialog đang mở). Hai cờ này có lý do cụ thể: gán giá trị mặc định lúc mở dialog cũng kích `onchange`, nếu không chặn sẽ bắn một preview thừa; và nếu debounce còn treo khi dialog đã đóng, preview sẽ âm thầm ghi DB, làm `modified` của báo giá cha tăng mà form không biết, dẫn tới `TimestampMismatchError` ở lần Save sau.

#### Dữ liệu dialog nhận từ server: `alumglass.api.get_variable_set_for_bom(bom_code)`

| Khối trả về | Cách server dựng |
| --- | --- |
| Thông tin BOM | Kiểm quyền đọc `AL BOM`; đọc `AL BOM` → `AL Bom Set`. Trả `bom_code`, `bom_name`, `bom_set_code`, `variable_set_code`, hệ profile, hãng (`brand`), bộ phụ kiện mặc định, `cost_template_code`, và `item_code`, `item_name`, `item_image` của `representative_item` |
| `variables` (người dùng) | Mỗi dòng của `AL Variable Set`: nhãn, kiểu, `link_doctype`, `select_options` lấy từ `AL Variable Library` (nguồn chính), dự phòng từ field trên dòng Variable Set; `default_value` ưu tiên giá trị trên dòng Variable Set rồi mới tới Library |
| `variables` (hệ thống) | Mọi biến `is_system = 1` của Library, `sort_order = 999`. Sau đó **phủ giá trị hệ profile vào `default_value`**: child table `system_variables` của `AL Profile System` thắng, dự phòng bốn field `offset_*`. Nên ô `OFFSET_FRAME` trong dialog hiện đúng offset của profile đang chọn |
| Cờ `is_pricing_dimension` | Đánh dấu biến nào có dòng trong `AL Variable Dimension Mapping`. Biến dimension không bắt buộc, để trống thì engine bỏ qua chiều đó khi khớp giá |
| `glass_groups` | Mỗi dòng BOM thuộc category kính gom theo "mã đại diện" (`glass_group_rep`). Mã đại diện là `AL Glass Master` thật thì `label = glass_name`, `default = rep`. Không phải mã thật thì `label` là nhãn slug, `default = ""` (bắt người dùng tự chọn) |
| `color_groups` | Mỗi dòng BOM Set **và** mỗi dòng phụ kiện có `default_color` (`color_group_rep`) tạo một nhóm, gắn nhãn theo `AL Material Category`; `label = color_name`, `default = rep`. Dòng không khai `default_color` thì không có ô chọn màu (màu cố định do admin chủ ý) |

#### Các hàm

| Hàm (dòng) | Làm gì |
| --- | --- |
| `show()` (574) | Chỉ gọi `_render_dialog()` |
| `_load_variable_set()` (579) | Không có `al_bom` thì đặt `_bom_meta = null` và trả `[]`. Có thì gọi `get_variable_set_for_bom`, lưu `_bom_meta`, trả `variables`. Lỗi mạng thì `_bom_meta = null` và `[]` |
| `_build_dialog_fields()` (606) | Trả danh sách field cố định: header sản phẩm; `al_bom` (Link, `onchange` → `_on_bom_change`); `al_bom_name`; `al_bom_version` (Link, lọc theo BOM đang chọn); `al_brand`; bốn field cấu hình `al_bom_set`, `al_accessory_set`, `al_profile_system`, `al_cost_template`; vùng `vars_container` (HTML, nơi vẽ biến động); bảng `extra_vars` (Link tới `AL Variable Library` lọc `is_system = 0`, Kiểu, Giá trị); vùng Export/Import; vùng `preview_html`. Vùng biến là một HTML container để đổi BOM chỉ vẽ lại vùng đó chứ không tạo lại dialog |
| `_render_dialog()` (692) | Dựng `frappe.ui.Dialog` cỡ lớn, rộng tối đa 80vw. **Nút "💾 Lưu"** gọi `_save()` rồi đóng; **nút "🖥️ Preview tính giá"** gọi `_save()` rồi `_run_preview(true)`. Khi dialog ẩn (`hidden.bs.modal`) đặt `_dialog_open = false` và `_cleanup_realtime()`. Sau khi hiện: `_populate_extra_vars`, `_setup_extra_vars_autofill`, rồi nạp Variable Set, vẽ vùng biến, điền thông tin BOM; 50 ms sau đặt `_dialog_ready = true`. Cuối cùng gắn `alumglass.excel_io.attach` lên bảng `extra_vars` và 300 ms sau gọi `_render_preview_panel` |
| `_render_bom_info(preserveExisting)` (753) | Điền sáu ô cấu hình. Mở dialog (`true`): ưu tiên override đã lưu trong `al_bom_vars` (`_bom_name`, `_bom_set`, `_accessory_set`, `_profile_system`, `_cost_template`, `_brand`), không có thì lấy mặc định của BOM. Đổi BOM (`false`): bỏ override cũ, về mặc định của BOM mới. Cuối cùng gọi `_render_product_header` |
| `_render_product_header(m)` (782) | Vẽ ảnh 56×56 và tên, mã sản phẩm từ `_bom_meta`; chưa chọn BOM thì hiện dòng nhắc chọn BOM. Chuỗi đi qua `_esc_html` |
| `_setup_extra_vars_autofill()` (807) | Hai handler uỷ quyền sự kiện trên lưới `extra_vars`: (1) khi chọn `var_name`, gọi `frappe.db.get_value("AL Variable Library", …, [var_type, select_options, link_doctype])` để tự điền cột Kiểu và nhớ options vào dòng; (2) mọi thay đổi ở ô nào trong lưới đều gọi `_schedule_auto_preview` |
| `_var_to_field(v, current_val)` (859) | Đổi một biến thành định nghĩa field Frappe. `fieldname = "al_var_" + var_name`; `default` = giá trị đã lưu nếu có, không thì `default_value`; `reqd = 0` nếu là pricing dimension, không thì `is_required`. Kiểu: `Float` (precision `"1"`), `Int`, `Data`, `Select` (thêm lựa chọn rỗng khi không bắt buộc), `Link` (theo `link_doctype`), `Check`, `Currency`, mặc định `Data` |
| `_render_vars_container(vars)` (894) | Xoá và vẽ lại toàn bộ vùng biến, gồm bốn mục thu gọn được (xem bên dưới) |
| `_annotate_var_name($cell, name)` (1105) | Thêm `(tên_biến)` nhỏ và tooltip cạnh nhãn, để người dùng thấy tên biến dùng trong công thức |
| `_make_var_control($grid, v, df)` (1117) | `frappe.ui.form.make_control` rồi `make_input`, `refresh`, `set_value(default)`; đăng ký `{var_name, ctrl}` vào `_var_controls` |
| `_populate_extra_vars()` (1140) | Đọc `extra_vars` trong `al_bom_vars` và nạp vào lưới; kiểu đoán bằng `_guess_var_type` |
| `_guess_var_type(val)` (1161) | boolean → `Check`; số nguyên → `Int`; số lẻ → `Float`; còn lại `Data` |
| `_on_bom_change()` (1170) | Chọn BOM mới: lấy `current_version` của BOM đó bằng `frappe.db.get_value` và đặt vào `al_bom_version`; ghi `al_bom` vào `child_doc` (chỉ trong bộ nhớ); nạp lại Variable Set, vẽ lại vùng biến, `_render_bom_info(false)`, rồi `_schedule_auto_preview` |
| `_vars_container()` (1190) | Trả `$wrapper` của field `vars_container` |
| `_schedule_auto_preview()` (1207) | Bỏ qua nếu dialog chưa sẵn sàng hoặc không mở. Ngược lại gọi `_mark_preview_stale`, rồi (tạo một lần) debounce 700 ms bằng `frappe.utils.debounce`; khi đến hạn mà dialog còn mở thì gọi `_run_preview()` (không `manual`) |
| `_mark_preview_stale()` (1220) | Chèn dải vàng "⏳ Tham số vừa đổi — đang tự động tính lại giá..." lên đầu vùng preview, không xoá kết quả cũ (tránh cảm giác dialog đứng). Có sẵn dải thì không chèn thêm |
| `_bind_auto_preview_listeners()` (1232) | Gắn `change` và `awesomplete-selectcomplete` cho mọi control (biến, kính, màu), gỡ listener cũ trước khi gắn. Gọi lại mỗi lần vẽ vùng biến vì control cũ đã bị huỷ |

**Bốn mục trong `_render_vars_container`** (mỗi mục bọc trong `<details>`, lưới 3 cột):

1. **Kính theo vị trí**: mỗi `glass_group` một ô Link tới `AL Glass Master`. Giá trị hiện: `glass_master_map[rep]`, rồi `glass_master` cũ, rồi `g.default`. Chưa có lựa chọn đã lưu mà đang hiện mã đại diện của BOM thì thêm dòng nhắc màu vàng: mã giữ chỗ thường chưa có Item Price, giá tạm 0 kèm cảnh báo thiếu giá.
2. **Màu sắc**: gom `color_groups` theo category, mỗi vị trí một ô Link tới `AL Color Standard` chỉ hiện bản ghi `is_representative = 1`. Giá trị hiện: `color_master_map[rep]`, rồi `aluminum_color` cũ, rồi `g.default`.
3. **Biến đầu vào**: các biến `is_system = 0` còn lại. Biến `glass_master` ẩn khi đã có `glass_groups`; `aluminum_color` ẩn khi đã có `color_groups`; `accessory_set` và `_accessory_set` luôn ẩn (đã có ô riêng ở mục Cấu hình BOM). Giá trị hiện: `al_bom_vars[var]` nếu có, không thì mặc định.
4. **Biến hệ thống (tự động)**: các biến `is_system = 1`, cùng cách điền giá trị, kèm nút "↺ Khôi phục mặc định biến hệ thống" đặt lại về `default_value` do server trả (đã phủ giá trị profile).

Chưa có Variable Set (hoặc chưa chọn BOM) thì hiện khung hướng dẫn dùng bảng "Biến mở rộng".

**Điểm cần biết 1: lưu dialog ghim biến hệ thống.** `_save` (12.5) ghi **mọi control có giá trị không rỗng** vào `al_bom_vars`, kể cả mục "Biến hệ thống". Các ô này không rỗng: `OFFSET_*` được phủ giá trị profile, `NC_SX_PCT` và `PROFIT_MARGIN` có `default_value` 8 và 16 trong Library. Vì `al_bom_vars` thắng mọi nguồn khác ở B1.5, **chỉ cần bấm Lưu hoặc Preview một lần là các giá trị này thành override cho dòng đó**. Sửa `AL Product Type` hoặc `AL Profile System` sau đó sẽ không đổi giá của dòng này nữa. Muốn bỏ ghim phải xoá ô thủ công; nút "Khôi phục" chỉ đặt lại giá trị không rỗng, nên không bỏ ghim được.

**Điểm cần biết 2: làm tròn.** Ô `Float` khai `precision: "1"`. Control Float chuẩn của Frappe làm tròn theo precision khi đọc giá trị, nên `W_mm = 2450.25` có thể thành 2450.3. Chưa kiểm trên site; nên thử nếu có kích thước lẻ.

**Điểm cần biết 3: Export/Import dùng cấu hình lạ.** `excel_io.attach` được gọi với `doctype: "Purchase Receipt"` và `filename: "purchase_receipt"` (mã còn sót từ ứng dụng khác, kèm một dòng validator bị comment trỏ tới `eupapp`). Tính năng này không liên quan tới tính giá, nên nhãn và tên tệp xuất sẽ không đúng ngữ cảnh.

### 12.5 `ItemParamDialog`: xem giá thử, tính nền và lưu (dòng 1247–1686)

**Một lần preview tự động, theo thứ tự thật:**

1. Người dùng đổi một ô (kính, màu, biến, version, ô cấu hình, lưới biến mở rộng). `onchange` gọi `_schedule_auto_preview`.
2. Dải vàng "đang tự động tính lại" hiện lên đầu vùng kết quả. Debounce 700 ms; đổi tiếp trong thời gian đó thì đếm lại.
3. `_run_preview()`: hiện spinner, gọi `_save()` (ghi vào **bộ nhớ trình duyệt**), tăng `_preview_seq`.
4. `_sync_row_to_db` ghi năm field xuống DB (12.3). Bước này **lưu cả báo giá cha** trên server.
5. `calculate_bom` chạy B0→B7 và **ghi kết quả vào DB** (giá, `al_bom_result`, `rate`, tổng báo giá).
6. `get_result_display` đọc lại kết quả đã gắn nhãn; renderer vẽ bảng; banner và popup cảnh báo nếu có.

Hệ quả cần biết: **không có chế độ tính thử không ghi**. Mọi preview, kể cả preview tự động sau 700 ms, đều ghi DB của báo giá nháp ngay, không đợi bấm Save. Server chặn báo giá đã submit hoặc huỷ (12.9).

| Hàm (dòng) | Làm gì |
| --- | --- |
| `_render_preview_panel()` (1247) | Gọi 300 ms sau khi mở dialog. Đọc `child_doc.al_calc_status` thay vì gọi API: `Success` kèm `al_bom_result` thì vẽ ngay kết quả cũ (không tính lại); `Queued` hoặc `Running` thì hiện câu "đang xếp hàng… nếu chờ lâu bấm Preview để tính lại" và nghe realtime theo `al_calc_job_id`; `Failed` thì hiện lỗi đã làm sạch; chưa tính thì hiện khung nhắc bấm Preview |
| `_listen_realtime(job_id, $container)` (1282) | Huỷ listener cũ rồi đăng ký `frappe.realtime.on("alumglass_bom_calc_done")`. Handler bỏ qua sự kiện khác `job_id`. `Success`: đặt `al_calc_status` và `al_bom_result` vào model, gọi `_apply_rate(result.cost_template.GIA_BAN)`, vẽ kết quả với `force = true` (cảnh báo hiện ngay, không bị dedupe), báo "Tính giá xong". Lỗi: đặt `Failed`, lưu `al_calc_error`, hiện lỗi |
| `_cleanup_realtime()` (1319) | Gỡ listener. Gọi khi dialog ẩn và trước khi đăng ký listener mới, để không rò rỉ |
| `_preview_container()`, `_preview_progress_html(msg)`, `_preview_error_html(error)` (1326–1360) | Lấy vùng kết quả; spinner kèm câu; khối lỗi đỏ. Khối lỗi gọi `sanitize_calc_error`: chỉ hiện câu tiếng Việt, stack trace đẩy vào khối `<details>` "Chi tiết kỹ thuật (gửi cho quản trị khi cần)" |
| `_run_preview(manual)` (1362) | Điều phối như danh sách trên. `manual = true` (bấm nút) thì cuộn mượt tới kết quả; tự động thì không cuộn để không làm mất vị trí đang gõ. Không có BOM thì báo "Vui lòng chọn BOM trước khi Preview". Mọi bước bất đồng bộ kiểm `seq !== _preview_seq` để bỏ kết quả cũ về muộn. Nếu dòng mới được lưu lần đầu và đổi tên thật thì cập nhật lại `child_doc` |
| `_exec_calculate_bom($container, seq, manual)` (1418) | `frappe.call("alumglass.api.calculate_bom", {quotation_item_name})`. Trả `async` thì hiện spinner, đặt model `Queued` và `al_calc_job_id`, nghe realtime. Trả kết quả ngay thì đặt model `Success` và `al_bom_result = JSON(r.message)`, gọi `_apply_rate(GIA_BAN)`, rồi `_render_display_model(…, manual)`. Không có `r.message` thì báo "Không có kết quả". Lỗi mạng hoặc server thì hiện lỗi đã làm sạch |
| `_render_display_model($container, qi_name, force_notify)` (1480) | Gọi `get_result_display`. Có `summary.calculated` thì vẽ `calc_errors_banner(errors)` + `render_bom_result_display(…, {compact: true, show_trace: false})`, rồi `notify_calc_errors` với `dedupe_key = qi_name`; `force_notify` (bấm tay, hoặc kết quả mới về) thì luôn popup, còn mở lại panel xem kết quả cũ thì chỉ hiện banner. Server trả rỗng thì dự phòng `raw_to_display(al_bom_result)` trong bộ nhớ; không có cả hai thì hiện "Đang tải kết quả..." |
| `_build_preview_html(data)` (1525) | Bản dự phòng đồng bộ cho mã cũ: `raw_to_display` rồi renderer chung |
| `_parse_existing()` (1531) | `JSON.parse(child_doc.al_bom_vars)`; lỗi thì `{}` |
| `_esc_html(str)` (1536) | Thoát `& < >` (không thoát dấu nháy). `_render_product_header` dùng hàm này cho thuộc tính `src="…"`; giá trị là URL ảnh do admin nhập nên rủi ro thấp, nhưng nên dùng `alumglass.esc` cho chỗ đó |
| `_save()` (1540) | Gom dữ liệu rồi đặt vào **model trình duyệt**, chưa ghi DB. Xem bên dưới |
| `_apply_rate(giaban)` (1643) | Chỉ khi `giaban` là số **lớn hơn 0** mới `frappe.model.set_value("rate", giaban)`. Đây là lớp chặn mà nút "Tính giá" cấp form không có (12.8) |
| `_collect_overrides()` (1656) | Với sáu cặp (khoá override ← ô dialog ← mặc định của BOM), chỉ trả cặp mà ô có giá trị khác rỗng **và** khác mặc định của BOM |

**`_save()` thu gì, theo thứ tự:**

1. Mọi control trong `_var_controls`: `get_value()` khác rỗng thì `vars[var_name] = giá trị` (gồm cả biến hệ thống, xem điểm cần biết 1 ở 12.4).
2. `glass_master_map = {rep: mã kính}` từ `_glass_controls`, chỉ ghi khi ít nhất một ô có giá trị.
3. `color_master_map = {rep: mã màu}` từ `_color_controls`, cùng điều kiện.
4. `extra_vars` từ lưới: dòng có `var_name`; `Float` hoặc `Int` qua `parseFloat` (NaN thành 0); `Check` thành boolean; còn lại giữ chuỗi.
5. Các override từ `_collect_overrides` gộp thẳng vào `vars`.
6. Nếu có BOM và `_bom_meta.item_code`: đặt `item_code` và `item_name` của dòng theo `representative_item` của BOM, chỉ khi khác giá trị hiện có.
7. `frappe.model.set_value` cho `al_bom_vars` (JSON thụt lề 2), `al_bom`, `al_bom_version` (hai field sau chỉ khi có giá trị).

`vars` luôn được dựng lại từ đầu, nên ô bị xoá trong dialog sẽ biến mất khỏi `al_bom_vars` ở lần lưu sau. Nút **💾 Lưu** chỉ làm tới đây rồi đóng dialog: dữ liệu mới nằm trong form và chỉ xuống DB khi (a) có preview hoặc tính giá, hoặc (b) người dùng bấm Save báo giá.

**Sáu override trong `_collect_overrides`:** `_bom_set` (←`al_bom_set`), `_accessory_set`, `_profile_system`, `_cost_template`, `_bom_name`, `_brand`. Engine chỉ đọc ba cái giữa (12.8, bảng khoá `al_bom_vars`).

**Điểm cần biết 4: sau preview, model và DB lệch nhau ở hai field giá.** Đường dialog chỉ cập nhật model của `al_calc_status`, `al_bom_result` và `rate`; không cập nhật `al_gia_ban` và `al_gia_vat` (hai field này `read_only` trên form). Server đã ghi giá mới vào DB, nhưng form giữ giá cũ tới khi tải lại hoặc có đường cập nhật khác. Nút "Tính giá" cấp form thì đặt đủ cả ba. Chưa kiểm hệ quả khi Save báo giá ngay sau preview (phụ thuộc cách Frappe xử lý field `read_only` do client gửi lên); nên thử trên site và tải lại form sau khi preview.

### 12.6 `BOMDialog`: dialog kết quả tính giá (dòng 1687–1893)

**Mục đích.** Xem kết quả của một dòng báo giá ở dạng đầy đủ (có trace từng dòng). Khác `ItemParamDialog`: không có ô nhập, chỉ một vùng HTML `result_html` và nút Close. Hàm vẽ là `render_bom_result_display` với `show_trace: true`.

| Hàm (dòng) | Làm gì |
| --- | --- |
| `constructor(quotation_item_name)` (1688) | Nhận **tên thật** của dòng (đã tồn tại trong DB), không nhận `child_doc` |
| `show()` (1694) | Dựng `frappe.ui.Dialog` cỡ lớn tiêu đề "BOM Calculation Result", gắn `hidden.bs.modal` để dọn realtime, rồi gọi `_load_existing_state()` |
| `_load_existing_state()` (1715) | Đọc từ **DB** bằng `frappe.db.get_value` bốn field `al_calc_status`, `al_calc_job_id`, `al_bom_result`, `al_calc_error`. `Success` kèm kết quả thì vẽ luôn, **không tính lại**. `Queued` hoặc `Running` thì hiện tiến trình và nghe realtime. `Failed` thì hiện lỗi. Chưa có trạng thái thì mới gọi `calculate()` |
| `calculate()` (1746) | Gọi `calculate_bom`. Trả `async` thì hiện tiến trình và nghe realtime; trả kết quả ngay thì `render_results` |
| `_listen_realtime(job_id)`, `_cleanup_realtime()` (1776, 1796) | Giống bản trong `ItemParamDialog`: lọc theo `job_id`, nhận được thì tự huỷ listener; `Success` thì báo "Tính giá xong cho …" và vẽ `data.result`, ngược lại hiện lỗi |
| `_show_loading(msg)`, `_show_async_progress(job_id, msg)` (1804, 1811) | Spinner; khung xanh "đang tính nền" kèm lối thoát: đóng và bấm tính lại nếu chờ lâu (job nền có thể chết khi worker khởi động lại) |
| `_render_error(error)` (1824) | Qua `sanitize_calc_error`; câu ngắn hiện nguyên văn, stack trace vào khối `<details>` |
| `_set_html(html)` (1839) | `dialog.set_value("result_html", html)` rồi `dialog.show()` |
| `render_results(data)` (1850) | Gọi `get_result_display`; có `summary.calculated` thì dán `calc_errors_banner` + bảng kết quả (trace bật, tiêu đề "BOM Calculation Results") và `notify_calc_errors` với `force: true`. Server trả rỗng hoặc lỗi mạng thì dự phòng `raw_to_display(data)` |

**Điểm cần biết 5: mở BOMDialog có thể hiện kết quả cũ.** Hai nút "🖥️ Preview tính giá" (trên dòng và trong form mở rộng) chỉ `_sync_row_to_db` rồi mở `BOMDialog`. Nếu dòng đã ở trạng thái `Success` thì `_load_existing_state` vẽ kết quả đã lưu và **không gọi lại `calculate_bom`**. Người dùng sửa tham số trong dialog 📐 rồi bấm 🖥️ sẽ thấy giá cũ nếu auto-preview của dialog 📐 chưa chạy xong hoặc bị tắt (nhờ auto-preview, đa số trường hợp kết quả đã mới). Muốn chắc chắn: bấm "Preview tính giá" trong dialog 📐, hoặc dùng nút "Tính giá" cấp form.

### 12.7 Sự kiện form và nút trên từng dòng (dòng 1896–2100)

| Hàm / handler (dòng) | Làm gì |
| --- | --- |
| `frappe.ui.form.on("Quotation").refresh` (1897) | Gọi `_attach_row_actions`, `_schedule_row_actions_retry`, đặt placeholder cột `item_code` thành "Chọn Asset Category" (`alumglass.grid_placeholder.set_column`), và `_add_form_actions` |
| `…on("Quotation").after_save` (1911) | Sau 600 ms gắn lại nút (lưới vẽ lại sau khi lưu) |
| `…on("Quotation Item").items_add` (1918) | Dòng mới thêm thì sau 200 ms gắn nút |
| `…on("Quotation Item").form_render` (1923) | Khi mở rộng một dòng thành form con: nếu `docstatus ≠ 0` thì không làm gì. Ngược lại sau 400 ms chèn hai nút "📐 Tham số BOM" và "🖥️ Preview tính giá" vào `.grid-form-body`, chỉ chèn một lần (`.al-form-btn`). Nút Preview kiểm đã có `al_bom`, ghi `al_bom_vars` từ `_collect_form_vars` vào model, `_sync_row_to_db`, rồi mở `BOMDialog` |
| `_schedule_row_actions_retry(frm, maxAttempts = 10)` (1983) | Lưới Frappe vẽ dòng **sau** `refresh`, nên hàm này lặp mỗi 500 ms (tối đa 10 lần, khoảng 5 giây) gọi `_attach_row_actions`, dừng sớm khi mọi dòng đã có nút. Giữ một biến timer toàn cục `_alRowActionsTimer`; gọi lại sẽ xoá timer cũ |
| `_attach_row_actions(frm)` (2011) | Với mỗi `.grid-row`: bỏ qua nếu đã gắn (`data("_al_btn")`), bỏ qua nếu `docstatus ≠ 0`. Chèn vào góc phải ô `item_code` hai nút 📐 (mở `ItemParamDialog`) và 🖥️ (đồng bộ DB rồi mở `BOMDialog`, có `frappe.dom.freeze` trong lúc đồng bộ, chưa chọn BOM thì nhắc mở 📐 trước). Biến ô thành flex để nút nằm bên phải. Gắn thêm `dblclick.alumglass` trên dòng để mở `ItemParamDialog` |
| `_get_row_doc(frm, $row)` (2094) | Đọc `data-name` của dòng và tìm trong `frm.doc.items`; không thấy thì `null` |
| `_collect_form_vars(frm, cdn)` (2102) | Parse `al_bom_vars` của dòng; nếu có `al_bom` mà chưa có `_bom` thì thêm `_bom = al_bom`. Không đọc control nào trên form (dù tên nói "collect form"). Khoá `_bom` chỉ lọt vào `inputs` như biến thừa |

Ghi chú về `docstatus`: cả ba chỗ (`form_render`, `_attach_row_actions`, `_add_form_actions`) kiểm `docstatus` ở client chỉ để **không mời bấm nhầm**. Lớp chặn thật là `assert_quotation_item_editable` ở server (12.9).

### 12.8 Nút cấp form: Tính giá và Preview giá (dòng 2116–2351)

| Hàm (dòng) | Làm gì |
| --- | --- |
| `_add_form_actions(frm)` (2116) | Thêm hai nút vào nhóm "AlumGlass" của form Quotation. **Tính giá** chỉ khi `docstatus = 0`; **Preview giá** hiện ở mọi trạng thái vì chỉ đọc. `add_custom_button` tự khử trùng theo nhãn nên gọi mỗi lần `refresh` vẫn an toàn |
| `_calc_all_items(frm)` (2132) | Tính giá tuần tự cho mọi dòng (chi tiết bên dưới) |
| `_preview_all_items(frm)` (2251) | Mở dialog 90vw "Preview giá toàn bộ sản phẩm": bảng tổng hợp (STT, mã, tên, số lượng, đơn giá `rate`, thành tiền `qty × rate`), rồi mỗi sản phẩm một khối `<details>` mà nội dung nạp bất đồng bộ bằng `get_result_display` (không tính, chỉ đọc kết quả đã lưu). Nhãn trạng thái bên phải: "Đã tính", "Đã tính — có cảnh báo", "Đã tính — có lỗi" hoặc "Chưa tính giá". Chưa tính thì câu hướng dẫn đổi theo `docstatus` (đã gửi hoặc đã huỷ thì nói rõ không tính lại được, thay vì chỉ vào nút đã bị ẩn) |

**`_calc_all_items`, từng bước:**

1. Lấy các dòng bằng bộ lọc `!r.is_new`. Không có field `is_new` nào được khai báo (tìm trong toàn bộ mã), nên bộ lọc giữ lại **mọi** dòng.
2. Không có dòng nào thì báo "Chưa có dòng sản phẩm nào".
3. Kiểm từng dòng có `al_bom`, `al_bom_version`, `al_bom_vars`. Thiếu **một** dòng là dừng cả lượt và liệt kê dòng nào thiếu gì; không dòng nào được tính.
4. Với từng dòng, tuần tự: `_sync_row_to_db` (12.3), rồi `calculate_bom`.
5. Trả `async`: đặt model `al_calc_status = Queued` và `al_calc_job_id`, tăng bộ đếm `queued`, sang dòng kế (kết quả nền không được chờ ở đây).
6. Trả đồng bộ: gom cảnh báo (`collect_calc_errors`), đặt model `al_calc_status = Success`, `al_bom_result = JSON(r.message)`, `al_gia_ban = ct.GIA_BAN || 0`, `al_gia_vat = ct.GIA_VAT || 0`, `rate = ct.GIA_BAN || 0`. Các giá trị đọc **theo tên** `GIA_BAN` và `GIA_VAT`, không theo cờ (xem phát hiện 6 ở 11.1).
7. Lỗi: `Failed` kèm câu đã làm sạch (`sanitize_calc_error`), đếm `failed`.
8. Cuối lượt: `refresh_field("items")`, thông báo "Đã tính X/Y dòng" (kèm số dòng chờ nền, số dòng lỗi) và **một** popup gom mọi cảnh báo của cả lượt (không popup từng dòng). Hết lượt không tự Save báo giá; giá đã nằm sẵn trong DB do server ghi.

**Điểm cần biết 6: bản `al_bom_result` trong model nhẹ hơn bản trong DB.** Server lưu `al_bom_result` gồm `buckets`, `cost_template`, `cost_template_trace`, `lines`, `gia_vat`, `gia_ban`, `errors` (`b7_save_results`). Nhưng phản hồi trả cho client (`_build_response`) không có `gia_vat`, `cost_template_trace` (đúng với chú thích trong mã: "response không có gia\_vat top-level"). Cả dialog và `_calc_all_items` đều đặt model `al_bom_result = JSON(phản hồi)`. Nếu Save báo giá làm bản nhẹ này ghi đè DB, `summary.gia_vat` sẽ về 0 và trace lưu sẵn mất, màn hình tự dựng lại trace từ công thức. Chưa kiểm hệ quả này trên site (phụ thuộc cách Frappe xử lý field `read_only` khi client gửi lên). Cách an toàn: tính xong thì tải lại form trước khi Save.

**Bảng khoá `al_bom_vars` mà engine thật sự đọc** (đã đối chiếu `b1_gather_inputs`, 11.3):

| Khoá | Nơi đọc | Tác dụng |
| --- | --- | --- |
| mọi khoá phẳng (`W_mm`, `n_panel`, `NC_SX_PCT`…) | B1.5 | Vào `inputs`, thắng mọi nguồn trước đó |
| `extra_vars` | B1.1 | Gộp vào `inputs` (sau đó bị FB và 1.5 ghi đè nếu trùng tên) |
| `_accessory_set` hoặc `accessory_set` | B1.5b | Chọn bộ phụ kiện (doc sống) |
| `glass_master`, `glass_master_map` | B1.5b | Kính toàn BOM, kính theo vị trí |
| `aluminum_color`, `color_master_map` | B1.5b | Màu toàn BOM, màu theo vị trí |
| `_profile_system` | B1.5b/c | Resolve lại biến hệ thống theo profile này |
| `_cost_template` | B1.5b, B6 | Dùng doc `AL Cost Template` sống thay snapshot |
| `_bom_set`, `_bom_name`, `_brand`, `_bom` | không ai đọc | Chỉ lọt vào `inputs` như biến thừa |

### 12.9 Phía server mà `quotation.js` gọi

| Hàm (tệp) | Vào → ra | Mục đích và cách hoạt động |
| --- | --- | --- |
| `calculate_bom(quotation_item_name)` (`api/__init__.py:7`) | tên dòng → kết quả hoặc `{async: true, job_id…}` | API chính, `@frappe.whitelist`. Thứ tự: (1) `_require_quotation_item_permission(…, "read")`: chỉ cần quyền **đọc** Quotation cha (cố ý: vai trò `AL BOM Manager` làm việc được, và đây là chốt quyền duy nhất, vì ghi kết quả bằng db.set\_value bỏ qua kiểm quyền của Frappe); (2) `assert_quotation_item_editable` chặn sớm báo giá đã gửi hoặc huỷ; (3) `frappe.get_doc` dòng; (4) so số dòng BOM với ngưỡng async; (5) `≤` ngưỡng thì `BomOrchestrator(…).run()` đồng bộ và `_normalize_bom_response`, `>` ngưỡng thì `_enqueue_bom_calculation` |
| `_estimate_bom_line_count(qi)` (api/\_\_init\_\_.py) | → số nguyên | Đếm số dòng trong `bom_set_snapshot` của version đã ghim (hoặc `current_version` của BOM). Không có version hoặc parse lỗi thì 0 (chạy đồng bộ). Không đếm dòng phụ kiện |
| `_get_async_threshold()` | → số nguyên | Đọc `ASYNC_BOM_THRESHOLD` từ `Formula Global Variable` (đọc thẳng `constant_value`), mặc định 150 |
| `_enqueue_bom_calculation(qi)` | → `{async, job_id, status, message}` | Sinh `job_id = albom-<tên dòng>-<hash 8>`, ghi `Queued` và commit (`update_modified=False`), rồi `frappe.enqueue(queue="long", timeout=600)`. Enqueue nằm trong `try`: Redis hoặc worker chết thì đặt `Failed` kèm câu tiếng Việt, ghi Error Log và ném lỗi, để dòng không kẹt `Queued` mãi |
| `_run_bom_calculation_job(qi_name, job_id, user)` | job nền, không whitelist | `frappe.set_user(user)` trước (không thì job chạy quyền Administrator của worker), đặt `Running`, chạy `BomOrchestrator.run()`, đặt `Success`, rồi `publish_realtime("alumglass_bom_calc_done", {job_id, qi_name, status, result}, user=user)`. Lỗi: đặt `Failed` + `al_calc_error` (câu ngắn), Error Log chứa stack trace, và publish sự kiện `Failed` kèm `error` |
| `_bom_error_message(exc)` | exception → một câu | `FormulaZeroDivisionError` thì "Công thức chia cho 0 — kiểm tra lại kích thước/số lượng đầu vào (W, H, số cánh…)"; `frappe.ValidationError` thì dùng nguyên văn (cắt 300 ký tự); còn lại câu chung. Không lộ stack trace ra UI |
| `_normalize_bom_response(result)` | → dict | `setdefault` cho `buckets`, `cost_template`, `lines`, `errors`, để UI không gãy khi engine thiếu khoá. (Docstring còn ghi "engine chưa trả `errors`", đã lỗi thời) |
| `get_result_display(quotation_item_name)` (1242) | → display model | Chỉ đọc. Kiểm quyền `read` trên Quotation cha (vì trả cả công thức và giá thành). Đọc `al_bom_result`, gắn nhãn slug (`_get_slug_labels`), tên bucket (`_get_bucket_names`), công thức và nhãn dòng cost template (`_get_cost_template_display`). Trace: ưu tiên `cost_template_trace` đã lưu, thiếu thì dựng lại bằng `_build_trace` với context gồm bucket, kết quả và các biến số trong `al_bom_vars` |
| (trong `get_result_display`) |  | `summary.gia_vat = data.gia_vat`; `summary.gia_ban = data.gia_ban`, thiếu thì `cost_template.GIA_BAN`; `calculated` = có `lines` hoặc `cost_template`. Dòng cost template được coi là tổng phụ (`is_subtotal`) khi mã bắt đầu `TONG_`, `GIA_`, `VAT` hoặc bằng `PROFIT` (đoán theo tên; không đọc cờ `is_subtotal` của `AL Cost Template Item`). Nhãn ô thứ hai ở thanh tóm tắt là "VAT" nhưng nội dung là `gia_vat`, tức giá **đã gồm** VAT, không phải tiền thuế |
| `get_variable_set_for_bom(bom_code)` (737) | → meta BOM + biến + nhóm kính/màu | Xem 12.4 |
| `assert_quotation_item_editable(name)` (`engine/bom_orchestrator.py:30`) | → ném lỗi hoặc không | Lấy `parent` của dòng, đọc `docstatus` của **Quotation cha** (không tin docstatus dòng con); `1` thì ném "đã gửi khách… huỷ rồi Tạo bản sửa (Amend)", `2` thì ném "đã huỷ". Gọi ở đầu `calculate_bom` và sát lệnh ghi trong B7 (bắt cả ca báo giá bị submit giữa lúc job nền đang chạy) |
| `b7_save_results` (`:2588`) |  | Ghi `al_gia_vat`, `al_gia_ban`, `al_bom_result`, `rate` bằng một `frappe.db.set_value` rồi `_recalculate_quotation_totals`: nạp Quotation cha, gán `rate` đúng dòng này (làm tròn theo precision của field), đặt tạm `price_list_rate = 0` và `discount_percentage = 0` **trong bộ nhớ** để ERPNext không tự thay giá, tính lại tổng, ghi 13 field tổng bằng `set_value(update_modified=False)`, một commit duy nhất. Lỗi ở bước tổng thì ném lỗi lên thay vì để trạng thái nửa vời (giá mới, tổng cũ) |
| `quotation_events.on_submit(doc)` | doc submit | Với mỗi dòng đã có `al_bom_result`, tạo một `ConfigSnapshot` (`bom_version`, `inputs_json = al_bom_vars`, `result_json = al_bom_result`, thời điểm) rồi gắn vào `al_config_snapshot` của dòng. Hai pha: tạo hết snapshot trước, gắn sau, để lỗi giữa chừng rollback sạch. Chạy trong transaction submit, không `commit` riêng |

**Các field tùy biến trên `Quotation Item`** (`setup/custom_fields.py`): `al_bom` (Link), `al_bom_version` (Link), `al_bom_vars` (JSON), `al_config_snapshot` (Link, chỉ đọc), `al_gia_ban`, `al_gia_vat` (Currency, chỉ đọc), `al_bom_result` (JSON, chỉ đọc), `al_calc_status` (Select rỗng/Queued/Running/Success/Failed, chỉ đọc, không sao chép, ẩn khi in), `al_calc_job_id` (Data, chỉ đọc, ẩn, không sao chép), `al_calc_error` (Small Text, chỉ đọc, không sao chép, ẩn khi in).

### 12.10 Toàn bộ luồng từ lúc mở dòng tới lúc submit

1. Mở form Quotation Draft: `refresh` gắn nút 📐 và 🖥️ vào từng dòng (có retry tối đa 5 giây vì lưới vẽ muộn), thêm nút **Tính giá** và **Preview giá**.
2. Bấm 📐 (hoặc nhấp đúp dòng): `ItemParamDialog` mở, gọi `get_variable_set_for_bom`, vẽ vùng biến, nghe realtime, vẽ panel kết quả theo trạng thái đã lưu.
3. Người dùng đổi tham số: sau 700 ms, `_run_preview` → `_save` (model) → `_sync_row_to_db` (DB, kèm lưu báo giá cha) → `calculate_bom` (B0→B7, ghi DB) → `get_result_display` → bảng kết quả, banner, popup cảnh báo.
4. BOM lớn hơn ngưỡng: server trả `Queued`; job `long` chạy dưới quyền người bấm; sự kiện `alumglass_bom_calc_done` về, client đặt model `Success` và `rate` rồi vẽ kết quả.
5. Bấm **💾 Lưu**: chỉ đặt `al_bom_vars`, `al_bom`, `al_bom_version` (và `item_code`, `item_name`) vào model rồi đóng dialog. Dữ liệu xuống DB khi preview, khi tính giá, hoặc khi Save báo giá.
6. Bấm **Tính giá** (cấp form): kiểm đủ dữ liệu, tuần tự đồng bộ và tính từng dòng, đặt giá vào model, popup gom cảnh báo.
7. Bấm **Preview giá** (cấp form): đọc kết quả đã lưu của mọi dòng, không tính.
8. Save Quotation: Frappe gửi cả form; ERPNext tính tổng theo `rate` từng dòng.
9. Submit Quotation: `on_submit` tạo `ConfigSnapshot` cho dòng đã tính. Từ đây `assert_quotation_item_editable` chặn mọi lần tính lại; muốn đổi giá phải huỷ rồi Amend.

**Tổng hợp các điểm cần biết riêng của giao diện**

| # | Điểm | Mức độ ảnh hưởng | Đã kiểm bằng cách |
| --- | --- | --- | --- |
| 1 | Lưu dialog ghim biến hệ thống (`OFFSET_*`, `NC_*`, `PROFIT_MARGIN`) vào `al_bom_vars` | Đổi Product Type hoặc Profile System không còn tác dụng với dòng đã lưu | Đọc mã `_save` và `get_variable_set_for_bom` |
| 2 | Float `precision: "1"` | Kích thước lẻ có thể bị làm tròn 0,1 | Suy ra từ hành vi chuẩn Frappe, chưa kiểm site |
| 3 | Export/Import dùng cấu hình `Purchase Receipt` | Chỉ sai nhãn, tên tệp | Đọc mã |
| 4 | Sau preview, model lệch DB ở `al_gia_ban`, `al_gia_vat` | Có thể hiện giá cũ trên form | Đọc mã; hệ quả khi Save chưa kiểm |
| 5 | 🖥️ mở `BOMDialog` hiện kết quả cũ nếu dòng đang `Success` | Có thể xem nhầm giá cũ | Đọc mã |
| 6 | `al_bom_result` trong model nhẹ hơn DB | Có thể mất `gia_vat` và trace nếu Save ghi đè | Đọc mã; hệ quả chưa kiểm |
| 7 | Mọi preview đều ghi DB | Báo giá nháp đổi giá khi chưa Save | Đọc mã |
| 8 | `calculate_bom` chỉ cần quyền đọc Quotation | Người chỉ có quyền đọc cũng ghi được giá của báo giá nháp (thiết kế có chủ ý, docstring nêu rõ) | Đọc mã |
