# CHANGELOG CHI TIẾT — File / Hàm / Tính năng thay đổi

> Trích xuất trực tiếp từ `git diff` của 2 repo sau khi áp dụng patch (không
> chép tay) — đảm bảo khớp 100% với code thật trong zip đã gửi.
> Tổng: **23 file thay đổi** (`alumglass`) + **1 file thay đổi** (`formula_builder`).

---

## Repo `AlumGlass`

### 1. `alumglass/engine/bom_orchestrator.py` (218 dòng thay đổi — file sửa nhiều nhất)

| Hàm | Loại thay đổi | Tính năng cụ thể |
|---|---|---|
| `_fetch_composite_prices_via_fb` | **Sửa toàn bộ thân hàm** (chữ ký giữ nguyên) | Trước: gọi `resolve_all_bindings_batch` theo **từng item_code** (N+1 — 2×M query cho M dòng BOM). Sau: đọc `pricing_mode` từ binding **1 lần**, rồi rẽ nhánh nhanh (`exact_match` → gọi `_fetch_composite_prices` batch 1 query; `multiplier_chain` → hàm mới bên dưới). Chỉ chạy nhánh nhanh khi có **đúng 1** binding `aluminum_price_composite` active; ngược lại rơi về `_fetch_composite_prices_via_fb_slow` (an toàn hơn đoán). |
| `_fetch_composite_prices_via_fb_slow` | **Hàm mới** | Giữ nguyên 100% logic per-item cũ (có N+1) — dùng làm lưới an toàn cho case lạ (0 hoặc >1 binding cùng lúc), tránh đoán sai config nào ưu tiên. |
| `_fetch_composite_prices_multiplier_chain` | **Hàm mới** | Chế độ tính giá theo hệ số nhân (`pricing_mode=multiplier_chain`): 1 query `Item Price` lấy base price cho **toàn bộ** item_codes, dùng `frappe.get_cached_value` (đã cache theo request) cho multiplier — không còn N+1. |
| `_fetch_composite_prices` | **Đổi chữ ký**: `(self, item_codes)` → `(self, item_codes, price_list=None, allow_missing=False)` | Thêm tham số `price_list` (cho phép FB-max truyền price list từ binding config) và `allow_missing` (item không khớp giá trả `0` thay vì `throw` — khớp hành vi `fb_handlers.aluminum_price_composite`). **Sửa lỗi dữ liệu**: loop nay chạy qua **toàn bộ** `item_codes` yêu cầu thay vì chỉ các item có ≥1 dòng Item Price — trước đây item 0 dòng giá bị **thiếu khỏi kết quả** một cách âm thầm (không phải 0, không throw — biến mất). |
| `_match_composite_price` | **Đổi chữ ký**: thêm `allow_missing=False` | Không khớp giá + `allow_missing=True` → trả `0` thay vì `frappe.throw`. |
| `_color_variable_for_category` | **Sửa toàn bộ thân hàm** (chữ ký giữ nguyên) | Trước: hardcode so sánh `m.get("pricing_dimension") == "MAU_SAC"`. Sau: gọi `_get_color_dimension_codes()` — tra theo field mới `AL Pricing Dimension.represents_color=1`, không còn phụ thuộc tên mã dimension cụ thể. |
| `_get_color_dimension_codes` | **Hàm mới** | Cache (theo instance) tập `dimension_code` có `represents_color=1`. |
| `_load_accessories` | **Sửa 1 đoạn** | Trước: hardcode `"color_group_category": "PHU_KIEN"`. Sau: gọi `get_named_constant("DEFAULT_ACCESSORY_CATEGORY", ...)` **1 lần trước vòng lặp**, dùng biến kết quả cho mọi dòng phụ kiện. |
| `b2_prefetch_master_data` | **Thêm 2 dòng** | Gọi `fetch_glass_category_codes(cat_codes)`, lưu vào `self._glass_categories` — dùng chung cho 2 nhánh nhận diện "category kính" bên dưới. |
| (2 vị trí trong logic build BOM — không phải hàm riêng, nằm trong thân `b2_prefetch_master_data`/hàm build glass group) | **Sửa 2 chỗ** | Trước: `if (item.get("category") or "").upper() == "KINH":`. Sau: `if item.get("category") in self._glass_categories:` — không còn hardcode chuỗi `"KINH"`. |
| `_get_dim_mappings_raw` (2 câu query `AL Variable Dimension Mapping` bên trong) | **Thêm filter** | Cả 2 query (nhánh live, không phải nhánh đọc snapshot) thêm `filters={"is_active": 1}`. |

### 2. `alumglass/al_bom_engine/glass_group_resolver.py`

| Hàm | Loại thay đổi | Tính năng cụ thể |
|---|---|---|
| `fetch_glass_category_codes(category_codes)` | **Hàm mới** | Nguồn duy nhất trả về tập `AL Material Category` có `requires_glass_master=1` trong danh sách `category_codes` truyền vào — thay hardcode `"KINH"` ở **3 nơi** khác nhau (`bom_orchestrator.py` ×2, `api/__init__.py` ×1) bằng **1 nguồn dữ liệu chung**, không thể lệch nhau nữa. |
| (thêm `import frappe`) | Thay đổi phụ trợ | Module trước đó chưa import `frappe`. |

### 3. `alumglass/al_bom_engine/fb_config.py` — **FILE MỚI**

| Hàm | Tính năng cụ thể |
|---|---|
| `get_named_constant(variable_name, default=None)` | Đọc 1 "named constant" qua **Formula Variable Binding** (`source_type=constant`), cache theo request (`frappe.local`). Cơ chế **chung** cho mọi nhu cầu "chọn 1 giá trị cấu hình cho 1 mục đích" — sửa được ngay qua UI, không cần `bench migrate`. Dùng để thay hardcode `"PHU_KIEN"`. Không có binding active → ghi `frappe.log_error` + trả `default`, **không** tự đoán giá trị ngầm trong code. |

### 4. `alumglass/api/__init__.py`

| Vị trí | Loại thay đổi | Tính năng cụ thể |
|---|---|---|
| Hàm build "glass groups" (đọc `bom_set.items`) | Sửa 1 đoạn | Thay `if (item.get("category") or "").upper() != "KINH":` bằng tra `fetch_glass_category_codes(...)` 1 lần trước vòng lặp rồi `if item.get("category") not in _glass_cats:`. |
| Đoạn đọc phụ kiện (`AL Accessory Set`) trong cùng hàm | Sửa 1 đoạn | Thay hardcode `_add_color_group(acc_item, "PHU_KIEN", ...)` bằng `get_named_constant("DEFAULT_ACCESSORY_CATEGORY", ...)`. |
| 2 vị trí khác (danh sách biến cho dialog Quotation JS) | Thêm filter | `frappe.get_all("AL Variable Dimension Mapping", pluck="variable_name")` → thêm `filters={"is_active": 1}`. |

### 5. `alumglass/fb_handlers.py`

| Vị trí | Loại thay đổi | Tính năng cụ thể |
|---|---|---|
| `aluminum_price_composite` (hàm xử lý source_type, load mapping) | Sửa 1 dòng | `mapping_filters = {}` → `mapping_filters = {"is_active": 1}`. |

### 6. `alumglass/al_bom_engine/doctype/al_bom_version/al_bom_version.py`

| Vị trí | Loại thay đổi | Tính năng cụ thể |
|---|---|---|
| Hàm chụp `pricing_dimension_snapshot` lúc publish | Thêm 2 filter | Cả query `AL Pricing Dimension` lẫn `AL Variable Dimension Mapping` thêm `filters={"is_active": 1}` — snapshot chỉ chụp cấu hình đang active tại thời điểm publish. |

### 7. `alumglass/al_buying/doctype/al_supplier_price_list/al_supplier_price_list.py`

| Hàm | Loại thay đổi | Tính năng cụ thể |
|---|---|---|
| `_backfill_previous_price_and_change_pct(self)` | **Hàm mới**, gọi từ `validate()` | Với mỗi dòng item, tìm bảng giá **gần nhất trước đó** của cùng nhà cung cấp (+ cùng `currency_type`) để tự động điền `previous_unit_price` và tính lại `base_price_change_pct`. **Chủ động không tính** `fx_change_pct` (để trống) vì cần xác nhận quy ước quy đổi tỷ giá thật trước khi suy đoán công thức. |

### 8. `alumglass/setup/install_fb_bindings.py`

| Vị trí | Loại thay đổi | Tính năng cụ thể |
|---|---|---|
| `DEFAULT_ACCESSORY_CATEGORY_BINDING` | **Hằng số mới** | Payload seed cho Formula Variable Binding `DEFAULT_ACCESSORY_CATEGORY` (giá trị mặc định `"PK"` — **cần xác nhận đúng tên category thật trong production**, khác hardcode cũ `"PHU_KIEN"`). |
| `install_named_constant_bindings()` | **Hàm mới** | Idempotent — chỉ seed nếu binding **chưa tồn tại** (khác `install_composite_pricing_binding()` vốn ép cấu hình lại mỗi lần) — tôn trọng nếu admin đã tự sửa qua UI. |

### 9. `alumglass/hooks.py`

| Vị trí | Loại thay đổi | Tính năng cụ thể |
|---|---|---|
| `_after_install`, `_after_migrate` | Bỏ comment `install_workflows()` | Trước: `# install_workflows()` — Workflow thật (đã viết sẵn trong `install_workflows.py`) **chưa từng chạy**, khiến `workflow_state` trên 4 doctype (`AL BOM Version`, `AL Change Order`, `AL Design Revision`, `AL Dynamic Item Rule Version`) chỉ là Select tự do, ai cũng tự chuyển trạng thái được. Sau: bật thật. |
| `_after_install`, `_after_migrate` | Thêm import + gọi | `install_named_constant_bindings()` — wire hàm mới ở mục 8. |

### 10. `alumglass/setup/install_roles.py`

| Vị trí | Loại thay đổi | Tính năng cụ thể |
|---|---|---|
| `CHANGE_ORDER_APPROVAL_PERMISSIONS` | **Hằng số mới** | `{"System Manager", "AL Project Accountant", "AL Technical Admin"}` → quyền write ở **permlevel=1**. |
| `install_roles_and_permissions()` | Thêm 1 khối (bước "3.6") | Áp `CHANGE_ORDER_APPROVAL_PERMISSIONS` qua `_upsert_docperm` (record permlevel riêng, không ghi đè quyền permlevel=0 sẵn có) — tách biệt "người tạo Change Order" khỏi "người xác nhận đã được duyệt". |

### 11. Field JSON — additive, không đổi hành vi cũ

| Doctype | Field mới | Mục đích |
|---|---|---|
| `AL Pricing Dimension` | `represents_color` (Check) | Nguồn duy nhất đánh dấu "dimension này là màu sắc" — bỏ hardcode `"MAU_SAC"`. |
| `AL Variable Dimension Mapping` | `is_active` (Check, default 1) | Cho phép "nghỉ hưu" 1 mapping mà không xoá record (giữ lịch sử). |
| `AL Slug Library` | `is_active` (Check, default 1) | Tương tự — không phải xoá slug cũ đang được `AL Bom Item` tham chiếu. |
| `AL Glass Master` | `weight_kg_per_m2` (Float) | Trọng lượng kính theo m² — khác đơn vị `Item.al_weight_per_m` (kg/mét, dùng cho nhôm thanh). |
| `AL Glass Master` | `max_area_m2` (Float) | Diện tích tối đa an toàn theo tiêu chuẩn kính cường lực/dán an toàn. |
| `AL Site Survey Item` | `width_deviation_mm`, `height_deviation_mm`, `within_tolerance` | Đổi thành `read_only=1` (đã có controller `_calculate_deviations()` tính, trước đó field trông như nhập tay được nhưng bị ghi đè âm thầm). |
| `AL Punchlist Item` | `assigned_to` (Link → Employee) | Người **cần** xử lý, trước khi có `resolved_by`. |
| `AL Handover Acceptance` | `company_representative_signature` (Attach Image) | Đủ 2 chữ ký (khách hàng + đại diện công ty) trong biên bản nghiệm thu. |
| `AL Supplier Price List Item` | `previous_unit_price` (Currency, read_only) | Hiển thị cạnh `unit_price`/`%` thay đổi để đối chiếu trực quan (điền tự động bởi mục 7). |
| `AL Change Order` | `customer_approval`, `internal_approval` → thêm `permlevel: 1` | Giới hạn quyền tick 2 checkbox này (xem mục 10). |

### 12. File mới / xoá khác

| File | Thay đổi |
|---|---|
| `alumglass/patches/v28_12/__init__.py` | File mới (rỗng, module patch). |
| `alumglass/patches/v28_12/set_represents_color_flag.py` | Hàm `execute()` — backfill `represents_color=1` cho dimension `MAU_SAC` hiện có. |
| `alumglass/patches.txt` | Thêm dòng đăng ký `alumglass.patches.v28_12.set_represents_color_flag`. |
| `alumglass/al_selling/doctype/custom_fields/custom_field_quotation.py` | **ĐÃ XOÁ** — dead code, không được gọi ở đâu trong hooks.py, và định nghĩa field xung đột với `setup/custom_fields.py` (đặt field BOM/màu ở header Quotation thay vì item-level như bản đang chạy thật). |

---

## Repo `Formula-Builder` (nhánh `develop`)

### `formula_builder/api/data_source_registry.py` (207 dòng thêm, 2 dòng xoá — 1 file duy nhất thay đổi)

| Hàm | Loại thay đổi | Tính năng cụ thể |
|---|---|---|
| `_fetch_range_rows(cfg)` | **Hàm mới** | Đọc toàn bộ dòng cấu hình khoảng số (`from`/`to`/`value`) từ 1 doctype theo `cfg`. |
| `_match_range_value(rows, cfg, input_val, default_value, data_type)` | **Hàm mới** | Chọn dòng có `from ≤ input_val ≤ to`, ép kiểu theo `data_type`. |
| `_handle_range_lookup(binding, doc, resolved_so_far)` | **Hàm mới** — đăng ký `@register_source("range_lookup", ...)` | **Source type mới: `range_lookup`** — tra giá trị theo khoảng số (from-to → result), tổng quát hoá pattern `AL Dynamic Item Rule` (THRESHOLD mode) thành 1 cơ chế dùng chung mọi ngành, không riêng cho alumglass. |
| `_resolve_range_lookup_batch(bindings, doc, resolved_so_far)` | **Hàm mới** | Batch resolver — fetch rows 1 lần cho cả nhóm binding cùng (doctype, filters). |
| `_handle_linked_doctype_field(binding, doc, resolved_so_far)` | **Sửa thân hàm** (chữ ký giữ nguyên) | Trước: bắt buộc `link_field` trong config. Sau: `link_field` **có thể để trống** nếu có `target_doctype` — engine tự dò field `Link` đầu tiên trên `doc.doctype` trỏ tới `target_doctype` qua `_auto_discover_link_field`. |
| `_auto_discover_link_field(source_doctype, target_doctype)` | **Hàm mới** | Dò field Link đầu tiên (theo `frappe.get_meta`, đã tự cache) khớp `target_doctype`. |
| `_resolve_linked_doctype_field_batch(...)` | **Sửa thân hàm** | Thêm đúng nhánh auto-discover tương tự bản đơn — giữ nhất quán hành vi giữa 2 đường resolve (đơn lẻ và batch). |
| `_fetch_child_table_row(cfg, doc)` | **Hàm mới** | Tìm 1 dòng khớp `key_field`/`key_value` trong 1 child table của `doc` (có thể lọc thêm `filter_active_field`). |
| `_handle_child_table_lookup(binding, doc, resolved_so_far)` | **Hàm mới** — đăng ký `@register_source("child_table_lookup", ...)` | **Source type mới: `child_table_lookup`** — tra **đúng 1 dòng** trong child table theo key rồi trả 1 field khác (khác `child_table_aggregate` vốn chỉ tổng hợp/aggregate). |
| `_resolve_child_table_lookup_batch(bindings, doc, resolved_so_far)` | **Hàm mới** | Batch resolver (đọc thẳng từ `doc` đã load sẵn, không có DB round-trip nên không cache). |

---

## Tổng số hàm mới/sửa

| Loại | Số lượng |
|---|---|
| Hàm hoàn toàn mới | 15 (`bom_orchestrator.py` ×3, `fb_config.py` ×1, `glass_group_resolver.py` ×1, `al_supplier_price_list.py` ×1, `install_fb_bindings.py` ×1, `data_source_registry.py` ×8) |
| Hàm sửa thân (chữ ký cũ hoặc mới) | 6 (`_fetch_composite_prices_via_fb`, `_fetch_composite_prices`, `_match_composite_price`, `_color_variable_for_category`, `_handle_linked_doctype_field`, `_resolve_linked_doctype_field_batch`) |
| Field JSON thêm mới | 8 (`represents_color`, `is_active` ×2, `weight_kg_per_m2`, `max_area_m2`, `assigned_to`, `company_representative_signature`, `previous_unit_price`) |
| Field JSON đổi thuộc tính (không đổi tên) | 5 (3 field Site Survey Item → read_only; 2 checkbox Change Order → permlevel=1) |
| File mới | 5 (`fb_config.py`, `patches/v28_12/__init__.py`, `patches/v28_12/set_represents_color_flag.py`, + 2 file `__init__.py`/`.py` bị xoá tính là "diff") |
| File xoá | 1 (`custom_field_quotation.py`, dead code) |
