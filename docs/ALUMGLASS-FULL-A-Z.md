# ALUMGLASS A–Z — toàn bộ DocType, luồng file–hàm, rà soát field

> **Mốc code tài liệu này mô tả**
>
> | | |
> |---|---|
> | App / nhánh | `alumglass` — nhánh `main`, HEAD `f5b769c` (2026-11-19), working tree sạch khi khảo sát |
> | Quy mô | **68 DocType** (46 doc · 21 child · 1 Single) trong 10 module có DocType; 236 file Python, 51 file JS |
> | Phạm vi | Kiến trúc file · luồng runtime B0–B7 · API/hook/patch/JS · catalog từng DocType · rà soát field dư thừa |
> | Mức kiểm chứng | Đọc mã + `rg` toàn repo. **Chưa chạy `bench migrate`, chưa chạy test trên site.** Mọi hành vi là đọc từ mã |
> | Kết luận nhanh | **119/574 field (21 %) có thể rời màn hình mà không đổi một phép tính nào** — 98 ẩn được ngay, 21 bỏ được sau khi soát. Chi tiết + 3 phương án ở **mục 9** |
> | Quan hệ tài liệu | Đây là bản A–Z **hiện hành** cho **DocType + luồng + field**, thay phần đó của `docs/DANH-GIA-TOAN-DIEN-ALUMGLASS.md` (bản cũ còn viết `AL Slug Library` và `AL Variable Dimension Mapping` *thiếu* `is_active` — nay cả hai **đã có**, xem §8). `docs/BAN-FULL-A-Z.md` là **kế hoạch sửa code**, không phải catalog DocType. `CAU_TRUC_MODULE_VA_DOCTYPE.md` (1 713 dòng, ở **repo root** chứ không phải `docs/`) là bản cũ hơn (61 DocType, v28.8) — giữ để tra lịch sử, ⛔ không dùng làm chuẩn |
>
> **Cách đọc:** mục 1–4 trả lời “hệ thống chạy thế nào”; mục 5 trả lời “DocType này là gì, ai dùng”;
> mục 6–7 trả lời “field nào dư, quy trình bỏ thế nào”; **mục 8 là chi tiết từng field** (mục đích,
> đường vào engine, mức cần thiết); **mục 9 là phân tích độ phức tạp và phương án bỏ bớt**.

**Mục lục**

1. Bản đồ file và phân lớp
2. Luồng tính giá B0–B7 — từng file, từng hàm
3. Các luồng còn lại (báo giá, chốt đơn, biến, Excel)
4. Hook · API · patch · JS · in ấn
5. Catalog 68 DocType theo module
6. Rà soát field dư thừa — phương pháp và kết quả
7. Đề xuất giảm phức tạp (không xoá dữ liệu)
8. Chi tiết từng field — mục đích, đường vào engine, mức cần thiết
9. Phân tích độ phức tạp & phương án bỏ bớt
10. Đọc tiếp

---

## 1. Bản đồ file và phân lớp

### 1.1 Cây thư mục có vai trò

```
alumglass/
├── hooks.py                    # 18 hook đang bật (mục 4.1)
├── modules.txt                 # 12 module, 2 module chưa có DocType (AL Selling, AL HR)
├── patches.txt                 # 4 pre_model_sync + 10 post_model_sync
├── api/
│   ├── __init__.py             # 11 endpoint + helper quyền/async (1 776 dòng)
│   ├── variable_catalog.py     # 5 endpoint catalog biến (416 dòng)
│   ├── formula_registry.py     # get_formula_fields
│   ├── quotation_events.py     # on_submit → ConfigSnapshot
│   └── excel_io.py             # tải mẫu / nhập / xuất Excel
├── engine/
│   ├── bom_orchestrator.py     # ★ B0–B7 (2 783 dòng)
│   ├── composite_pricing.py    # match Item Price composite key
│   └── engine_cache.py         # LRU FormulaEngine theo fingerprint
├── variable_sources/           # registry + 10 adapter + rules + context
├── al_bom_engine/
│   ├── system_variable_resolver.py  # nguồn duy nhất resolve System Variable
│   ├── formula_validate.py          # validate công thức dùng chung
│   ├── glass_group_resolver.py / color_group_resolver.py
│   └── doctype/                     # 12 DocType lõi BOM
├── al_master_data/doctype/     # 20 DocType danh mục + biến
├── al_formula_rules/doctype/   # 8 DocType rule
├── al_buying|stock|manufacturing|construction|account|quality|ai_intelligence/doctype/
├── setup/                      # custom field, role, workflow, print format, seed demo
├── patches/v28_9 … v28_14/     # 14 patch dữ liệu
├── public/js/                  # 6 asset toàn cục + 2 report JS
├── alumglass/doctype/overrides/ # quotation.js, sales_order.js
└── templates/print_formats/bao_gia.html
```

### 1.2 Phân lớp trách nhiệm

| Lớp | File tiêu biểu | Được phép làm gì | ⛔ Không được làm |
|---|---|---|---|
| **Form/UI** | `public/js/*`, `**/*.js` | Thu thập input, gọi API, render kết quả | Tự tính giá, tự ghi DB nghiệp vụ |
| **API** | `api/__init__.py` | Kiểm quyền, chuẩn hoá tham số, gọi engine, chọn sync/async | Chứa công thức tính giá |
| **Engine** | `engine/bom_orchestrator.py` | Đọc snapshot, dựng công thức, tính, ghi kết quả 1 lần | Đọc thẳng form chưa lưu |
| **Master data** | `al_master_data`, `al_formula_rules` | Cung cấp dữ liệu cấu hình | Chứa logic tính |
| **Validate** | `formula_validate.py` | Kiểm cú pháp/biến, cảnh báo | Chặn oan công thức đang chạy |
| **Setup** | `setup/*.py`, `hooks.py` | Tạo field/role/workflow/in ấn idempotent | Sửa dữ liệu nghiệp vụ |

### 1.3 Quy ước dữ liệu xuyên suốt

| Khái niệm | Nơi lưu | Ai ghi | Ai đọc |
|---|---|---|---|
| Tham số một dòng báo giá | `Quotation Item.al_bom_vars` (JSON) | Dialog Tham số BOM | B1 |
| Cấu trúc dòng BOM | `AL BOM Version.bom_set_snapshot` (JSON) | `AL BOM Version` khi tạo/publish | B2 |
| Bảng giá thành | `AL BOM Version.cost_template_snapshot` (JSON) | `AL BOM Version` | B6 |
| Kết quả tính | `Quotation Item.al_bom_result` (JSON) | B7 (một `set_value`) | Client, `get_result_display`, submit |
| Ảnh chụp để tái lập | `ConfigSnapshot` | `Quotation.on_submit` | Tra cứu/audit |

---

## 2. Luồng tính giá B0–B7 — từng file, từng hàm

### 2.1 Sơ đồ gọi

```
Quotation Item (quotation.js)
  → _sync_row_to_db()                     # bắt buộc ghi DB trước khi tính
  → alumglass.api.calculate_bom(quotation_item_name)
     → _require_quotation_item_permission  # cổng quyền duy nhất
     → assert_quotation_item_editable      # chặn docstatus 1/2
     → _estimate_bom_line_count + _get_async_threshold (mặc định 150)
        ├─ ≤ ngưỡng: BomOrchestrator.run() đồng bộ
        └─ > ngưỡng: _enqueue_bom_calculation → RQ → publish realtime
     → BomOrchestrator.run()
        B0 → B1 → B2 → B3 → B4 → B5 → B6 → B7 → _build_response
```

### 2.2 Từng bước

| Bước | Hàm (file:line) | Đọc | Ghi / trả | Guard chính |
|---|---|---|---|---|
| **B0** | `b0_version_pinning` (`engine/bom_orchestrator.py:315`) | `Quotation Item.al_bom`, `.al_bom_version`; `AL BOM.current_version`; fallback `_latest_existing_version` (:354) | `self.bom_version`, `self._qi_doc` | Không có version nào → `throw`. ⚠️ Fallback **không lọc `workflow_state`** |
| **B1** | `b1_gather_inputs` (:372) + `_resolve_fb_context` (:739), `_resolve_system_variables` (:611), `_resolve_user_variable_defaults` (:581), `_normalize_percent_inputs` (:549) | `al_bom_vars`; `Formula Global Variable`; FVB `get_live_context`; `AL Variable Library`; `AL Profile System.system_variables`; `AL Calculation Rule` CONSTANT | `self.inputs` phẳng; cờ override `_accessory_set`, `_profile_system`, `_cost_template`, `glass_master_map`, `color_master_map` | User input thắng profile; biến `%` chuẩn hoá về 0–100 |
| **B2** | `b2_prefetch_master_data` (:893) + `_load_accessories` (:835), `_fetch_composite_prices*` (:1597–1845), `_get_dim_*` (:1182–1320), `_resolve_color_override` (:1914) | `AL BOM Version.bom_set_snapshot`; `AL Accessory Set`; `Item`; `Item Price`; `AL Glass Master`; `AL Material Category`; `AL Dynamic Item Rule`; `AL Variable Dimension Mapping`; `AL Pricing Dimension`; FVB | `self.bom_items`, `self.row_literals`, `self._glass_data`, cache giá/tiền tệ | Thiếu snapshot → `throw`; thiếu giá: FB path trả 0 + warning, fallback **throw** |
| **B3** | `b3_build_formulas` (:2003) + `_normalize_items_ref` (:2181) | `AL Bom Set.formula_fieldnames`, `apply_scrap_pct`; `AL Quantity Calc Method.input_vars` | `self.bom_formulas`; `inputs["items"]`; synthetic `{slug}__unit_qty/total_qty/line_total` | `items.X.Y` → `X__Y`; chỉ regex slug `\w-` |
| **B4** | `b4_calculate_bom_items` (:2217) + `_validate_glass_max_area` (:2316) | `BOM_ENGINE_CACHE`; `AL Quantity Calc Method.output_unit` | `self.bom_result`, `self.inputs` cập nhật | Diện tích kính > `max_area_m2` → **warning**, không chặn |
| **B5** | `b5_aggregate_cost_buckets` (:2351) + `_resolve_cost_buckets_via_fb` (:2377) | `AL Cost Bucket.source_type/source_config`; FVB batch | `self.buckets` | `source_type` lạ → warning; lỗi FB → fallback sum Python |
| **B6** | `b6_calculate_cost_template` (:2468) + `_resolve_final_price` (:2601), `_resolve_pre_vat_price` (:2611) | `AL Cost Template` (override) hoặc `cost_template_snapshot`; `COST_ENGINE_CACHE` | `self.cost_result`, `gia_vat`, `gia_ban`, trace, errors | Thiếu snapshot → bỏ qua B6, không throw |
| **B7** | `b7_save_results` (:2624) + `_recalculate_quotation_totals` (:2677) | `bom_result`, `cost_result` | **Một** `frappe.db.set_value` cho `al_gia_vat`, `al_gia_ban`, `al_bom_result`, `rate`; cập nhật tổng Quotation với `update_modified=False`; 1 `commit` | Guard lại editable (:2651); chặn Pricing Rule đổi giá (:2737) |
| **Kết** | `_build_response` (:2770) | state engine | `{buckets, cost_template, lines, errors}` | ⚠️ **Không** có `gia_vat`/`gia_ban` top-level |

### 2.3 Năm điểm dễ vỡ của luồng

1. **Client đọc `GIA_BAN`/`GIA_VAT` cố định.** `quotation.js:1456` và `:2212–2221` lấy
   `cost_template.GIA_BAN` để ghi `rate`, trong khi B7 ghi `rate` theo cờ `is_final_price` /
   `is_pre_vat_price`. Nếu template đặt cờ ở line_code khác, client **ghi đè rate = 0**; chỉ
   `get_result_display.summary` là đúng theo cờ.
2. **“Không tìm thấy giá” đổi hành vi theo số binding.** Đúng 1 binding
   `aluminum_price_composite` → FB path `allow_missing=True` (0 + warning); 0 hoặc ≥2 binding →
   fallback `allow_missing=False` → `throw`. Thêm/xoá một binding đổi lỗi cứng thành giá 0 im lặng.
3. **Bắt buộc ghi DB trước khi tính.** Engine đọc `al_bom_vars` từ DB; client phải
   `_sync_row_to_db` và tự vá `frm.doc.modified` sau `frappe.client.set_value` trên bảng con
   (`quotation.js:494–514`). Hai request đồng thời dễ `TimestampMismatchError` / tính dữ liệu cũ.
4. **Cross-row phụ thuộc normalize của Formula Builder.** Fallback regex chỉ khớp `items.\w+.\w+`;
   slug có ký tự lạ hoặc dạng index sẽ không thành `X__Y`, engine trả 0 âm thầm.
5. **B0 có thể pin version Draft.** Fallback lấy `creation DESC` mà không lọc `workflow_state`;
   version Draft vẫn có snapshot nhờ `before_insert`, nên có thể tính bằng bản chưa publish.

---

## 3. Các luồng còn lại

### 3.1 Mở dialog Tham số BOM

```
quotation.js ItemParamDialog (:551)
  → get_variable_set_for_bom (api/__init__.py:1083)
     → AL BOM → AL Bom Set → AL Variable Set/Item/Library
     → AL Profile System, AL Product Type, AL Accessory Set,
       AL Glass Master, AL Color Standard
  → người dùng nhập biến/kính/màu
  → _save (:1540) ghi Quotation Item.al_bom_vars + item_code + al_bom + al_bom_version
```

### 3.2 Preview và Tính giá

- Preview: `get_result_display` (`api/__init__.py:1611`) đọc `al_bom_result` đã lưu, dựng
  `summary/lines/buckets/cost_template/errors`; **không** chạy lại engine.
- Tính giá: `calculate_bom` (`api/__init__.py:11`) → engine; chạy dài thì đẩy RQ, client nghe
  realtime `alumglass_bom_calc_done` (`quotation.js:1285`, `:1776`).
- Nút form-level “Tính tất cả”: `_calc_all_items` (`quotation.js:2132`) gọi tuần tự từng dòng.

### 3.3 Chốt báo giá

`Quotation.on_submit` (`quotation_events.py:21`) → mỗi dòng có `al_bom_result` tạo một
`ConfigSnapshot`, ghi `Quotation Item.al_config_snapshot`. Không tính lại.

### 3.4 Xem trước Cost Template

`AL Cost Template.preview_cost_template` (`al_cost_template.py`) dựng `FormulaEngine` với
`inputs_json` giả định, trả kết quả từng dòng. Endpoint `preview_cost_template` kiểm quyền đọc
template trước khi gọi.

### 3.5 Catalog biến (v28_14)

```
Form mở → formula_setup.js fetch
  → get_formula_context (api/__init__.py:658)
     ├─ có profile → variable_catalog.get_variable_catalog
     │    → 10 adapter → rules.select_candidates → dedupe/build_groups
     │    → build_references (cross_row / slug_reference / legacy)
     └─ không profile → 8 nhóm legacy + AL Slug Library
Validate → build_known_names(include_all_sources=True) → bỏ qua profile
```

### 3.6 Excel I/O

`api/excel_io.py`: `download_template` (:479) trả file mẫu; `upload` (:541) đọc/validate/ghi;
`export_xlsx` (:645) xuất dữ liệu. Client dùng `public/js/excel_io.js`.

---

## 4. Hook · API · patch · JS · in ấn

### 4.1 Hook đang bật (`alumglass/hooks.py`)

| Hook | Dòng | Đích | Việc làm |
|---|---|---|---|
| `required_apps` | 13 | `formula_builder` | Bắt buộc |
| `app_include_js` / `_css` | 16–29 | 6 JS + 1 CSS | Nạp toàn Desk |
| `doctype_js` | 36–39 | `Quotation`, `Sales Order` | Gắn override JS |
| `fixtures` | 42–54 | Custom Field (15 doctype), Role (5) | Đồng bộ khi migrate |
| `Quotation.on_submit` | 58–61 | `quotation_events.on_submit` | Tạo ConfigSnapshot |
| `AL Bom Item.validate` | 65–67 | `backfill_input_vars` | Bổ sung key `input_vars` |
| `AL Quantity Calc Method.on_update/on_trash` | 72–75 | `api.on_calc_method_change/trash` | Xoá cache `calc_fn` |
| `fb_source_types` | 82–85 | 2 handler | Đăng ký nguồn dữ liệu FB |
| `after_install` / `after_migrate` | 195 / 239 | `_after_install`, `_after_migrate` | Field, role, in ấn, binding; ⛔ **không** chạy workflow (comment) |

⛔ `scheduler_events` bị comment toàn bộ; `whitelisted_methods` là danh sách tra cứu, **không phải hook**.

### 4.2 API

| Endpoint | Dòng | Vai trò |
|---|---|---|
| `calculate_bom` | `api/__init__.py:11` | Tính giá 1 dòng; sync/async |
| `preview_cost_template` | :297 | Xem trước template |
| `get_slug_info` | :307 | Tra slug |
| `resolve_item_rule` | :317 | Tra item theo rule |
| `get_bom_structure` | :328 | Cấu trúc BOM |
| `get_cost_template_context` | :337 | **Deprecated** |
| `get_formula_context` | :658 | Context biến cho autocomplete/validate |
| `get_allowed_formula_functions` | :980 | Whitelist hàm custom |
| `get_variable_set_for_bom` | :1083 | Biến + lựa chọn cho dialog |
| `product_item_query` | :1456 | Link query Item nhóm `SAN_PHAM` |
| `get_result_display` | :1611 | Display model từ `al_bom_result` |
| `get_formula_fields` | `formula_registry.py:101` | Registry field công thức |
| `get_variable_catalog` | `variable_catalog.py:274` | Catalog đã lọc profile |
| `get_row_literal_names` | :293 | Row literal đang bật |
| `get_variable_profile` | :317 | Profile của bản ghi |
| `preview_variable_catalog` | :325 | Preview theo profile |
| `explain_variable` | :339 | Giải thích vì sao thấy/không thấy |

Quyền: `_require_quotation_item_permission` (:79) là cổng duy nhất của luồng ghi vì B7 dùng
`db.set_value`; các endpoint khác dùng `_require_doctype_read_permission` (:101).

### 4.3 Patch (`alumglass/patches.txt`)

| Thời điểm | Patch | Tác động |
|---|---|---|
| pre_model_sync | `v28_9.backfill_pricing_dimension_snapshot` | Snapshot pricing cho version Published |
| pre | `v28_9.create_bao_gia_print_format` | Tạo Print Format |
| pre | `v28_9.seed_fvb_from_variable_library` | Seed FVB |
| pre | `v28_9.normalize_percent_system_vars` | Chuẩn hoá biến % |
| post | `v28_9.backfill_glass_master_item_code` | Gán Item code cho Glass Master |
| post | `v28_9.backfill_profile_system_variables` | Sinh child variable từ `offset_*` |
| post | `v28_10.rebackfill_snapshot_category_final_price` | Bổ sung field vào snapshot |
| post | `v28_11.seed_fvb_full_from_variable_library` | Seed FVB đầy đủ |
| post | `v28_11.migrate_cost_bucket_aggregate_to_aggregate_from_items` | Đổi source_type bucket |
| post | `v28_11.rebackfill_cost_template_pre_vat_price` | Thêm `is_pre_vat_price` |
| post | `v28_12.set_represents_color_flag` | Gắn cờ màu đại diện |
| post | `v28_13.fix_cost_template_div_by_zero` | Vá chia 0 |
| post | `v28_14.seed_variable_catalog` | Seed 3 profile + Settings + Formula Field |
| post | `v28_14.seed_bom_profile` | Seed `P_BOM_DEFAULT` |

### 4.4 Client JS

| File | Vai trò | API gọi | Cache |
|---|---|---|---|
| `report/report_aggregation_core.js` | Total Row: sum/avg/min/max/count/sumif | — | `localStorage` |
| `report/report_agg_dropdown.js` | Dialog chọn hàm tổng | — | không lưu (mở lại là mặc định) |
| `formula_setup.js` | Context biến + registry `AL Formula Field` | `get_formula_context`, `get_formula_fields` | 5 phút / 60 giây |
| `cost_template.js` | Validate, preview, inject context | `get_formula_context`, `validate_formula`, `get_allowed_formula_functions`, `preview_cost_template` | Theo `docname` |
| `grid_placeholder.js` | Placeholder grid | — | — |
| `excel_io.js` | Tải mẫu/nhập/xuất | `excel_io.*` | Cờ busy |
| `overrides/quotation.js` | Dialog tham số, tính giá, preview, nút form | `get_variable_set_for_bom`, `calculate_bom`, `get_result_display` | Không cache dữ liệu |
| `overrides/sales_order.js` | Formula Builder trên Sales Order | API Formula Builder | — |

### 4.5 In ấn / báo cáo

- Print Format `Báo giá AlumGlass` tạo bởi `setup/print_format.py:20`, template
  `templates/print_formats/bao_gia.html`; gọi ở after_install/after_migrate và patch v28_9.
- **Không có report server-side** trong app; chỉ 2 JS tổng hợp client.

---

## 5. Catalog 68 DocType theo module

> Cột “Consumer” chỉ nêu nơi **đọc/ghi bằng code**. “Chỉ form/sidebar” nghĩa là không thấy
> consumer ngoài giao diện — đây là ứng viên ở mục 6.
>
> Một số dòng **gộp nhiều DocType** bằng ký hiệu `+` (thường là DocType cha + bảng con của nó),
> nên số dòng ít hơn số ở tiêu đề mục — tiêu đề là số DocType thật trong module.

### 5.1 AL Master Data — 20 DocType

| DocType | Loại | Vai trò | Controller chính | Consumer |
|---|---|---|---|---|
| AL Slug Library | doc | Danh mục slug vật tư | — | `al_bom_item.get_slug_info`, engine |
| AL Material Category | doc | Nhóm vật tư + pattern/bucket mặc định | — | B2, `formula_handlers`, `get_category_requirements` |
| AL Profile System (+ Variable) | doc + child | Hệ nhôm, offset, biến hệ | — | B1/B2, `system_variable_resolver` |
| AL Color Standard | doc | Màu + hệ số giá/tồn | — | `color_group_resolver`, B2 |
| AL Glass Type | doc | Loại kính | — | Link từ Glass Master |
| AL Glass Master | doc | Thông số kính | — | B2, `fb_handlers.glass_master_data` |
| AL Product Type | doc | Loại SP + NC/LD/margin | — | B1/B2, variable set |
| AL Pricing Dimension | doc | Chiều giá động | validate/after_insert/on_update | B2, snapshot, FB handler |
| AL Variable Dimension Mapping | doc | Map biến → chiều giá | — | `fb_handlers`, catalog |
| AL Formula Field | doc | Sổ field công thức | validate | `formula_registry`, JS |
| AL Variable Library | doc | Danh mục biến | validate | B1, resolver, adapter |
| AL Variable Set (+ Item) | doc + child | Bộ biến theo sản phẩm | before_save (item) | Adapter `variable_set`, API |
| AL Variable Profile (+ Rule, Cross Row) | doc + 2 child | Lọc/gợi ý biến | validate | Catalog, JS, validate |
| AL Variable Settings (Single) | single | Cấu hình chung biến | — | Adapter, API, BOM item/set |
| AL Common Variable / AL Row Literal | child | Khai báo biến chung/literal | — | Adapter qua Settings |

### 5.2 AL Bom Engine — 12 DocType

| DocType | Loại | Vai trò | Controller chính | Consumer |
|---|---|---|---|---|
| AL BOM | doc | Định nghĩa BOM, version hiện hành | validate, create_bom_version, get_bom_structure | Engine B0/B2, API |
| AL Bom Set (+ Item) | doc + child | Bộ dòng BOM chuẩn | validate, clone, cross-row checks | B2/B3, dialog |
| AL BOM Version (+ Change Log) | doc + child | Snapshot bất biến | before_insert, validate, on_update, snapshot | B0/B2/B6, submit |
| AL Accessory Set (+ Item) | doc + child | Bộ phụ kiện | validate, `_cross_row_fields` | B2, adapter |
| AL Cost Template (+ Item) | doc + child | Dòng công thức giá | validate, preview | B6, JS |
| AL Cost Bucket | doc | Bucket chi phí | validate source_config | B5, adapter |
| AL Design Revision | doc | Yêu cầu sửa thiết kế | on_update | Workflow khai nhưng **chưa cài** (`hooks.py:191`) |
| ConfigSnapshot | doc | Ảnh chụp lần tính | autoname | Submit Quotation |

### 5.3 AL Formula Rules — 8 DocType

| DocType | Loại | Vai trò | Controller chính | Consumer |
|---|---|---|---|---|
| AL Calculation Rule (+ Threshold/Lookup) | doc + 2 child | Rule constant/threshold/lookup | validate, resolve | `_lookup_rule`, resolver |
| AL Dynamic Item Rule (+ Threshold/Lookup) | doc + 2 child | Rule chọn item | validate, resolve, resolve_item | B2, API |
| AL Dynamic Item Rule Version | doc | Version rule (workflow) | — | Workflow chưa cài; **engine không đọc** — sửa rule là mọi lần tính dùng bản mới |
| AL Quantity Calc Method | doc | Pattern tính SL + calc_fn | validate calc_fn, cache hooks | `formula_handlers`, B3/B4 |

### 5.4 AL Buying — 5 DocType

| DocType | Loại | Vai trò | Controller chính | Consumer |
|---|---|---|---|---|
| AL Material Plan (+ Item) | doc + child | Kế hoạch vật tư, thiếu hụt | validate, aggregate_requirements | **Không caller** cho API |
| AL Supplier Price List (+ Item) | doc + child | Giá NCC, FX | validate, backfill | Nội bộ controller |
| AL Cost Variance | doc | Ước tính vs thực tế | — | Chỉ form |

### 5.5 AL Stock / Manufacturing / Construction / Account / Quality / AI — 23 DocType

| Module | DocType | Loại | Vai trò | Consumer |
|---|---|---|---|---|
| Stock | AL Project Warehouse Map | doc | Map dự án → kho | Chỉ form |
| Manufacturing | AL Cutting Standard | doc | Chuẩn cắt/tolerance | `al_site_survey` đọc tolerance |
| Manufacturing | AL Cutting Plan Aluminum (+ Item) | doc + child | Kế hoạch cắt nhôm | Chỉ link từ bridge; **không code sinh** |
| Manufacturing | AL Cutting Plan Glass (+ Item) | doc + child | Kế hoạch cắt kính | Chỉ link từ bridge; **không code sinh** |
| Manufacturing | AL Production Order Bridge | doc | Nối BOM Version ↔ Work Order | Custom field; không runtime |
| Construction | AL Installation Team | doc | Đội lắp đặt | Custom field Sales Order; BOM default |
| Construction | AL Site Survey (+ Item) | doc + child | Khảo sát, độ lệch | Chỉ form (đọc Cutting Standard) |
| Construction | AL Installation Order (+ Task) | doc + child | Lệnh lắp đặt | Handover/Progress đọc |
| Construction | AL Installation Progress | doc | Tiến độ ngày | Ghi ngược Order; không ai đọc |
| Construction | AL Installation Cost Actual | doc | Chi phí lắp thực tế | Chỉ form |
| Construction | AL Change Order | doc | Thay đổi phạm vi/giá | Workflow khai nhưng **chưa cài**; custom field |
| Construction | AL Handover Acceptance (+ Punchlist) | doc + child | Nghiệm thu bàn giao | Custom field Payment Entry |
| Account | AL Project Financial Config | doc | Cấu hình tài chính dự án | Chỉ form |
| Account | AL Project Profitability Snapshot | doc | Ảnh chụp lợi nhuận | Chỉ form |
| Quality | AL Warranty Policy | doc | Chính sách bảo hành | Link Product Type; custom field |
| AI | AL Alert Config | doc | Cấu hình cảnh báo | Chỉ validate; **không runtime** |
| AI | AL AI Interaction Log | doc | Log hỏi đáp AI | Chỉ form |
| AI | AL AI Suggestion Log | doc | Log gợi ý AI | Chỉ form |

### 5.6 Bất thường cấu trúc

- **43/68 controller rỗng** (`pass`): phần lớn DocType danh mục/bảng con — bình thường; nhưng
  `AL Accessory Item` rỗng trong khi `AL Bom Item` cùng vai trò có validate.
- **17 DocType không có consumer ngoài form/sidebar** (danh sách đầy đủ ở mục 6.5).
- **Trùng vai:** `AL BOM`/`AL Bom Set`/`AL BOM Version`; `AL Calculation Rule`/`AL Dynamic Item
  Rule`; `AL Cutting Plan Aluminum`/`Glass`; `AL Installation Progress`/`Task`; 4 nơi khai biến.
- **Không có bảng con mồ côi.**

---

## 6. Rà soát field dư thừa

### 6.1 Cách đo — và điều phép đo KHÔNG chứng minh

Đo trên toàn bộ 68 file DocType JSON của nhánh `main` (HEAD `f5b769c`), ngày 2026-11-19.

- **Đơn vị đo:** field khai trong `fields[]`, trừ `Section Break` / `Column Break` / `Tab Break` /
  `Fold` và 11 field chuẩn của Frappe (`name`, `owner`, `creation`, `modified`, `modified_by`,
  `docstatus`, `idx`, `parent`, `parentfield`, `parenttype`, `doctype`). Thực tế **không JSON nào
  khai 11 field đó**, nên phép trừ không đổi số: **777 field khai − 203 break = 574**.
- **Nơi tính là "có dùng":** mọi `.py` · `.js` · `.html` dưới `alumglass/` — **kể cả** controller và
  JS của chính DocType, và `patches/`, `setup/`, `tests/` — cộng mọi `.json` **trừ** file nằm trong
  `*/doctype/*/`. `docs/**` **không** tính. (`standalone_tests/` nằm ở **repo root**, ngoài glob
  `alumglass/**` nên **không** tính; nếu tính vào thì ra **167**, lệch đúng 1 field —
  `AL Installation Cost Actual.amount`.)
- **Cách so:** tên field khớp **nguyên từ** bằng `(?<!\w)<field>(?!\w)` (nên `snap.<field>` vẫn tính).
- **"Không dùng"** = không khớp ở đâu trong phạm vi trên.

⚠️ Con số **phụ thuộc quy tắc loại trừ**, nên ghi kèm để khỏi tranh cãi khi chạy lại:
loại **toàn bộ** file trong thư mục `doctype/` (kể cả controller) → **218**; loại **thư mục của
chính** DocType đang xét nhưng vẫn tính JSON khai báo của DocType khác → **172**; theo đúng quy tắc
trên → **168**. Đây là ba quy tắc khác nhau, không phải ba kết quả mâu thuẫn. Script dưới đây tái
lập đúng **168**:

```python
# chạy tại ~/myfrappe/apps/alumglass
import json, re, glob
CORPUS  = [p for e in ("py","js","html") for p in glob.glob("alumglass/**/*."+e, recursive=True)]
CORPUS += [p for p in glob.glob("alumglass/**/*.json", recursive=True) if "/doctype/" not in p]
blob = "\n".join(open(p, encoding="utf-8", errors="ignore").read() for p in CORPUS)
SKIP = {"Section Break","Column Break","Tab Break","Fold"}
STD  = {"name","owner","creation","modified","modified_by","docstatus","idx",
        "parent","parentfield","parenttype","doctype"}
zero = 0
for p in glob.glob("alumglass/**/doctype/*/*.json", recursive=True):
    for f in json.load(open(p)).get("fields", []):
        fn = f.get("fieldname")
        if not fn or f.get("fieldtype") in SKIP or fn in STD: continue
        if not re.search(r"(?<!\w)" + re.escape(fn) + r"(?!\w)", blob): zero += 1
print(zero)   # 168
```

Ba điều phép đo **không** chứng minh — đọc trước khi cắt bất cứ field nào:

1. **Không thấy dữ liệu thật.** Cả lần rà soát này **không truy cập production / DB site nào**.
   Một field 0 tham chiếu vẫn có thể đang chứa dữ liệu người dùng nhập tay hoặc đang lên báo cáo
   làm trên web (Report Builder).
2. **Không thấy nơi dùng ngoài mã:** Print Format viết trên web, Import Excel, Workflow, Dashboard
   Chart, hoặc **app khác** gọi API / đọc dữ liệu (ngoài `formula_builder` — đã khai trong
   `hooks.py`).
3. **Trùng tên làm sai cả hai chiều:** `price_list` trên dòng BOM trùng tên `price_list` của
   `Item Price` (ERPNext) nên bị tính *có dùng* dù engine không đọc; ngược lại có 3 field chỉ chạy
   qua **metadata** nên bị tính *0 tham chiếu* oan — tách riêng ở §6.6.

### 6.2 Con số

| Chỉ số | Số | Ghi chú |
|---|---|---|
| Field khai trong 68 DocType JSON | **574** | Sau khi trừ break + field chuẩn |
| Field **0 tham chiếu** | **168 (29 %)** | 120 nằm trong 17 DocType chưa có runtime **và các bảng con của chúng** (§6.5), 48 nằm trên DocType đang chạy (§6.3–6.4) |
| Field 0 tham chiếu nhưng **đang chạy** qua metadata | **3** | Giữ nguyên — §6.6 |
| Field "có tham chiếu" nhưng thực chất chết | **5** | Chỉ trùng tên / nằm trong comment — §6.4 |

### 6.3 Nhóm A — bỏ được, không cần chờ quyết định sản phẩm

Toàn bộ dưới đây **không nơi nào đọc**, và **đã có đường khác thay thế** cho cùng mục đích.

| DocType | Field (nhãn) | Đường thay thế đang chạy |
|---|---|---|
| AL Bom Item | `price_rule` (Price Rule) · `fixed_price` (Fixed Price) · `price_type` (Price Type) | Giá luôn tra từ `Item Price` theo `price_base_item` / composite key (`bom_orchestrator.py:1066-1081`). `al_bom_item.py:101` ghi rõ engine **không** đọc `price_type` |
| AL Bom Item | `price_list` (Price List) | Bảng giá do binding `_active_price_list()` quyết định (`bom_orchestrator.py:1066`) — **không** đọc trên dòng BOM |
| AL Bom Item | `formula_set` (Formula Set) | Công thức nay do `AL Cost Template.variable_profile` + Formula Builder (`AL Formula Field`) lo |
| AL Bom Item | `cut_fee_pct` (Cut Fee %) | Không nơi nào đọc. Chi phí cắt phải đi qua dòng bucket/công thức nếu cần |
| AL BOM | `pk_set` (Accessory Set) | Phụ kiện đi qua DocType `AL Accessory Set` (engine đọc trực tiếp); cờ này không nơi nào đọc |
| AL BOM | `requires_approval_for_new_version` | Cờ **không được đọc ở đâu**. Workflow duyệt có khai cho `AL BOM Version` (`setup/install_workflows.py:49-65`) nhưng **lệnh cài bị comment** ở `hooks.py:191` và `:235` ⇒ site mới migrate **không có** workflow; đừng tin dòng "★ ĐÃ BẬT" ngay trên đó |
| AL Cost Bucket | `default_expense_account` | Chưa nối hạch toán; B5 chỉ dùng `source_type` / `source_config` |
| AL Cost Template Item | `show_on_quotation` | Báo giá lấy theo `is_final_price` / `is_pre_vat_price`; cờ này không nơi nào đọc |
| ConfigSnapshot | `snapshot_id` | Nơi tạo snapshot (`api/quotation_events.py:28-62`) chỉ ghi 5 field: `bom_version`, `quotation_item_name`, `calculation_timestamp`, `inputs_json`, `result_json` |
| AL Dynamic Item Rule Version | `rule_snapshot_json` | Không nơi nào ghi lẫn đọc |

**Không nằm trong bảng này — cờ của tính năng chưa từng được cài** (không có "đường thay thế" nào
đang chạy, nên xếp `ẨN` chứ không `BỎ`): `AL Bom Item.item_fallback`, `allow_sales_override`,
`override_item_group`, `allow_substitute`, `substitute_item_group`, `panel_count_formula`,
`qty_per_panel_formula`, `panel_glass_override_allowed`; `AL Cost Bucket.batch_group`;
`ConfigSnapshot.fb_snapshot_id`, `rule_version_ids`. Xoá chỉ đúng khi chốt là **không làm** các
tính năng đó.

(`AL Alert Config` — cả DocType — không nằm trong bảng này vì bỏ nó là bỏ một DocType, không phải
bỏ field; xem §7.2 P5.)

### 6.4 Nhóm B — 0 tham chiếu, nhưng phải chốt với người dùng trước khi bỏ

Đây là **dữ liệu danh mục hoặc field của luồng nghiệp vụ chưa làm**. Bỏ hay giữ là quyết định
sản phẩm, không phải quyết định kỹ thuật — cần xem dữ liệu thật rồi mới cắt.

> Mục này xếp theo **mức chắc chắn của dữ liệu**, không theo nhãn §8; chỗ lệch đã ghi ở §9.7.

| DocType | Field | Nhận định |
|---|---|---|
| AL Glass Master | `weight_kg_per_m2` · `u_value` · `shgc` · `vlt` | Thông số kỹ thuật kính. Không mã nào đọc — nhưng có thể cần cho in ấn / đối chiếu khách. **Đo dữ liệu trước** |
| AL Color Standard | `default_safety_stock_qty` · `surcharge_rule` | Không mã nào đọc. (`is_default` không nằm ở đây vì §8 xếp `BỎ` — `is_representative` đã thay) |
| AL Cutting Standard | `jumbo_sheet_size` · `min_offcut_reusable_mm` | Thuộc bài toán tối ưu cắt — chưa có mã nào giải cắt (cùng nhóm với `AL Cutting Plan *`) |
| AL Product Type | `default_warranty_policy` | Nối sang `AL Warranty Policy`, mà `AL Warranty Policy` cũng chưa có runtime |
| AL BOM | `default_installation_team` | Nối sang luồng thi công chưa có runtime |
| AL BOM Version | `valid_to` | Chưa có mã kiểm hiệu lực theo thời gian: B0 lấy version theo `creation DESC` (`bom_orchestrator.py:354-368`), không xét `valid_to` |
| AL Material Plan | `plan_date` | DocType chưa có runtime, nhưng đây là field **bắt buộc người dùng thấy** — §8 xếp `GIỮ` |
| AL Design Revision | `revision_code` · `requested_by` · `revision_type` · `old_spec_json` · `new_spec_json` · `impact_analysis` | DocType có workflow, nhưng mọi field nghiệp vụ **không mã nào đọc** — người dùng nhập rồi để đó |
| AL Installation Order / Task / Site Survey (+Item) | 12 field (`order_code`, `installation_team`, `task_name`, `bom_slug`, `planned_hours`, `survey_code`…) | Cùng lý do: luồng thi công mới có form, chưa có mã |
| AL Pricing Dimension | `is_required_for_price` | Không nơi nào đọc; cổng bắt buộc giá đang do `AL Material Category.requires_price_base_item` lo |

**5 field bị tính "có dùng" oan** (chỉ trùng tên hoặc nằm trong comment): `price_type` (comment +
`seed_demo_data.py`), `price_list` (trùng `Item Price.price_list`), `cut_fee_pct` (trùng tham số
`cut_fee_pct` của template Python trong `formula_builder/templates.py` — khác nghĩa),
`panel_count_formula`, `qty_per_panel_formula` (chỉ 1 dòng comment).

### 6.5 Mười bảy DocType không có mã nào dùng ngoài thư mục của chính nó

**Nhóm 1 — hoàn toàn không có consumer (10):** `AL AI Interaction Log` · `AL AI Suggestion Log` ·
`AL Cost Variance` · `AL Cutting Plan Aluminum` · `AL Cutting Plan Glass` ·
`AL Installation Cost Actual` · `AL Installation Progress` · `AL Project Financial Config` ·
`AL Project Profitability Snapshot` · `AL Project Warehouse Map`.

**Nhóm 2 — chỉ được nhắc trong patch/seed, hoặc bởi DocType cha/con của chính nó (7):**
`AL Change Order` · `AL Dynamic Item Rule Version` · `AL Glass Type` · `AL Handover Acceptance` ·
`AL Installation Team` · `AL Production Order Bridge` · `AL Warranty Policy`.

**Trường hợp riêng — chỉ có `validate()` + seed, không runtime:** `AL Alert Config`.
**Bảng con không có người ghi:** `AL BOM Change Log` (khai trong `AL BOM Version.items` nhưng không
đoạn mã nào tạo dòng).

Hệ quả: **120/168 field 0 tham chiếu** nằm trong nhóm này. Đây không phải "field thừa rải rác" —
nó là **cả một tầng nghiệp vụ đã dựng khung nhưng chưa có mã**, nên cắt field lẻ tẻ ở đây không
giảm được gì; phải quyết ở mức DocType (§7.3).

### 6.6 Field 0 tham chiếu nhưng PHẢI GIỮ

| DocType.Field | Vì sao vẫn sống |
|---|---|
| `AL Alert Config.alert_code` | `autoname = field:alert_code` — Frappe dùng để đặt tên bản ghi |
| `AL Warranty Policy.policy_code` | `autoname = field:policy_code` |
| `AL Installation Cost Actual.reference_doctype` | Là `options` của Link động `reference_docname` — quyết định bảng được trỏ tới |
| Cột hiển thị của bảng con (`AL Cutting Plan Item.bar_number`, `AL Glass Cutting Item.sheet_number`…) | **Không** tính vào con số **3** ở §6.2 (đây là một nhóm, không phải 1 field): không mã nào đọc, nhưng là cột người dùng phải nhìn trên form/in |

Ngoài ra **49/168 field 0 tham chiếu nằm trong bảng con** — phần lớn thuộc 17 DocType ở §6.5
(`AL Bom Item` và `AL Cost Template Item` là hai bảng con **đang chạy**). Với bảng con, bỏ hay giữ
phải nhìn màn hình, không nhìn mã: một cột không mã nào đọc vẫn có thể là cột người dùng phải thấy.

### 6.7 Kết luận của mục 6

1. **Field thừa thật gồm hai nhóm:** 11 field ở §6.3 (đã có đường thay thế) và 11 field là cờ của
   tính năng chưa cài (nhóm `ẨN`, chúng **không** nằm ở §6.3). Việc làm ngay chỉ là **ẩn** (tầng 2);
   **xoá khai báo / xoá cột** theo P4 ở §7.2, không làm ngay.
2. **Phần lớn "0 tham chiếu" không phải field thừa** mà là **17 DocType chưa có runtime**. Cắt field
   ở đó là dọn nhà chưa ở.
3. Trước khi xoá bất cứ field nào thuộc §6.4, **phải đo dữ liệu thật** — việc này chưa làm được
   trong lần rà soát này vì không có quyền vào DB site.

---

## 7. Đề xuất giảm phức tạp

### 7.1 Nguyên tắc: giảm theo tầng, không xoá theo cảm giác

Xoá field trong Frappe có hai cái bẫy: **JSON** chỉ là khai báo, còn **cột trong DB vẫn nằm đó**;
và dữ liệu người dùng đã nhập **không lấy lại được**. Vì vậy đi theo 4 tầng, tầng nào cũng phải
qua được tầng trước.

| Tầng | Việc | Hoàn tác | Rủi ro |
|---|---|---|---|
| 1 | **Đo dữ liệu**: đếm số bản ghi có giá trị khác rỗng cho từng field ứng viên | — | Không |
| 2 | **Ẩn khỏi form** (`hidden: 1` hoặc `depends_on: "0"`) | Đổi lại 1 dòng JSON | Không |
| 3 | **Xoá khai báo** khỏi JSON + `bench migrate` | Trả lại JSON + migrate | Thấp (cột DB còn) |
| 4 | **Xoá cột DB** bằng patch `ALTER TABLE … DROP COLUMN` | Chỉ từ backup | Cao — không hoàn tác được |

Khuyến nghị: **làm tầng 2 cho toàn bộ §6.3 ngay**, tầng 3–4 chỉ sau khi tầng 1–2 chạy ổn một
chu kỳ và Owner xác nhận.

### 7.2 Việc ưu tiên

| Ưu tiên | Việc | Phạm vi | Công | Vì sao trước |
|---|---|---|---|---|
| **P1** | `AL Bom Item`: 10 field ẩn + 6 field xoá · `AL BOM`: 2 field xoá · `ConfigSnapshot`: ẩn 2, xoá 1 · 3 field lẻ xoá (`AL Cost Bucket`, `AL Cost Template Item`, `AL Dynamic Item Rule Version`) | 24 field, 6 DocType (12 ẩn, 12 xoá) | S | `AL Bom Item` có 38 field, 16 trong đó là tàn dư ⇒ bớt nhiễu ngay ở dòng BOM sale nhập |
| **P2** | Quyết định 17 DocType §6.5: **giữ thì ẩn khỏi menu + workspace**, chưa xoá | 17 DocType | S | Bớt 17/68 DocType khỏi menu; chỉ đổi cấu hình hiển thị, đảo ngược được, không mất dữ liệu |
| **P3** | Đo dữ liệu §6.4 rồi chốt bỏ/giữ | các field ở §6.4 | M | Cần DB site; không đo được thì không cắt |
| **P4** | Xoá khai báo + patch xoá cột cho phần đã ẩn ổn định | theo P1/P3 | M | Chỉ nên làm sau khi P1/P2 chạy 1 chu kỳ |
| **P5** | Dọn `AL Alert Config` / `AL BOM Change Log` (không có runtime / không có người ghi) | 2 DocType | S | Hoặc cài runtime, hoặc bỏ — đừng để lửng |

### 7.3 Trước khi xoá một field, phải soát 6 nơi **ngoài** mã

Mã không thấy không có nghĩa là không ai dùng. Với mỗi field sắp xoá, kiểm:

1. **`AL Formula Field`** — bảng đăng ký field công thức (`hooks.py` + `api/formula_registry.py`).
2. **`AL Variable Library` / `AL Variable Profile` / `AL Variable Profile Rule`** — soát
   `name_regex`, `only_fields`, `source_ref` xem có trỏ tới field sắp xoá (sai tên bảng ở bước này
   là bỏ sót đúng chỗ profile đang dùng field).
3. **`AL Slug Library` / `AL Material Category`** — slug hoặc rule tham chiếu tên field.
4. **Property Setter** trên site (đã từng có ca bị ghi đè hàng loạt ở site khác ⇒ đừng giả định
   metadata trên site giống trong repo).
5. **Print Format / Report Builder / Dashboard Chart / Workspace Shortcut** tạo trên web.
6. **Custom Field** do `setup/custom_fields.py` gắn lên DocType lõi — xoá nhầm là vỡ màn hình
   `Quotation`, `Item Price`, `Work Order`.

Thêm một hệ quả cần biết trước: field của `AL Bom Item` đi vào **snapshot** dạng JSON
(`AL BOM Version.bom_set_snapshot`, ghi ở `al_bom_version.py:130-138`, đọc lại ở
`al_material_plan.py:39-41`) và vào **context biến**
(`get_live_context`). Xoá field **không** làm hỏng bản ghi cũ (JSON tự do), nhưng biến sinh từ field
đó **mất nguồn giá trị**: dòng công thức nào còn trỏ tới nó sẽ lỗi `NameError` ngay khi tính
(`engine_core.py:756` chỉ bỏ qua trường hợp `assertion` có `depends_on`). Vì vậy phải soát
§7.3 (1)–(3) trước, đừng chỉ soát mã.

### 7.4 Việc KHÔNG nên làm

- **Không gộp 68 DocType xuống ít hơn bằng cách sáp nhập bảng.** Các cặp "trùng vai" ở §5.6
  (`AL BOM`/`AL Bom Set`/`AL BOM Version`, `AL Calculation Rule`/`AL Dynamic Item Rule`) **khác
  nhau ở vòng đời**: bản ghi cấu hình vs bản ghi phiên bản vs bản ghi ảnh chụp. Gộp là đổi khoá
  ngoại của dữ liệu đã submit — không có đường lùi.
- **Không đổi tên field** để "cho gọn". Mỗi lần đổi là một patch di trú dữ liệu + sửa mọi công thức
  FB đang trỏ tới tên cũ.
- **Không xoá `AL Variable Library`/`AL Variable Profile`** vì "thấy thừa" — đây là nguồn của
  autocomplete và của `cross_row` (§3.5); xoá là mất gợi ý và mất bảng tham chiếu.
- **Không xoá `AL Slug Library`** — đường fallback legacy khi không có profile (§3.5).

### 7.5 Cách nghiệm thu việc giảm phức tạp

Đo lại **sau** khi làm, không đánh giá bằng cảm nhận:

| Chỉ số | Hiện tại | Đo bằng |
|---|---|---|
| Field khai trong JSON | 574 | đếm `fields[]` toàn bộ DocType |
| Field 0 tham chiếu | 168 | chạy lại phép đo §6.1 |
| DocType người dùng thấy trên menu | 68 (khai trong app — **chưa đếm thực tế trên site**) | đếm mục trong Workspace |
| DocType có runtime | 51 (68 − 17) | phép đo §6.5 |
| Thời gian mở form BOM / số field trên form | chưa đo | mở form trên site dev, đếm field hiển thị |

Điều kiện không được làm hỏng: **B0–B7 chạy đúng với một BOM mẫu** và **submit Quotation vẫn tạo
ConfigSnapshot** — hai đường này là nơi mọi field ở §6.3 đang nằm cạnh.

---

## 8. Chi tiết từng field — mục đích, đường vào engine, mức cần thiết

### 8.0 Cách đọc mục này

Mỗi DocType có một khối gồm: **Vai trò** · **Ai dùng** · **Tổng kết** · bảng từng field · **Giảm
phức tạp**. Bảng field trả lời đúng ba câu: field để làm gì, nó **vào phép tính ở đâu** (kèm
`file:dòng`), và **có nên giữ**.

**Năm nhãn — chỉ năm, không có nhãn khác:**

| Nhãn | Nghĩa | Việc làm |
|---|---|---|
| `GIỮ` | Có lệnh thật đọc, hoặc là nhãn/khóa người dùng buộc phải thấy | Không đụng |
| `GỘP` | Trùng nghĩa với field khác **trong cùng** DocType | Gộp vào field được chỉ định |
| `ẨN` | Không lệnh nào đọc, có thể là tính năng dự kiến | Ẩn khỏi form, **chưa xoá** |
| `BỎ` | Không consumer **và** đã có đường khác thay thế | Xoá khai báo — nhưng qua §7.3 trước |
| `CHỜ-DỮ-LIỆU` | Không consumer, chưa biết có dữ liệu thật | Chỉ bỏ sau khi đếm dữ liệu |

**Hai loại số trong tài liệu, đừng cộng lẫn:**

- **Số máy đo (§6.1):** 574 field · 288 có đường vào mã · 118 chỉ hiển thị · 168 không tham chiếu.
  Đếm theo *tên field xuất hiện trong mã*.
- **Số sau khi đọc từng field (§8):** GIỮ 326 · ẨN 98 · BỎ 21 · CHỜ-DỮ-LIỆU 124 · GỘP 5.
  Đếm theo *ý nghĩa field sau khi mở đúng dòng mã*. Một field có thể "máy đếm là có dùng" nhưng vẫn
  `BỎ` vì cái được đếm là **field trùng tên ở DocType khác** — đó chính là lý do phải đọc từng field.

⚠️ **Bẫy trùng tên** đã kiểm từng ca và ghi ngay trong ô "Vào tính toán thế nào": `is_active`,
`price_list`, `status`, `project`, `calc_formula`, `description`, `current_version`,
`item_code`… đều xuất hiện ở nhiều DocType và cả ERPNext.

---

### 8.1 AL Master Data — 20 DocType

Nguồn: `alumglass/al_master_data/doctype/*` + bằng chứng đọc trực tiếp trong `alumglass/`.
Mọi đường dẫn dưới đây tính từ `alumglass/` (trừ khi ghi rõ khác).

---

##### Đọc nhanh nhóm biến — phân biệt 6 DocType dễ lẫn nhất

Đây là chỗ hiểu sai nhiều nhất: **đa số DocType "biến" KHÔNG tham gia tính tiền** — chỉ `AL Variable Library` là nguồn thật.

| DocType | Nó là gì | Có làm đổi số tiền BOM không |
|---|---|---|
| `AL Variable Library` | 1 record = 1 biến: tên, kiểu, và **nguồn giá trị** (`source_doctype`/`source_field`) hoặc `default_value` | **CÓ** — engine resolve ở B1 (`engine/bom_orchestrator.py:611-737`), `var_type=Percent` quyết định chia 100 (`:544`) |
| `AL Variable Set` + `AL Variable Set Item` | Bộ biến **người dùng nhập** khi mở dialog "Tham số BOM" | **KHÔNG trực tiếp** — chỉ dựng form nhập (`api/__init__.py:1151-1184`). Giá trị user nhập mới đi vào engine |
| `AL Variable Profile` | Chọn bộ biến **hiện ra khi gõ công thức** | **KHÔNG** — chỉ lọc autocomplete |
| `AL Variable Profile Rule` | 1 dòng Include/Exclude trong profile | **KHÔNG** |
| `AL Variable Cross Row` | Khai child table nào được gợi ý `items.<slug>.<field>` | **KHÔNG** |
| `AL Common Variable` | Khai **tên** biến người dùng nhập (W_mm, H_mm…) | **KHÔNG** — chỉ tên/nhãn/kiểu để gợi ý + validate |
| `AL Row Literal` | Khai **tên** biến engine inject theo dòng (unit_price, glass_thick…) | **KHÔNG** — xem cảnh báo ở mục `AL Row Literal` |
| `AL Variable Settings` | Single nối các bảng trên | **KHÔNG** (trừ `default_profile` chọn profile mặc định) |

**Nguồn giá trị thật** (đọc DB lúc tính): `AL Variable Library` → `AL Profile System` (+ bảng con), `AL Product Type`, `AL Glass Master`, `AL Material Category`, `AL Color Standard`, `AL Variable Dimension Mapping`, `AL Pricing Dimension`.
**Chỉ metadata gợi ý**: `AL Variable Profile`, `AL Variable Profile Rule`, `AL Variable Cross Row`, `AL Common Variable`, `AL Row Literal`, `AL Formula Field`, `AL Variable Set(Item)`.

Bằng chứng mạnh nhất cho ranh giới này: validate công thức **cố ý bỏ qua profile**
(`al_bom_engine/formula_validate.py:66-70` — "Profile chỉ được lọc GỢI Ý… nếu thu hẹp cả
universe validate thì bật profile là chặn oan các công thức đang chạy").

---

#### AL Color Standard — doc, 9 field

**Vai trò:** Danh mục màu nhôm. Mỗi mã màu mang một hệ số giá; báo giá chọn màu theo vị trí.
**Ai dùng:** engine B2 — tra giá composite, hệ số đọc qua `AL Pricing Dimension.link_doctype`; API dialog hiển thị tên màu; JS lọc danh sách màu đại diện.
**Tổng kết:** 9 field · 2 field vào engine tính toán · 2 field chỉ để cấu hình/hiển thị · 5 field không có tham chiếu · **đề xuất:** giữ 4 / ẩn 3 / bỏ 1 / chờ dữ liệu 1.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `color_code` | Color Code | Data | Mã màu, khóa chính | `fb_handlers.py:243` — `frappe.get_cached_value(link_doctype, var_value, "price_multiplier")`, `var_value` là mã màu; engine cũng dùng làm khóa dòng | GIỮ — khóa chính, tra theo name |
| `color_name` | Color Name | Data | Tên hiển thị của màu | Không vào tính toán — `api/__init__.py:1339` dùng làm nhãn nhóm màu | GIỮ — nhãn người đọc |
| `applies_to` | Applies To | Link | Nhóm hàng áp dụng | Không vào tính toán. Hit duy nhất `al_construction/doctype/al_site_survey/al_site_survey.py:19` là **`AL Cutting Standard.applies_to`** — trùng tên, chưa chắc | ẨN — không consumer, giữ làm dự kiến |
| `is_standard_stock` | Is Standard Stock? | Check | Màu thuộc hàng chuẩn | Không vào tính toán — chỉ `setup/seed_demo_data.py:83` ghi, không ai đọc | ẨN — chỉ seed ghi |
| `is_representative` | Mau dai dien | Check | Màu đại diện cho nhóm chọn | Không vào tính toán — 3 form lọc danh sách màu: `al_bom_set.js:19`, `al_accessory_set.js:17`, `doctype/overrides/quotation.js:1042` | GIỮ — UI đang lọc theo cờ này |
| `is_default` | Mau mac dinh | Check | Màu mặc định | Không vào tính toán — 0 tham chiếu | BỎ — `is_representative` đã thay |
| `price_multiplier` | Price Multiplier | Float | Hệ số giá theo màu | `fb_handlers.py:234` lấy hệ số từ mapping; `:242-243` ưu tiên đọc `price_multiplier` của bản ghi Link (chính là màu này) | GIỮ — engine đọc (động) |
| `default_safety_stock_qty` | Default Safety Stock Qty | Float | Tồn kho an toàn mặc định | Không vào tính toán — 0 tham chiếu | ẨN — chưa có consumer |
| `surcharge_rule` | Surcharge Rule | Link | Luật phụ phí | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — đếm dữ liệu trước khi bỏ |

**Giảm phức tạp:**
- Bỏ `is_default`: mọi nơi chọn màu đã lọc bằng `is_representative`.
- Ẩn `applies_to`, `default_safety_stock_qty`, `surcharge_rule` khỏi form (không xoá).
- Đếm dữ liệu 3 field ẩn trước khi quyết định xoá hẳn.

---

#### AL Common Variable — bảng con, 7 field

**Vai trò:** Bảng con của `AL Variable Settings`. Khai các biến người dùng nhập khi mở dialog Tham số BOM (W_mm, H_mm, n_panel…). Trước đây danh sách này viết cứng trong code.
**Ai dùng:** catalog gợi ý (`variable_sources/adapters.py:672-701`) và API `get_formula_context` (`api/__init__.py:836-848`). **Không engine nào đọc bảng này.**
**Tổng kết:** 7 field · 0 field vào engine tính toán · 7 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 7, cân nhắc gộp với `AL Row Literal`.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `var_name` | Tên biến | Data | Tên biến dùng trong công thức | Không vào tính toán — `variable_sources/adapters.py:681` đọc làm tên gợi ý; `api/__init__.py:512` dựng danh sách validate | GIỮ — nguồn tên biến |
| `var_label` | Nhãn hiển thị | Data | Nhãn tiếng Việt | Không vào tính toán — `api/__init__.py:517` trả về client | GIỮ — nhãn người đọc |
| `var_type` | Kiểu | Select | Kiểu dữ liệu để dựng ô nhập | Không vào tính toán — `api/__init__.py:518` trả `type` cho dialog chọn ô nhập | GIỮ — quyết định ô nhập |
| `group_label` | Nhóm hiển thị | Data | Nhóm trong autocomplete | Không vào tính toán — `api/__init__.py:519`; `variable_sources/adapters.py:693` | GIỮ — gom nhóm gợi ý |
| `sort_order` | Thứ tự | Int | Thứ tự trong nhóm | Không vào tính toán — `api/__init__.py:508-509` sắp danh sách; `adapters.py:694` | GIỮ — thứ tự gợi ý |
| `is_active` | Đang dùng | Check | Bật/tắt biến | Không vào tính toán — `variable_sources/adapters.py:679`, `api/__init__.py:507` | GIỮ — tắt được biến |
| `description` | Mô tả | Small Text | Giải thích biến | Không vào tính toán — `api/__init__.py:520`, `adapters.py:698` | GIỮ — trợ giúp người nhập |

**Giảm phức tạp:**
- Gộp `AL Common Variable` + `AL Row Literal` thành 1 bảng + cột "nguồn giá trị": 2 bảng hiện có **cùng 7 field, cùng 1 Single cha**.
- Nếu không gộp: chỉ cần 5 field (`var_name`, `var_label`, `var_type`, `sort_order`, `is_active`); `group_label`/`description` có thể gộp vào nhãn.
- Không thêm cột "engine đọc" vào bảng này — sẽ gây hiểu sai.

---

#### AL Formula Field — doc, 7 field

**Vai trò:** Sổ đăng ký "field nào trên doctype nào có công thức", thay danh sách cứng `FORMULA_DOCTYPE_REGISTRY` trong JS. Thêm field công thức = thêm 1 record, không sửa JS.
**Ai dùng:** API `get_formula_fields` (`api/formula_registry.py:101-157`) → JS `alumglass.FormulaFields` gọi lúc refresh form. **Không engine nào đọc.**
**Tổng kết:** 7 field · 0 field vào engine tính toán · 7 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 7.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `target_doctype` | Doctype | Link | Doctype đích | Không vào tính toán — `api/formula_registry.py:125-135` lọc + trả key `doctype` cho JS | GIỮ — khóa đăng ký |
| `child_table` | Child table | Data | Bảng con chứa field (rỗng = field trên chính doctype) | Không vào tính toán — `api/formula_registry.py:133`, `:149` | GIỮ — phân biệt field cha/con |
| `fieldname` | Fieldname | Data | Tên field có công thức | Không vào tính toán — `api/formula_registry.py:134-150`; controller chặn trùng bộ 3 khóa (`al_formula_field.py:18-48`) | GIỮ — khóa đăng ký |
| `id_field` | ID field | Data | Field định danh dòng của bảng con (mặc định `slug`) | Không vào tính toán — `api/formula_registry.py:151` trả cho JS dựng tham chiếu dòng | GIỮ — cần cho bảng con |
| `editor_opts` | Editor Options | JSON | Tuỳ chọn editor (cao, popup số) | Không vào tính toán — `api/formula_registry.py:152` parse, hỏng thì `{}` | GIỮ — tuỳ chọn hiển thị |
| `sort_order` | Thứ tự | Int | Thứ tự field trong form | Không vào tính toán — `api/formula_registry.py:134` dùng `order_by` | GIỮ — thứ tự hiển thị |
| `is_active` | Đang dùng | Check | Bật/tắt đăng ký | Không vào tính toán — `api/formula_registry.py:124` lọc `is_active: 1` | GIỮ — tắt được field |

**Giảm phức tạp:**
- `id_field` mặc định `"slug"` (`api/formula_registry.py:151`) — với bảng con không có `slug` sẽ trả tên sai mà không báo.
- Đã có validate chống trùng bộ 3 khóa trong controller; nên nêu rõ trong mô tả field để người nhập không tạo bản ghi trùng.
- `editor_opts` là JSON tự do — chỉ cần 2 khóa đang dùng, nên ghi ví dụ trong mô tả.

---

#### AL Glass Master — doc, 10 field

**Vai trò:** Danh mục kính: độ dày, loại, khổ tối đa nhà cung cấp sản xuất được. Mỗi mã kính là 1 lựa chọn ở dialog "Kính theo vị trí".
**Ai dùng:** engine B2 (batch query lấy `glass_thick`/`glass_type`/`max_area_m2`), validate diện tích kính ở B4/B5, FB handler `glass_master_data`.
**Tổng kết:** 10 field · 4 field vào engine tính toán · 1 field chỉ để cấu hình/hiển thị · 5 field không có tham chiếu · **đề xuất:** giữ 5 / ẩn 4 / bỏ 1.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `glass_code` | Glass Code | Data | Mã kính, khóa chính | `engine/bom_orchestrator.py:967-968` tra theo `name`; `fb_handlers.py:303` đọc bản ghi theo mã này | GIỮ — khóa chính |
| `glass_name` | Glass Name | Data | Tên kính | Không vào tính toán — chỉ seed ghi (`setup/seed_demo_data.py:95`) và patch đọc (`patches/v28_9/backfill_glass_master_item_code.py:32`) | GIỮ — nhãn người đọc |
| `total_thick_mm` | Total Thickness (mm) | Float | Tổng độ dày (mm) | `engine/bom_orchestrator.py:974-977` → `glass_thick`; `fb_handlers.py:303-306` | GIỮ — engine dùng |
| `glass_type` | Glass Type | Link | Loại kính | `engine/bom_orchestrator.py:974-978` → `glass_type`; `fb_handlers.py:303-307` | GIỮ — engine dùng |
| `item_code` | Item Code | Link | Mã Item tương ứng | Không vào tính toán — **chỉ patch một lần ghi** (`patches/v28_9/backfill_glass_master_item_code.py:38-40`), không ai đọc. Engine tra giá kính theo `glass_code` | BỎ — engine tra theo `glass_code` |
| `weight_kg_per_m2` | Weight (kg/m²) | Float | Trọng lượng riêng | Không vào tính toán — 0 tham chiếu (trọng lượng lấy từ `Item.weight_per_unit`, `bom_orchestrator.py:1132`) | ẨN — chưa có consumer |
| `u_value` | U-Value | Float | Hệ số truyền nhiệt | Không vào tính toán — 0 tham chiếu | ẨN — chưa có consumer |
| `shgc` | SHGC | Float | Hệ số nhiệt mặt trời | Không vào tính toán — 0 tham chiếu | ẨN — chưa có consumer |
| `vlt` | VLT | Float | Độ truyền sáng | Không vào tính toán — 0 tham chiếu | ẨN — chưa có consumer |
| `max_area_m2` | Max Safe Area (m²) | Float | Diện tích tối đa 1 tấm | `engine/bom_orchestrator.py:979` nạp; `:2251-2320` so với `{slug}__unit_qty` và ghi cảnh báo (không chặn) | GIỮ — engine dùng |

**Giảm phức tạp:**
- Bỏ `item_code`: chỉ có 1 patch ghi vào, engine không đọc — giữ lại là bẫy "tưởng engine dùng mã Item".
- Ẩn 4 field thông số kỹ thuật (`weight`, `u_value`, `shgc`, `vlt`) tới khi có nơi đọc.
- Ghi rõ trong mô tả `max_area_m2` rằng đây chỉ là **cảnh báo**, không chặn tính giá.

---

#### AL Glass Type — doc, 2 field

**Vai trò:** Danh mục loại kính, làm đích Link cho `AL Glass Master.glass_type`.
**Ai dùng:** chỉ là đích Link; `type_code` chính là giá trị lưu trong `AL Glass Master.glass_type`. Không engine nào đọc trực tiếp.
**Tổng kết:** 2 field · 1 field vào engine tính toán (gián tiếp qua khóa Link) · 1 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 2.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `type_code` | Type Code | Data | Mã loại, khóa chính | Gián tiếp — `engine/bom_orchestrator.py:974-978` chép giá trị `glass_type` (chính là `type_code`) vào context công thức | GIỮ — khóa chính, đích Link |
| `type_name` | Type Name | Data | Tên loại kính | Không vào tính toán — chỉ seed ghi (`setup/seed_demo_data.py:91,187`) | GIỮ — nhãn người đọc |

**Giảm phức tạp:**
- Đặt `title_field = type_name` để ô Link hiện tên thay vì mã — 1 dòng JSON, không thêm field.
- DocType 2 field: không cần field nào thêm.

---

#### AL Material Category — doc, 12 field

**Vai trò:** Nhóm vật tư (nhôm, kính, thép, phụ kiện…). Quyết định dòng BOM bắt buộc gì, tính số lượng theo pattern nào, hao hụt bao nhiêu.
**Ai dùng:** `AL Bom Item.validate` (chặn save), engine B2 (hao hụt, trọng lượng, nhận diện nhóm kính), `formula_handlers` (lọc pattern), `glass_group_resolver`.
**Tổng kết:** 12 field · 4 field vào engine tính toán · 7 field chỉ để cấu hình/hiển thị · 1 field không có tham chiếu · **đề xuất:** giữ 11 / ẩn 1.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `category_code` | Category Code | Data | Mã nhóm, khóa chính | `engine/bom_orchestrator.py:1008,1116` so `item["category"]` với mã; `:988-990` tra batch | GIỮ — engine dùng |
| `category_name` | Category Name | Data | Tên nhóm | Không vào tính toán — `api/__init__.py:1325` dùng làm nhãn hiển thị | GIỮ — nhãn người đọc |
| `default_calc_pattern` | Default Calc Pattern | Link | Pattern số lượng mặc định | Không vào tính toán trực tiếp — `al_bom_engine/doctype/al_bom_item/al_bom_item.py:203` trả cho client qua API whitelist `get_category_requirements`; engine đọc `calc_pattern` **trên chính dòng BOM** | GIỮ — gợi ý mặc định |
| `default_cost_bucket` | Default Cost Bucket | Link | Nhóm chi phí mặc định | Không vào tính toán — `al_bom_item.py:204` trả cho client cùng API trên | GIỮ — gợi ý mặc định |
| `requires_item_code` | Requires Item Code? | Check | Bắt buộc Item Code | Không vào tính toán — `al_bom_item.py:93` chặn save khi thiếu | GIỮ — cổng kiểm dữ liệu |
| `requires_price_base_item` | Requires Price Base Item? | Check | Bắt buộc mã đại diện tra giá | Không vào tính toán — `al_bom_item.py:108` chặn save | GIỮ — cổng kiểm dữ liệu |
| `requires_glass_master` | Requires Glass Master? | Check | Nhóm này là kính | `al_bom_engine/glass_group_resolver.py:18-22` lọc `requires_glass_master: 1` → tập category kính; `bom_orchestrator.py:1008,1116` dùng tập đó; `formula_handlers.py:293` lọc pattern | GIỮ — công tắc engine |
| `requires_ctx_inject_prefix` | Requires CTX Inject Prefix? | Check | Bắt buộc tiền tố inject | Không vào tính toán — `al_bom_item.py:130` chặn save | GIỮ — cổng kiểm dữ liệu |
| `has_weight` | Has Weight (kg/m)? | Check | Nhóm có trọng lượng | `engine/bom_orchestrator.py:990-993` nạp `has_weight`; `:1142` → cột Trọng lượng ở kết quả; `formula_handlers.py:287-290` lọc pattern | GIỮ — engine dùng |
| `has_dimensions` | Has Dimensions (WxH)? | Check | Nhóm có kích thước | Không vào số tiền — `formula_handlers.py:288-296` lọc pattern cho dropdown | GIỮ — lọc pattern |
| `default_scrap_pct` | Default Scrap % | Float | Hao hụt mặc định | `engine/bom_orchestrator.py:990-992` nạp `scrap_pct`; B3 nhân vào `total_qty`, chỉ khi `AL Bom Set.apply_scrap_pct` bật (`:2034,2138`) | GIỮ — engine dùng (opt-in) |
| `is_active` | Is Active? | Check | Bật/tắt nhóm | Không vào tính toán — **không query nào lọc cờ này của AL Material Category** (các hit `is_active` là của doctype khác) | ẨN — cờ không có tác dụng |

**Giảm phức tạp:**
- `is_active` đang vô tác dụng: hoặc ẩn khỏi form, hoặc thêm filter ở `glass_group_resolver` + batch query — đừng để cờ "trông như tắt được" mà không tắt.
- `default_calc_pattern`/`default_cost_bucket` chỉ là gợi ý client: nếu client không gọi `get_category_requirements` thì 2 field này không có consumer.
- Ghi rõ `default_scrap_pct` chỉ có hiệu lực khi Bom Set bật `apply_scrap_pct`.

---

#### AL Pricing Dimension — doc, 10 field

**Vai trò:** Một chiều giá (màu sắc, xuất xứ, độ dày, bề mặt). Mỗi bản ghi tự sinh 1 Custom Field trên `Item Price` để làm khóa tra giá.
**Ai dùng:** engine tra giá composite (`_get_dim_fieldnames`, `_get_dim_mappings_raw`), FB handler `aluminum_price_composite` (mode `multiplier_chain`), snapshot `AL BOM Version`.
**Tổng kết:** 10 field · 5 field vào engine tính toán · 3 field chỉ để cấu hình/hiển thị · 2 field không có tham chiếu · **đề xuất:** giữ 8 / ẩn 1 / chờ dữ liệu 1.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `dimension_code` | Dimension Code | Data | Mã chiều giá, khóa chính | `engine/bom_orchestrator.py:1200,1204` nối `pricing_dimension` → `custom_fieldname`; `al_pricing_dimension.py:33` sinh tên cột `custom_pd_<code>` | GIỮ — khóa chính |
| `dimension_name` | Dimension Name | Data | Tên chiều giá | Không vào tính toán — `al_master_data/doctype/al_pricing_dimension/al_pricing_dimension.py:108` làm nhãn Custom Field | GIỮ — nhãn người đọc |
| `dimension_type` | Dimension Type | Select | Kiểu dữ liệu của chiều | Không vào phép tính — `al_pricing_dimension.py:109,114,117` quyết định **kiểu cột** sinh trên Item Price mà engine đọc | GIỮ — sinh schema giá |
| `link_doctype` | Link Doctype | Link | Doctype của chiều khi kiểu Link | `fb_handlers.py:239-243` đọc `price_multiplier` của bản ghi Link (vd `AL Color Standard`) trong chế độ `multiplier_chain` | GIỮ — engine dùng |
| `select_options` | Select Options | Small Text | Danh sách chọn khi kiểu Select | Không vào phép tính — `al_pricing_dimension.py:117-118` ghi options cho Custom Field | GIỮ — sinh schema giá |
| `custom_fieldname` | Custom Fieldname | Data | Tên cột thật trên Item Price (tự sinh) | `engine/bom_orchestrator.py:1200,1204` và `fb_handlers.py:148` dùng làm tên cột tra giá | GIỮ — engine dùng |
| `is_required_for_price` | Required for Price? | Check | Bắt buộc khi tra giá | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — đếm dữ liệu trước |
| `is_active` | Is Active? | Check | Bật/tắt chiều giá | `al_bom_engine/doctype/al_bom_version/al_bom_version.py:178-180` chỉ chụp chiều `is_active=1` vào snapshot mà engine đọc | GIỮ — engine dùng khi publish |
| `represents_color` | Represents Color Dimension? | Check | Đánh dấu chiều "màu" | `engine/bom_orchestrator.py:1944-1949` lọc `represents_color: 1` để tìm biến màu của từng nhóm | GIỮ — engine dùng |
| `sort_order` | Sort Order | Int | Thứ tự chiều | Không vào tính toán — 0 tham chiếu (các hit `sort_order` là của `AL Quantity Calc Method`, `formula_handlers.py:319-343`) | ẨN — chưa có consumer |

**Giảm phức tạp:**
- `sort_order` và `is_required_for_price` là 2 field duy nhất không ai đọc — ứng viên ẩn trước.
- Đổi `dimension_type` sau khi đã có dữ liệu sẽ ALTER kiểu cột: controller đã đi qua `cf.save()` để không lệch metadata (`al_pricing_dimension.py:132-145`) — nên giữ nguyên cách này.
- `custom_fieldname` là read-only; đừng cho sửa tay sau khi đã có Item Price.

---

#### AL Product Type — doc, 6 field

**Vai trò:** Loại sản phẩm (cửa đi, cửa sổ…) và tỉ lệ nhân công/lợi nhuận mặc định theo loại.
**Ai dùng:** engine B1 qua System Variables — biến `NC_SX_PCT`, `NC_LD_PCT`, `PROFIT_MARGIN` khai `source_doctype="AL Product Type"` trong `AL Variable Library`.
**Tổng kết:** 6 field · 3 field vào engine tính toán · 2 field chỉ để cấu hình/hiển thị · 1 field không có tham chiếu · **đề xuất:** giữ 5 / ẩn 1.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `type_code` | Type Code | Data | Mã loại, khóa chính | Gián tiếp — là `record_name` mà `al_bom_engine/system_variable_resolver.py:150-153` đọc qua field Link trên `AL Bom Set` | GIỮ — khóa chính |
| `type_name` | Type Name | Data | Tên loại | Không vào tính toán — chỉ seed ghi (`setup/seed_demo_data.py:187`) | GIỮ — nhãn người đọc |
| `nc_pct` | NC SX (%) | Float | % nhân công sản xuất | `system_variable_resolver.py:187` đọc qua `source_field` của biến `NC_SX_PCT`; engine dùng ở B6 | GIỮ — engine dùng |
| `nc_ld_rate` | NC LD Rate (%) | Float | % nhân công lắp đặt | `system_variable_resolver.py:187` qua `source_field` của biến `NC_LD_PCT` | GIỮ — engine dùng |
| `profit_margin` | Profit Margin (%) | Float | % lợi nhuận | `system_variable_resolver.py:187` qua `source_field` của biến `PROFIT_MARGIN` | GIỮ — engine dùng |
| `default_warranty_policy` | Default Warranty Policy | Link | Chính sách bảo hành mặc định | Không vào tính toán — 0 tham chiếu | ẨN — chưa có consumer |

**Giảm phức tạp:**
- 3 field tỉ lệ được đọc **qua tên field khai trong Library**, không qua tên biến: đổi tên `nc_pct` sẽ làm `NC_SX_PCT` mất nguồn mà không báo lỗi. Nên có kiểm khi sửa.
- Ẩn `default_warranty_policy` tới khi có nơi đọc.

---

#### AL Profile System — doc, 9 field

**Vai trò:** Hệ nhôm (Xingfa 55…) kèm 4 khe hở mặc định dùng khi tính kích thước.
**Ai dùng:** engine B1 qua System Variables; bảng con `system_variables` cho override theo hệ.
**Tổng kết:** 9 field · 5 field vào engine tính toán · 3 field chỉ để cấu hình/hiển thị · 1 field không có tham chiếu · **đề xuất:** giữ 8 / ẩn 1, chốt 1 nguồn cho 4 khe hở.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `system_code` | System Code | Data | Mã hệ, khóa chính | Gián tiếp — là `record_name` resolver đọc (`system_variable_resolver.py:150-153`); `api/__init__.py:1133` lấy làm mã hiển thị | GIỮ — khóa chính |
| `system_name` | System Name | Data | Tên hệ | Không vào tính toán — `api/__init__.py:1134` hiển thị ở dialog | GIỮ — nhãn người đọc |
| `brand` | Brand | Link | Hãng nhôm | Không vào tính toán — dialog lấy brand từ **`AL Bom Set.brand`** (`api/__init__.py:1136`), không đọc field này | GIỮ — dữ liệu nghiệp vụ phải thấy |
| `is_active` | Is Active? | Check | Bật/tắt hệ | Không vào tính toán — 0 tham chiếu | ẨN — cờ không có tác dụng |
| `offset_frame` | Offset Frame (mm) | Float | Khe hở khung–cánh | `system_variable_resolver.py:187` đọc qua `source_field` của biến `OFFSET_FRAME` | GIỮ — engine dùng |
| `offset_glass` | Offset Glass (mm) | Float | Khe hở cánh–kính | `system_variable_resolver.py:187` qua biến `OFFSET_GLASS` | GIỮ — engine dùng |
| `offset_fixed` | Offset Fixed (mm) | Float | Khe hở khung–kính cố định | `system_variable_resolver.py:187` qua biến `OFFSET_FIXED` | GIỮ — engine dùng |
| `offset_crossbar` | Offset Crossbar (mm) | Float | Khe hở đố ngang | `system_variable_resolver.py:187` qua biến `OFFSET_DO_NGANG` (tên biến **không** suy từ tên field) | GIỮ — engine dùng |
| `system_variables` | System Variables | Table | Ghi đè giá trị biến theo hệ | `engine/bom_orchestrator.py:697-714` đọc dòng `is_active`; ưu tiên **cao hơn** giá trị đọc từ field nguồn (`system_variable_resolver.py:193-212`) | GIỮ — engine dùng |

**Giảm phức tạp:**
- 4 khe hở đang có **2 nguồn**: field `offset_*` và bảng con `system_variables` (patch `patches/v28_9/backfill_profile_system_variables.py:17-22` chép field sang bảng con). Hai nguồn lệch nhau thì bảng con thắng **âm thầm** — cần chốt 1 nguồn và ghi rõ trên form.
- `is_active` không ai lọc: ẩn hoặc thêm filter, đừng để cờ vô tác dụng.

---

#### AL Profile System Variable — bảng con, 3 field

**Vai trò:** Bảng con của `AL Profile System` — ghi đè giá trị biến hệ thống cho từng hệ nhôm.
**Ai dùng:** engine B1 bước 1.4b (`engine/bom_orchestrator.py:697-714`), resolver dùng chung (`al_bom_engine/system_variable_resolver.py:193-212`), dialog tham số (`api/__init__.py:1209-1217`).
**Tổng kết:** 3 field · 3 field vào engine tính toán · 0 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 3.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `variable` | Variable | Link | Biến được ghi đè | `engine/bom_orchestrator.py:700` lấy tên biến; `system_variable_resolver.py:200` | GIỮ — khóa của dòng |
| `value` | Value | Data | Giá trị ghi đè (số hoặc công thức) | `bom_orchestrator.py:701-714` đọc, thử `float()` rồi ghi vào `self.inputs`; resolver `:202-212` tương tự | GIỮ — engine dùng |
| `is_active` | Is Active | Check | Dùng dòng này hay không | `bom_orchestrator.py:698`, `system_variable_resolver.py:198` bỏ qua dòng tắt | GIỮ — engine dùng |

**Giảm phức tạp:**
- `value` là Data (chuỗi): engine tự đoán số bằng `float()`. Nên validate "phải là số" cho biến có `var_type` số để lỗi hiện lúc save thay vì ra 0 lúc tính.
- Không thêm field — bảng đã tối giản.

---

#### AL Row Literal — bảng con, 7 field

**Vai trò:** Bảng con của `AL Variable Settings`. Khai **tên** các biến engine inject theo từng dòng BOM (`unit_price`, `glass_thick`, `scrap_pct`…).
**Ai dùng:** catalog gợi ý (`variable_sources/adapters.py:628-669`); API `get_row_literal_names` (`api/variable_catalog.py:294-314`) → dùng để **validate** `rule_input_expr` của `AL Bom Set` (`al_bom_engine/doctype/al_bom_set/al_bom_set.py:13-28`). **Không engine nào đọc bảng này để lấy giá trị.**
**Tổng kết:** 7 field · 0 field vào engine tính toán · 7 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 7, nhưng sửa mô tả.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `var_name` | Tên biến | Data | Tên biến inject theo dòng | Không vào tính toán — `variable_sources/adapters.py:638`; `api/variable_catalog.py:311` trả danh sách tên. **Engine dựng giá trị ở `engine/bom_orchestrator.py:1131-1151`, không đọc bảng này** | GIỮ — nguồn tên để validate |
| `var_label` | Nhãn hiển thị | Data | Nhãn tiếng Việt | Không vào tính toán — `adapters.py:654` | GIỮ — nhãn người đọc |
| `var_type` | Kiểu | Select | Kiểu dữ liệu | Không vào tính toán — `adapters.py:656` | GIỮ — hiển thị gợi ý |
| `group_label` | Nhóm hiển thị | Data | Nhóm trong autocomplete | Không vào tính toán — `adapters.py:660` | GIỮ — gom nhóm |
| `sort_order` | Thứ tự | Int | Thứ tự trong nhóm | Không vào tính toán — `adapters.py:661` | GIỮ — thứ tự gợi ý |
| `is_active` | Đang dùng | Check | Bật/tắt biến | Không vào tính toán — `adapters.py:636`; `api/variable_catalog.py:312` | GIỮ — tắt được biến |
| `description` | Mô tả | Small Text | Giải thích biến | Không vào tính toán — `adapters.py:665` | GIỮ — trợ giúp người đọc |

**Giảm phức tạp:**
- ⚠️ Thêm 1 dòng vào đây **không** làm engine inject biến đó: `lit` được dựng cứng ở `engine/bom_orchestrator.py:1131-1151`. Hệ quả: dòng thừa qua được validate nhưng runtime ra 0 — "biến ma". Phải ghi rõ trong mô tả DocType.
- Gộp với `AL Common Variable` (cùng 7 field) thành 1 bảng + cột "nguồn giá trị".
- Sửa mô tả field `var_name` từ "Tên biến" thành "Tên biến engine inject (phải khớp code)".

---

#### AL Slug Library — doc, 6 field

**Vai trò:** Danh mục vị trí vật tư (slug). Mỗi dòng BOM tham chiếu 1 slug và lấy `category`/`line_name` từ đây.
**Ai dùng:** `AL Bom Item.before_save` (tự điền), API `get_slug_info`, catalog references, nhãn dòng BOM.
**Tổng kết:** 6 field · 2 field vào engine tính toán · 3 field chỉ để cấu hình/hiển thị · 1 field không có tham chiếu · **đề xuất:** giữ 5 / ẩn 1.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `slug` | Slug Code | Data | Mã vị trí, khóa chính | `engine/bom_orchestrator.py:1109-1169` dùng `item["slug"]` làm khóa `row_literals`; `:2058` inject `{slug}__{field}` vào công thức | GIỮ — khóa dòng |
| `label` | Label | Data | Tên vị trí | Không vào tính toán — `al_bom_engine/doctype/al_bom_item/al_bom_item.py:174` điền `line_name`; `api/__init__.py:1534-1538` làm nhãn | GIỮ — nhãn người đọc |
| `category` | Material Category | Link | Nhóm vật tư của slug | `al_bom_item.py:172-173` tự điền `category` cho dòng BOM → quyết định validation + cách tính của engine | GIỮ — engine dùng (gián tiếp) |
| `group_tag` | Group Tag | Data | Nhóm hiển thị khi gợi ý | Không vào tính toán — `api/__init__.py:892-899` gom nhóm references | GIỮ — gom nhóm gợi ý |
| `is_active` | Is Active? | Check | Bật/tắt slug | Không vào tính toán — `api/__init__.py:891` **không lọc** cờ này | ẨN — cờ không có tác dụng |
| `description` | Description | Small Text | Mô tả vị trí | Không vào tính toán — chỉ hiện trên form | GIỮ — trợ giúp người đọc |

**Giảm phức tạp:**
- `is_active` không được lọc ở đâu: hoặc ẩn, hoặc thêm filter ở `api/__init__.py:891`.
- `group_tag` là Data tự do → gõ sai là mất nhóm. Nên đổi sang Select.
- `category` quyết định cách tính của dòng BOM: đổi category của slug sẽ đổi cách tính mọi BOM dùng slug đó — cần cảnh báo trên form.

---

#### AL Variable Cross Row — bảng con, 6 field

**Vai trò:** Bảng con của `AL Variable Profile`. Khai child table nào được gợi ý biến chéo dòng `items.<slug>.<field>`.
**Ai dùng:** chỉ `variable_sources/adapters.py:822-891` (dựng `references` cho autocomplete). Không engine.
**Tổng kết:** 6 field · 0 field vào engine tính toán · 6 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 6.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `table_field` | Child table | Data | Fieldname bảng con được gợi ý | Không vào tính toán — `variable_sources/adapters.py:841,849` lọc và dùng làm tiền tố `items.<table>` | GIỮ — khóa của dòng |
| `id_field` | Field định danh dòng | Data | Field làm `slug` (mặc định `slug`) | Không vào tính toán — `adapters.py:855`, rỗng thì tự dò (`:791`) | GIỮ — quyết định tên gợi ý |
| `label_field` | Field nhãn dòng | Data | Field làm nhãn dòng | Không vào tính toán — `adapters.py:857`, rỗng thì dò `line_name`/`item_code` (`:768-779`) | GIỮ — nhãn gợi ý |
| `include_index_form` | Sinh thêm dạng items[n] | Check | Sinh thêm dạng `items[0].field` | Không vào tính toán — `adapters.py:858` và `:810-819` | GIỮ — dạng gợi ý |
| `enabled` | Đang dùng | Check | Bật/tắt dòng | Không vào tính toán — `adapters.py:839` | GIỮ — tắt được bảng |
| `fields` | Danh sách field | Small Text | JSON list field được gợi ý | Không vào tính toán — `adapters.py:856`; rỗng thì lấy mọi field vô hướng (`:792`) | GIỮ — giới hạn gợi ý |

**Giảm phức tạp:**
- `fields` rỗng = **mọi** field vô hướng của bảng con → nở hàng trăm gợi ý. Khuyến nghị khai tường minh.
- `id_field` mặc định `"slug"` — bảng con không có `slug` sẽ gợi ý sai tên nhưng không báo.

---

#### AL Variable Dimension Mapping — doc, 5 field

**Vai trò:** Nối "tên biến" ↔ "chiều giá" (kèm hệ số). Đây là nơi duy nhất nói biến nào là khóa tra giá.
**Ai dùng:** engine `_get_dim_fieldnames`/`_get_dim_mappings_raw`, FB handler `aluminum_price_composite` cả 2 mode, dialog (cờ `is_pricing_dimension`).
**Tổng kết:** 5 field · 5 field vào engine tính toán · 0 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 5, thêm ràng buộc duy nhất.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `variable_name` | Variable Name | Data | Tên biến tra giá | `engine/bom_orchestrator.py:1204,1238-1240` nối sang `custom_fieldname`; `fb_handlers.py:151,225` | GIỮ — engine dùng |
| `pricing_dimension` | Pricing Dimension | Link | Chiều giá tương ứng | `engine/bom_orchestrator.py:1200,1229-1236`; `fb_handlers.py:126-130` | GIỮ — engine dùng |
| `material_category` | Material Category | Link | Chỉ áp cho nhóm vật tư này | `engine/bom_orchestrator.py:1318` lọc mapping theo category của dòng; `fb_handlers.py:116-117` lọc trước khi tra | GIỮ — engine dùng |
| `price_multiplier` | Price Multiplier | Float | Hệ số nhân cho chiều này | `fb_handlers.py:234` cộng vào `total_multiplier`; `:256-257` nhân dồn | GIỮ — engine dùng |
| `is_active` | Is Active? | Check | Bật/tắt mapping | `engine/bom_orchestrator.py:1227,1277`; `fb_handlers.py:115` lọc `is_active: 1` | GIỮ — engine dùng |

**Giảm phức tạp:**
- Không có ràng buộc duy nhất `(variable_name, pricing_dimension)`: 2 dòng trùng sẽ khiến `multiplier_chain` nhân hệ số **2 lần** (`fb_handlers.py:224-257`). Nên thêm validate trùng.
- `price_multiplier` mặc định `1.0`: dòng khai 1.0 thật khác "không khai" — code đã xử lý đúng (`fb_handlers.py:253-256`), nhưng người nhập dễ hiểu nhầm là vô nghĩa.

---

#### AL Variable Library — doc, 12 field

**Vai trò:** Thư viện biến trung tâm. 1 record = 1 biến, khai **nguồn giá trị** (`source_doctype`/`source_field`) hoặc giá trị mặc định. Thêm biến = thêm record, không sửa code.
**Ai dùng:** engine B1 (system vars, default user var, chuẩn hoá %), dialog tham số BOM, catalog gợi ý.
**Tổng kết:** 12 field · 8 field vào engine tính toán · 4 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 12.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `var_name` | Variable Name | Data | Tên biến, khóa chính | `engine/bom_orchestrator.py:541-546` (đọc mọi biến), `:600` (user var), `system_variable_resolver.py:180`; chính là key trong `self.inputs` | GIỮ — khóa biến |
| `var_label` | Label | Data | Nhãn tiếng Việt | `engine/bom_orchestrator.py:546` dùng trong cảnh báo biến %; `api/__init__.py:1194` cho dialog | GIỮ — engine dùng (cảnh báo) |
| `var_type` | Type | Select | Kiểu biến | `engine/bom_orchestrator.py:544` — `var_type == "Percent"` buộc chuẩn hoá chia 100; `variable_sources/adapters.py:355` | GIỮ — engine dùng |
| `category` | Category | Data | Nhóm biến | Không vào số tiền — `variable_sources/adapters.py:367` gắn vào candidate; rule `category_tag` khớp theo `variable_sources/rules.py:153-158` | GIỮ — lọc gợi ý |
| `is_system` | System Variable? | Check | Biến hệ thống hay user | `engine/bom_orchestrator.py:588-592` (user var), `:651` + `system_variable_resolver.py:54` (system var) | GIỮ — engine dùng |
| `link_doctype` | Link Doctype | Link | Doctype của biến kiểu Link | Không vào số tiền — `api/__init__.py:1191,1196` dựng ô Link trong dialog | GIỮ — dựng form nhập |
| `select_options` | Select Options | Small Text | Danh sách chọn của biến Select | Không vào số tiền — `api/__init__.py:1191,1197`; `al_variable_set_item.py:14` chép sang Set Item | GIỮ — dựng form nhập |
| `source_doctype` | Source Doctype | Link | Doctype nguồn của biến hệ thống | `al_bom_engine/system_variable_resolver.py:108-160` dò field Link trên chứng từ; `:180` | GIỮ — engine dùng |
| `source_field` | Source Field | Data | Field nguồn | `system_variable_resolver.py:187` — `frappe.db.get_value(sdt, record_name, sf)`, giá trị vào `self.inputs` | GIỮ — engine dùng |
| `source_link_field` | Source Link Field | Data | Field Link dùng để tìm bản ghi nguồn (khi có nhiều Link cùng đích) | `system_variable_resolver.py:113-147` — khai tường minh thắng auto-discover; khai sai thì cảnh báo + rơi về auto | GIỮ — engine dùng |
| `default_value` | Default Value | Data | Giá trị mặc định | `engine/bom_orchestrator.py:603-609` (user var), `:720-725` (system var khi không resolve được) | GIỮ — engine dùng |
| `description` | Description | Small Text | Giải thích biến | Không vào số tiền — `variable_sources/adapters.py:365`; `api/__init__.py:1190` | GIỮ — trợ giúp người đọc |

**Giảm phức tạp:**
- Controller chỉ chặn "có `source_doctype` mà thiếu `source_field`" (`al_variable_library.py:8-13`). Nên chặn thêm chiều ngược và kiểm `source_link_field` đúng là field Link — hiện chỉ cảnh báo ở log (`system_variable_resolver.py:133-138`).
- `var_type` sai = chuẩn hoá % sai (biến 8 thành 0.08 hay 8 tuỳ kiểu): nên cảnh báo trên form khi tên kết thúc bằng `_PCT` mà kiểu không phải Percent.
- `default_value` là Data: nhập chữ cho biến số sẽ lọt xuống engine rồi ra 0 (`bom_orchestrator.py:606-609` thử `float()` rồi giữ nguyên chuỗi).

---

#### AL Variable Profile — doc, 7 field

**Vai trò:** Chọn bộ biến **người dùng thấy khi gõ công thức**. Chỉ là lớp gợi ý/lọc.
**Ai dùng:** `api/variable_catalog.py` (resolve profile, dựng catalog, preview), JS nút "Xem trước danh sách biến". **Không tham gia tính giá** — validate công thức cố ý bỏ qua profile (`al_bom_engine/formula_validate.py:66-70`).
**Tổng kết:** 7 field · 0 field vào engine tính toán · 7 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 7.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `profile_code` | Mã profile | Data | Mã profile, khóa chính | Không vào tính toán — `api/variable_catalog.py:74-76` tra profile theo mã; `al_variable_profile.js:45` | GIỮ — khóa chính |
| `profile_name` | Tên profile | Data | Tên hiển thị | Không vào tính toán — `api/variable_catalog.py:130` trả cho client | GIỮ — nhãn người đọc |
| `is_active` | Đang dùng | Check | Bật/tắt profile | Không vào tính toán — `api/variable_catalog.py:79-81`: profile tắt thì coi như không có | GIỮ — tắt được profile |
| `default_action` | Chế độ mặc định | Select | `INCLUDE_ALL` (mặc định hiện mọi biến) hoặc `EXCLUDE_ALL` | Không vào số tiền — `variable_sources/rules.py:269-271` và `:308-309` quyết định biến nào bị loại | GIỮ — quyết định bộ gợi ý |
| `description` | Mô tả | Small Text | Giải thích profile | Không vào tính toán — chỉ hiện trên form | GIỮ — trợ giúp người đọc |
| `rules` | Rules | Table | Danh sách luật lọc | Không vào số tiền — `api/variable_catalog.py:132-133` đọc rules; áp ở `variable_sources/rules.py:286-336` | GIỮ — ruột của profile |
| `cross_row` | Cross Row | Table | Gợi ý biến chéo dòng | Không vào số tiền — `variable_sources/adapters.py:838-859` | GIỮ — gợi ý chéo dòng |

**Giảm phức tạp:**
- `EXCLUDE_ALL` là allowlist: quên khai rule Include là **mất sạch biến** gợi ý. Nút "Xem trước" đã báo `excluded_by_rules` — nên ghi rõ trong mô tả field.
- Ghi rõ trong mô tả DocType: "Profile không đổi số tiền" — đây là hiểu nhầm phổ biến nhất.

---

#### AL Variable Profile Rule — bảng con, 13 field

**Vai trò:** Bảng con của `AL Variable Profile` — mỗi dòng là 1 luật Include/Exclude một nguồn biến.
**Ai dùng:** chỉ `variable_sources/rules.py:110-180` (`_matches`). Không engine.
**Tổng kết:** 13 field · 0 field vào engine tính toán · 13 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 13.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `action` | Hành động | Select | Include hoặc Exclude | Không vào số tiền — `variable_sources/rules.py:114-115,287-288`: Exclude thắng Include | GIỮ — luật chính |
| `source_kind` | Nguồn biến | Select | 11 nguồn biến (variable_library_system, variable_set, row_literal…) | Không vào số tiền — `rules.py:126-129`: rỗng = mọi nguồn; `rules.py:248-271` chọn adapter cần chạy | GIỮ — chọn nguồn |
| `source_ref` | Tham chiếu nguồn | Data | Mã bản ghi nguồn, `*`/`AUTO` = mọi bản ghi | Không vào số tiền — `rules.py:131-136`; `adapters.py:452-466` dùng cho Variable Set | GIỮ — thu hẹp nguồn |
| `group_label` | Nhóm hiển thị | Data | Đổi tên nhóm khi hiện | Không vào số tiền — `rules.py:318-320` ghi đè `group` của candidate | GIỮ — nhóm hiển thị |
| `sort_order` | Thứ tự nhóm | Int | Thứ tự ưu tiên | Không vào số tiền — `rules.py:188-191,321-322` | GIỮ — thứ tự |
| `is_active` | Đang dùng | Check | Bật/tắt luật | Không vào số tiền — `rules.py:110-111,120-121` | GIỮ — tắt được luật |
| `name_prefix` | Tiền tố tên | Data | Chỉ khớp biến có tiền tố (danh sách ngăn bằng dấu gạch đứng) | Không vào số tiền — `rules.py:139-141`; phân biệt hoa thường | GIỮ — lọc theo tên |
| `name_regex` | Regex tên biến | Data | Chỉ khớp biến theo regex | Không vào số tiền — `rules.py:144-150`; regex hỏng = không khớp (không ném lỗi) | GIỮ — lọc theo tên |
| `category_tag` | Category | Data | Lọc theo category/nhóm (danh sách ngăn bằng dấu gạch đứng) | Không vào số tiền — `rules.py:153-158` | GIỮ — lọc theo category |
| `var_type` | Kiểu biến | Select | Lọc theo kiểu | Không vào số tiền — `rules.py:161-163` | GIỮ — lọc theo kiểu |
| `source_type` | Source Type (FVB) | Data | Lọc theo `source_type` của nguồn | Không vào số tiền — `rules.py:165-167` | GIỮ — lọc theo nguồn con |
| `only_fields` | Chỉ hiện ở field | Small Text | JSON list field được hiện | Không vào số tiền — `rules.py:171-173,229-245`; phải là JSON list, controller chặn sai định dạng (`al_variable_profile.py:20-33`) | GIỮ — lọc theo field |
| `require_value` | Bắt buộc có giá trị | Check | Chỉ hiện khi biến có giá trị | Không vào số tiền — `rules.py:176-178,339-346` | GIỮ — ẩn biến rỗng |

**Giảm phức tạp:**
- `source_kind` để trống = **mọi nguồn** (`rules.py:126-129`), không phải "không khớp" — ghi rõ trong mô tả.
- `only_fields` sai định dạng bị chặn khi save profile (tốt), nhưng `parse_json_list` khi đọc lại **nuốt lỗi** (`rules.py:85-90`) — dữ liệu cũ hỏng sẽ âm thầm thành "không giới hạn".
- `source_type` dễ lẫn với khái niệm `source_type` của Formula Variable Binding — nên đổi nhãn thành "Lọc theo Source Type (FVB)".

---

#### AL Variable Set — doc, 5 field

**Vai trò:** Bộ biến người dùng nhập cho một loại sản phẩm. Bom Set trỏ tới Variable Set; dialog Tham số BOM dựng form từ đây.
**Ai dùng:** `api/__init__.py:1155-1184` (`get_variable_set_for_bom`), catalog adapter (`variable_sources/adapters.py:469-523`). **Engine không đọc Variable Set** — engine nhận giá trị từ `al_bom_vars` do dialog lưu.
**Tổng kết:** 5 field · 0 field vào engine tính toán · 5 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 5, thống nhất 1 đường chọn set.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `set_code` | Set Code | Data | Mã bộ, khóa chính | Không vào tính toán — `api/__init__.py:1156` hiển thị; `adapters.py:485` làm `source_ref` + tên nhóm | GIỮ — khóa chính |
| `set_name` | Set Name | Data | Tên bộ | Không vào tính toán — `api/__init__.py:1157,1076`; `adapters.py:486` | GIỮ — nhãn người đọc |
| `product_type` | Product Type | Link | Loại sản phẩm áp dụng | Không vào số tiền — dùng để **tự tìm bộ** khi chứng từ có `product_type` mà không có field Link trực tiếp: `api/__init__.py:1035-1047` và `variable_sources/adapters.py:424-447` (cùng quy tắc `modified desc`). Dialog Tham số BOM đi theo `AL Bom Set.variable_set` (`api/__init__.py:1154-1155`), không dùng field này | GIỮ — đường chọn set tự động |
| `is_active` | Is Active? | Check | Bật/tắt bộ | Không vào số tiền — lọc ở đường tự tìm (`api/__init__.py:1041`, `adapters.py:439`), nhưng **không kiểm** khi Bom Set Link trực tiếp (`api/__init__.py:1154-1155`) | GIỮ — cần thống nhất |
| `items` | Variables | Table | Danh sách biến của bộ | Không vào số tiền — `api/__init__.py:1158`; `adapters.py:487` duyệt từng dòng | GIỮ — ruột của bộ |

**Giảm phức tạp:**
- Có 2 đường chọn set: field Link trực tiếp trên chứng từ/Bom Set (dialog) và suy theo `product_type` (`api/__init__.py:1026-1047`; `adapters.py:424-447`). Hai đường có thể ra 2 bộ khác nhau — nên chốt 1.
- `is_active` chỉ được kiểm ở đường suy theo `product_type`: set bị tắt vẫn hiện nếu được Link trực tiếp. Nên kiểm ở `api/__init__.py:1155`.

---

#### AL Variable Set Item — bảng con, 8 field

**Vai trò:** Bảng con của `AL Variable Set` — 1 dòng = 1 biến trong bộ, có thể ghi đè nhãn/kiểu/giá trị mặc định.
**Ai dùng:** `api/__init__.py:1158-1184` (dựng form nhập), catalog adapter (`variable_sources/adapters.py:487-522`).
**Tổng kết:** 8 field · 0 field vào engine tính toán · 8 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 4 / gộp 4 field bản sao.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `variable` | Variable | Link | Biến lấy từ thư viện | Không vào số tiền — `api/__init__.py:1161-1163`; `adapters.py:488` | GIỮ — khóa của dòng |
| `var_label` | Label | Data (ro) | Nhãn — tự điền từ Library | Không vào số tiền — `al_variable_set_item.py:11` điền; `api/__init__.py:1168` dùng khi Library thiếu | GỘP — vào `variable`, Library là nguồn |
| `var_type` | Type | Data (ro) | Kiểu — tự điền | Không vào số tiền — `al_variable_set_item.py:12`; `api/__init__.py:1169`; `adapters.py:508-509` | GỘP — vào `variable`, Library là nguồn |
| `link_doctype` | Link Doctype | Data (ro) | Doctype của biến Link — tự điền | Không vào số tiền — `al_variable_set_item.py:13`; `api/__init__.py:1170` | GỘP — vào `variable`, Library là nguồn |
| `select_options` | Select Options | Small Text (ro) | Danh sách chọn — tự điền | Không vào số tiền — `al_variable_set_item.py:14`; `api/__init__.py:1171` | GỘP — vào `variable`, Library là nguồn |
| `default_value` | Default Value (override) | Data | Giá trị mặc định riêng của bộ | Không vào số tiền — `api/__init__.py:1172` ưu tiên giá trị này hơn Library. **Adapter catalog lại bỏ qua** (`adapters.py:504` chỉ lấy từ `ctx.resolved`) | GIỮ — nhưng phải thống nhất |
| `sort_order` | Sort Order | Int | Thứ tự biến trong form | Không vào số tiền — `api/__init__.py:1182`; `adapters.py:515` | GIỮ — thứ tự hiển thị |
| `is_required` | Required? | Check | Bắt buộc nhập | Không vào số tiền — `api/__init__.py:1181` trả cho dialog | GIỮ — cổng kiểm form nhập |

**Giảm phức tạp:**
- 4 field read-only là **bản sao** của `AL Variable Library` (`al_variable_set_item.py:9-14`). Chỉ giữ nếu cần chạy khi Library bị xoá; còn lại gộp về `variable`.
- `default_value` có 2 nơi khai (Library + đây) và 2 consumer xử lý khác nhau (`api/__init__.py:1172` dùng, `adapters.py:504` bỏ qua) — chốt 1 quy tắc.

---

#### AL Variable Settings — Single, 4 field

**Vai trò:** Cấu hình chung cho Variable Catalog: profile mặc định, 2 bảng biến dùng chung, doctype xem trước.
**Ai dùng:** `api/variable_catalog.py` (profile mặc định), `variable_sources/adapters.py` (2 bảng con), `api/__init__.py:817-848` (đường cũ), JS preview.
**Tổng kết:** 4 field · 0 field vào engine tính toán · 4 field chỉ để cấu hình/hiển thị · 0 field không có tham chiếu · **đề xuất:** giữ 4.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `default_profile` | Profile mặc định | Link | Profile dùng khi doctype có field Link tới profile nhưng để trống | Không vào số tiền — `api/variable_catalog.py:113-117` chỉ đọc khi doctype **đã khai** field Link tới profile (`:99-101`) | GIỮ — cấu hình catalog |
| `preview_doctype` | Doctype xem trước | Link | Doctype mặc định của hộp xem trước | Không vào tính toán — chỉ JS đọc (`al_variable_profile.js:62`) | GIỮ — nhưng không thuộc "biến" |
| `common_variables` | Common Variables | Table | Bảng biến người dùng nhập | Không vào số tiền — `variable_sources/adapters.py:674`; `api/__init__.py:838` | GIỮ — nguồn khai biến |
| `row_literals` | Row Literals | Table | Bảng biến engine inject theo dòng | Không vào số tiền — `adapters.py:630`; `api/__init__.py:822`; `api/variable_catalog.py:304-314` (dùng cho validate) | GIỮ — nguồn tên để validate |

**Giảm phức tạp:**
- `preview_doctype` là field duy nhất không liên quan "biến": có thể chuyển sang `AL Variable Profile` hoặc bỏ, để Single này chỉ còn 3 field.
- `default_profile` chỉ áp cho doctype đã khai field Link (đúng thiết kế, `api/variable_catalog.py:87-93`) — nên ghi rõ trong mô tả, tránh tưởng là "bật cho mọi form".

---

##### Tổng hợp nhóm

| DocType | Số field | Vào engine | Chỉ cấu hình/hiển thị | 0 tham chiếu | Đề xuất |
|---|---|---|---|---|---|
| AL Color Standard | 9 | 2 | 2 | 5 | Giữ 4 · Ẩn 3 · Bỏ 1 · Chờ dữ liệu 1 |
| AL Common Variable | 7 | 0 | 7 | 0 | Giữ 7; cân nhắc gộp với Row Literal |
| AL Formula Field | 7 | 0 | 7 | 0 | Giữ 7 |
| AL Glass Master | 10 | 4 | 1 | 5 | Giữ 5 · Ẩn 4 · Bỏ 1 |
| AL Glass Type | 2 | 1 | 1 | 0 | Giữ 2; đặt `title_field` |
| AL Material Category | 12 | 4 | 7 | 1 | Giữ 11 · Ẩn 1 |
| AL Pricing Dimension | 10 | 5 | 3 | 2 | Giữ 8 · Ẩn 1 · Chờ dữ liệu 1 |
| AL Product Type | 6 | 3 | 2 | 1 | Giữ 5 · Ẩn 1 |
| AL Profile System | 9 | 5 | 3 | 1 | Giữ 8 · Ẩn 1; chốt 1 nguồn offset |
| AL Profile System Variable | 3 | 3 | 0 | 0 | Giữ 3; thêm validate số |
| AL Row Literal | 7 | 0 | 7 | 0 | Giữ 7; sửa mô tả, cân nhắc gộp |
| AL Slug Library | 6 | 2 | 3 | 1 | Giữ 5 · Ẩn 1 |
| AL Variable Cross Row | 6 | 0 | 6 | 0 | Giữ 6 |
| AL Variable Dimension Mapping | 5 | 5 | 0 | 0 | Giữ 5; thêm ràng buộc duy nhất |
| AL Variable Library | 12 | 8 | 4 | 0 | Giữ 12; thêm kiểm nguồn |
| AL Variable Profile | 7 | 0 | 7 | 0 | Giữ 7 |
| AL Variable Profile Rule | 13 | 0 | 13 | 0 | Giữ 13 |
| AL Variable Set | 5 | 0 | 5 | 0 | Giữ 5; thống nhất 1 đường chọn |
| AL Variable Set Item | 8 | 0 | 8 | 0 | Giữ 4 · Gộp 4 field bản sao |
| AL Variable Settings | 4 | 0 | 4 | 0 | Giữ 4 (cân nhắc bỏ `preview_doctype`) |
| **Tổng** | **148** | **42** | **90** | **16** | |

**Ba việc nên làm trước trong nhóm này:**

1. **Ghi rõ "profile không đổi số tiền" ngay trên 3 DocType** (`AL Variable Profile`, `AL Variable Profile Rule`, `AL Variable Cross Row`). Bằng chứng: `al_bom_engine/formula_validate.py:66-70` cố ý bỏ qua profile khi validate; catalog tự ghi chú "lớp GỢI Ý / LỌC, KHÔNG phải nguồn giá trị" (`api/variable_catalog.py:7-9`). Đây là hiểu nhầm tốn tiền nhất của nhóm.
2. **Sửa mô tả `AL Row Literal` + `AL Variable Set Item`** để nói đúng sự thật: thêm dòng Row Literal **không** làm engine inject biến (engine dựng `lit` cứng ở `engine/bom_orchestrator.py:1131-1151`; patch cũng ghi "chỉ đăng ký TÊN" ở `patches/v28_14/seed_bom_profile.py:30`); và `default_value` của Set Item bị 2 consumer xử lý khác nhau (`api/__init__.py:1172` dùng, `variable_sources/adapters.py:504` bỏ qua).
3. **Rà 16 field 0 tham chiếu**, trước hết nhóm đã rõ kết luận: bỏ `AL Color Standard.is_default` (→ `is_representative`), bỏ `AL Glass Master.item_code` (→ engine tra theo `glass_code`), ẩn `AL Color Standard.applies_to` (hit thật thuộc `AL Cutting Standard`) và 3 cờ `is_active` vô tác dụng (`AL Material Category`, `AL Profile System`, `AL Slug Library`).

**Ba thứ KHÔNG nên đụng:**

1. **`AL Variable Dimension Mapping` + `AL Pricing Dimension.custom_fieldname`/`link_doctype`/`represents_color`** — đây là xương sống tra giá composite (`fb_handlers.py:119-130,239-243`; `engine/bom_orchestrator.py:1200-1204,1944-1949`). Đổi tên/kiểu sẽ làm giá báo sai âm thầm.
2. **`AL Variable Library.source_doctype`/`source_field`/`source_link_field`/`is_system`** — nguồn duy nhất của mọi system variable (`al_bom_engine/system_variable_resolver.py:62-160`). Đổi tên field đích (vd `nc_pct`) sẽ làm biến mất nguồn mà không báo.
3. **`AL Glass Master.total_thick_mm`/`glass_type`/`max_area_m2` và `AL Material Category.default_scrap_pct`/`has_weight`/`requires_glass_master`** — engine B2 và validate đang đọc trực tiếp (`engine/bom_orchestrator.py:967-994,2251-2320`). `default_scrap_pct` còn là thay đổi số liệu thật (chỉ áp khi Bom Set bật `apply_scrap_pct`).

---

### 8.2 AL Bom Engine — 12 DocType (lõi tính giá)

> Nguồn đối chiếu: mã app `alumglass` tại `/home/nxc/myfrappe/apps/alumglass`, engine
> `alumglass/engine/bom_orchestrator.py` (2 783 dòng). Mọi kết luận "engine đọc/không đọc"
> đều mở đúng dòng ghi kèm. Cột "Đánh giá" chỉ dùng 5 nhãn: GIỮ · GỘP · ẨN · BỎ · CHỜ-DỮ-LIỆU.

**Bảy bước của engine** (dùng lại trong toàn tài liệu):

| Bước | Việc làm | Dòng |
|---|---|---|
| B0 | Ghim phiên bản BOM (chọn `AL BOM Version`) | 315–367 |
| B1 | Gom biến đầu vào (global var, FVB, Variable Library, user nhập) | 372–519 |
| B2 | Nạp trước dữ liệu chủ (Item, Item Price, kính, nhóm vật tư, rule) | 893–1180 |
| B3 | Dựng danh sách công thức cho Formula Builder | 2003–2162 |
| B4 | Tính từng dòng vật tư qua FormulaEngine | 2217–2314 |
| B5 | Gom `line_total` theo cost bucket | 2351–2375 |
| B6 | Tính Cost Template (giá thành → giá bán) | 2468–2589 |
| B7 | Ghi kết quả vào Quotation Item (1 commit) | 2624–2675 |

---

#### AL Accessory Item — bảng con, 11 field

**Vai trò:** Một dòng phụ kiện (tay nắm, khoá, bản lề…) trong bộ phụ kiện. Do người cấu hình
nhập trên form `AL Accessory Set`.
**Ai dùng:** Engine B2 — `_load_accessories()` biến mỗi dòng thành một dòng BOM giả
(`alumglass/engine/bom_orchestrator.py:856-888`), sau đó B3/B4/B5 xử lý y như dòng vật tư thường.
**Tổng kết:** 11 field · 8 field vào engine · 3 field chỉ hiển thị · 0 field không tham chiếu ·
**đề xuất:** giữ nguyên.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `slug` | Slug | Data | Khoá dòng, engine dùng làm tiền tố biến `{slug}__…` | `bom_orchestrator.py:857` — bỏ qua dòng không có slug; `:1109` khoá `row_literals`; `:2059` khoá công thức | GIỮ — khoá xuyên suốt B2–B6 |
| `item_code` | Item Code | Link Item | Mã hàng để tra giá/khối lượng | `bom_orchestrator.py:863` nạp vào dòng; `:916-917` gom batch; `:1133-1134` tra `prices` | GIỮ |
| `qty` | Qty (fixed) | Float | Số lượng cố định khi không khai công thức | `bom_orchestrator.py:865` — chỉ dùng khi `qty_formula` rỗng (mặc định 1) | GIỮ — nhưng là phương án dự phòng |
| `qty_formula` | Qty Formula | Small Text | Công thức số lượng (FB) | `bom_orchestrator.py:860,865` — có công thức thì thay hẳn `qty`; B3 dựng `{slug}__qty` | GIỮ |
| `calc_pattern` | Calc Pattern | Link AL Quantity Calc Method | Cách quy đổi kích thước → số đơn vị | `bom_orchestrator.py:870` (mặc định `COUNT`); B3 `:2127` truyền vào `lookup_calc_pattern` | GIỮ |
| `cost_bucket` | Cost Bucket | Link AL Cost Bucket | Ngăn chi phí nhận tiền dòng này | `bom_orchestrator.py:871` (mặc định `VL_PK`); B4 `:2299`; B5 `:2366-2374` | GIỮ |
| `unit_price` | Unit Price | Currency | Đơn giá ghi đè trực tiếp, không cần Item Price | `bom_orchestrator.py:866` và `:1166-1167` — khác 0 là đè giá đã tra | GIỮ |
| `default_color` | Default Color | Link AL Color Standard | Màu đại diện để chọn màu theo vị trí | `bom_orchestrator.py:882`; `:1128-1129`; `:1423-1453` đổi biến màu khi tra giá composite | GIỮ |
| `supplier_location` | Noi cap vat tu | Data | Nơi cấp vật tư, in trên báo giá | `bom_orchestrator.py:884` → `:2310` → `quotation.js:132` | GIỮ |
| `install_position` | Vi tri lap dat | Data | Vị trí lắp đặt, in trên báo giá | `bom_orchestrator.py:885` → `:2311` → `quotation.js:133` | GIỮ |
| `note` | Ghi chu | Small Text | Ghi chú dòng, in trên báo giá | `bom_orchestrator.py:887` → `:2313` → `quotation.js:82` | GIỮ |

**Giảm phức tạp:**
- `qty` và `qty_formula` là hai đường cho cùng một con số; nên ghi rõ trên nhãn "dùng khi không có công thức".
- Không có field chết — giữ nguyên schema.

---

#### AL Accessory Set — doc, 8 field

**Vai trò:** Bộ phụ kiện dùng chung cho nhiều BOM. Người cấu hình tạo; BOM trỏ tới qua
`AL Bom Set.default_accessory_set` hoặc biến `accessory_set` trong `al_bom_vars`.
**Ai dùng:** Engine B2 (`_load_accessories`, `bom_orchestrator.py:835-888`); API hiển thị tên bộ
(`api/__init__.py:1140-1144`); danh mục biến (autocomplete) đọc `variable_set`.
**Tổng kết:** 8 field · 2 field vào engine · 3 field cấu hình/hiển thị · 3 field không tham chiếu ·
**đề xuất:** giữ 5, ẩn 2, 1 chờ dữ liệu.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `set_code` | Set Code | Data | Mã bộ = tên bản ghi (`autoname='field:set_code'`) | `bom_orchestrator.py:844-850` — engine tra bộ theo đúng mã này | GIỮ — là định danh engine dùng |
| `set_name` | Set Name | Data | Tên bộ cho người đọc | `api/__init__.py:1144` trả về dialog | GIỮ |
| `item_code` | Mã sản phẩm | Link Item | Ý định gắn bộ với một mã sản phẩm | Không có tham chiếu — engine chỉ đọc bảng `items`, không đọc mã ở đầu phiếu | ẨN — chưa có consumer, chưa xoá |
| `product_type` | Product Type | Link AL Product Type | Phân loại sản phẩm của bộ | Không engine nào đọc; nhánh suy Variable Set theo `product_type` (`api/__init__.py:1035-1047`) không chạy vì bộ đã có `variable_set` trực tiếp | ẨN |
| `variable_set` | Variable Set | Link AL Variable Set | Bộ biến người dùng nhập khi lập báo giá | `api/__init__.py:1024` (khi đi qua BOM), `:1056`; `variable_sources/adapters.py:394` | GIỮ — phục vụ autocomplete/dialog, không vào phép tính |
| `is_active` | Is Active? | Check | Cờ tắt bộ | Không có tham chiếu — `_load_accessories` không kiểm `is_active` | CHỜ-DỮ-LIỆU — đếm số bộ đang tắt trước khi bỏ |
| `variable_profile` | Variable Profile | Link AL Variable Profile | Hồ sơ gợi ý biến khi gõ công thức | `api/variable_catalog.py:63-79` dò field Link tới `AL Variable Profile` | GIỮ — chỉ ảnh hưởng gợi ý, không ảnh hưởng giá |
| `items` | Items | Table AL Accessory Item | Danh sách phụ kiện | `bom_orchestrator.py:856` — vòng lặp chính của B2 | GIỮ |

**Giảm phức tạp:**
- Ẩn `item_code` và `product_type` khỏi form (không đổi schema, không mất dữ liệu cũ).
- Nếu muốn `is_active` có tác dụng thật: thêm một dòng `if not acc_doc.is_active: return` ở
  `bom_orchestrator.py:850` — hiện cờ này không tắt được gì.

---

#### AL BOM — doc, 13 field

**Vai trò:** Đầu mối sản phẩm: nối Bom Set + Cost Template + phiên bản hiện hành. Người cấu hình
tạo một lần cho mỗi sản phẩm.
**Ai dùng:** Engine B0 đọc `current_version`, B1/B2 đọc `bom_set`; phần còn lại phục vụ dialog báo
giá và nút tạo phiên bản.
**Tổng kết:** 13 field · 4 field vào engine · 3 field cấu hình/hiển thị · 6 field không tham chiếu ·
**đề xuất:** giữ 7, bỏ 2, ẩn 3, 1 chờ dữ liệu.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `bom_code` | BOM Code | Data | Mã BOM = tên bản ghi | `bom_orchestrator.py:317` lấy từ Quotation Item; `:325` nạp BOM | GIỮ |
| `bom_name` | BOM Name | Data | Tên sản phẩm cho người đọc | `api/__init__.py:1106,1369` trả về dialog | GIỮ |
| `product_type` | Product Type | Link AL Product Type | Phân loại sản phẩm | Không ai đọc — biến hệ thống `NC_*` lấy `product_type` của **AL Bom Set**, không phải của BOM | ẨN — gây hiểu nhầm là có tác dụng |
| `brand` | Brand | Link Brand | Hãng nhôm | Không ai đọc — `api/__init__.py:1136` đọc `brand` của **AL Bom Set** | ẨN |
| `representative_item` | Mã sản phẩm | Link Item | Ảnh/mã sản phẩm ở đầu dialog báo giá | `api/__init__.py:1381,1397-1419` (chỉ hiển thị) | GIỮ |
| `is_active` | Is Active? | Check | Cờ tắt BOM | Không có tham chiếu | CHỜ-DỮ-LIỆU |
| `bom_set` | BOM Set | Link AL Bom Set | Trỏ tới cấu trúc vật tư | `bom_orchestrator.py:828-830` — B1/B2 nạp Bom Set từ đây | GIỮ |
| `pk_set` | Accessory Set (Optional) | Link AL Accessory Set | Ý định bộ phụ kiện riêng cho BOM | Không có tham chiếu; engine lấy `AL Bom Set.default_accessory_set` (`:846`) hoặc `al_bom_vars.accessory_set` (`:468`) | BỎ — thay bằng 1 trong 2 đường đang chạy |
| `default_cost_template` | Default Cost Template | Link AL Cost Template | Mẫu công thức giá thành | `al_bom_version.py:141-143` chụp vào `cost_template_snapshot`; B6 đọc snapshot (`bom_orchestrator.py:2489`) | GIỮ — nguồn duy nhất của giá bán |
| `current_version` | Current Version | Link AL BOM Version | Phiên bản đang dùng | `bom_orchestrator.py:326-329` (B0); `al_bom_version.py:42` ghi khi Published | GIỮ |
| `create_new_version_btn` | Tạo BOM Version mới | Button | Nút gọi `create_bom_version` | `al_bom.py:102-115`; `al_bom.js:16` | GIỮ |
| `requires_approval_for_new_version` | Requires Approval for New Version? | Check | Ý định bắt duyệt phiên bản mới | Không có tham chiếu — việc duyệt do Workflow đảm nhiệm (`setup/install_workflows.py`) | BỎ — thay bằng Workflow |
| `default_installation_team` | Default Installation Team | Link AL Installation Team | Đội lắp đặt mặc định | Không có tham chiếu; field này dùng ở `AL Installation Order`, không ở BOM | ẨN |

**Giảm phức tạp:**
- `pk_set` là bẫy nặng nhất: người dùng chọn bộ phụ kiện mà giá không đổi. Bỏ field hoặc nối nó
  vào `_load_accessories`.
- `product_type`/`brand` trên BOM trùng tên với field cùng tên trên Bom Set nhưng engine chỉ đọc
  bản của Bom Set — nên ẩn để tránh sửa nhầm chỗ.

---

#### AL BOM Change Log — bảng con, 7 field

**Vai trò:** Ý định ghi vết thay đổi của một phiên bản BOM. Là bảng con của
`AL BOM Version.items` (nhãn "Change Log Items").
**Ai dùng:** **Không có consumer.** Không dòng mã nào ghi vào bảng này; engine cũng không đọc
`AL BOM Version.items`. Đây là bảng chỉ có trên form, chưa từng chạy.
**Tổng kết:** 7 field · 0 field vào engine · 0 field có consumer · 7 field không tham chiếu ·
**đề xuất:** ẩn cả bảng, đếm dữ liệu rồi bỏ.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `change_type` | Change Type | Select Added/Modified/Removed | Loại thay đổi | Không vào tính toán; hit duy nhất `al_construction/doctype/al_change_order/al_change_order.py:20` là **trùng tên** (doctype khác) | CHỜ-DỮ-LIỆU |
| `field_name` | Field Name | Data | Tên field bị đổi | Không vào tính toán; hit `api/__init__.py:951-953` là **biến vòng lặp** `for field_name in new_only` — trùng tên, chưa chắc | BỎ — không có writer/reader |
| `old_value` | Old Value | Small Text | Giá trị cũ | Không có tham chiếu | CHỜ-DỮ-LIỆU |
| `new_value` | New Value | Small Text | Giá trị mới | Không có tham chiếu | CHỜ-DỮ-LIỆU |
| `changed_by` | Changed By | Link User | Người đổi | Không có tham chiếu (Frappe đã có `owner`/`modified_by`) | CHỜ-DỮ-LIỆU |
| `changed_on` | Changed On | Datetime | Thời điểm đổi | Không có tham chiếu (Frappe đã có `modified`) | CHỜ-DỮ-LIỆU |
| `reason` | Reason | Small Text | Lý do | Không vào tính toán; hit `setup/custom_fields.py:193-221` là **khoá dict** `STALE_CUSTOM_FIELDS[...]["reason"]` — trùng tên | BỎ — không có writer/reader |

**Giảm phức tạp:**
- `changed_by`/`changed_on` trùng chức năng với `owner`/`modified` của Frappe — nếu làm thật thì bỏ 2 field này.
- Cả bảng đang chiếm chỗ trên form phiên bản mà không có dữ liệu; nên ẩn trước, xoá sau khi đếm.

---

#### AL Bom Item — bảng con, 38 field

**Vai trò:** Dòng vật tư trung tâm — mỗi dòng là một thành phần của sản phẩm (nhôm, kính, thép,
phụ kiện…). Người cấu hình nhập trong `AL Bom Set.items`.
**Ai dùng:** Engine B2 (nạp dữ liệu chủ) + B3 (dựng công thức) + B4 (tính) + B5 (gán ngăn chi phí).
**Tổng kết:** 38 field · 16 field vào engine · 2 field được biên dịch nhưng kết quả không ai đọc ·
7 field cấu hình/hiển thị/validate · 13 field không tham chiếu · **đề xuất:** giữ 21, bỏ 6, ẩn 10, gộp 1.

**Bản đồ field → bước (chỉ các field thực sự đi vào phép tính):**

| Bước | Field được đọc | Việc xảy ra |
|---|---|---|
| B1 | — | Dòng vật tư chưa được đọc; chỉ biến toàn cục |
| B2 | `slug`, `category`, `item_code`, `price_base_item`, `default_glass_master`, `item_selection_mode`, `item_rule`, `rule_input_expr`, `default_color`, `unit_price`* | `:894-900` đọc `bom_set_snapshot.items`; `:908-925` gom mã để batch; `:1005-1019` dựng `glass_data`; `:1037-1049` giải rule; `:1108-1169` dựng `row_literals` |
| B3 | `width`, `height`, `qty`, `calc_pattern`, `input_vars`, `cost_bucket`* | `:2058-2105` chèn literal + biến phụ; `:2108-2119` biên dịch các field công thức; `:2121-2151` sinh `unit_qty`/`total_qty`/`line_total` |
| B4 | — (đọc kết quả B3) | `:2239` engine tính; `:2289-2314` ghi `bom_result` (kèm `cost_bucket`, `item_code`) |
| B5 | `cost_bucket` | `:2366-2374` cộng `line_total` vào ngăn |
| B6 | — | Dòng vật tư không còn tham gia; chỉ bucket đi tiếp |
| B7 | — | Ghi JSON kết quả vào Quotation Item |

\* `unit_price` của dòng chỉ có ở phụ kiện; dòng BOM lấy giá qua `item_code`/`price_base_item`.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `slug` | Slug | Link AL Slug Library | Khoá dòng + nguồn nhãn | B2 `:1110` khoá `row_literals`; B3 `:2059` tiền tố biến `{slug}__`; `:2156-2162` dựng dict `items` cho tham chiếu chéo | GIỮ — hợp đồng xuyên B2–B6 |
| `category` | Material Category | Link AL Material Category | Nhóm vật tư | B2 `:986-994` lấy `scrap_pct`/`has_weight`; `:1008` nhận diện dòng kính; `:1300-1320` lọc trục giá theo nhóm | GIỮ |
| `line_name` | Line Name | Data | Nhãn dòng cho người đọc | Không vào phép tính. Tự điền từ Slug Library (`al_bom_item.py:168-178`); dùng làm nhãn trong danh mục biến (`variable_sources/adapters.py:769-776,883`) | GIỮ — nhãn người dùng phải thấy |
| `is_active` | Is Active? | Check | Tắt dòng khỏi cấu trúc | Engine **không** tự lọc; bị loại lúc chụp phiên bản — `al_bom_version.py:121` `if not i.is_active: continue` | GIỮ — nhưng chỉ có tác dụng khi tạo/publish phiên bản mới |
| `show_condition` | Show Condition (FB formula) | Small Text | Ý định ẩn/hiện dòng theo điều kiện | B3 biên dịch thành `{slug}__show_condition` (`:239-240`, `:2108-2117`), B4 tính — nhưng **không chỗ nào đọc kết quả** (`bom_result` `:2289-2314` không có field này) | ẨN — công thức chạy mà không ai dùng, còn sinh lỗi giả |
| `cost_bucket` | Cost Bucket | Link AL Cost Bucket | Ngăn chi phí | B4 `:2299` chép vào kết quả; B5 `:2366-2374` cộng dồn theo mã | GIỮ — quyết định dòng tiền vào ngăn nào |
| `item_selection_mode` | Item Selection Mode | Select Fixed/Rule/Formula | Cách chọn mã hàng | B2 chỉ rẽ nhánh `Rule` (`:1038`, `:1154`). Giá trị `Formula` **không có nhánh xử lý nào** trong toàn engine | GIỮ — nhưng phải bỏ lựa chọn `Formula` (xem Giảm phức tạp) |
| `item_code` | Item Code | Link Item | Mã hàng cố định | B2 `:916-917` gom batch, `:1133-1134` tra giá/khối lượng; B4 `:2291` | GIỮ |
| `item_rule` | Item Rule | Link AL Dynamic Item Rule | Luật chọn mã theo đầu vào | B2 `:924-925` gom rule, `:1038-1049` giải ra `item_code` | GIỮ — chỉ dùng khi mode = Rule |
| `item_fallback` | Item Fallback | Link Item | Mã dự phòng khi rule không ra | Không có tham chiếu — `bom_orchestrator.py` không đọc field này | ẨN — tính năng dự phòng **chưa cài**; rule trượt hiện ra giá 0 kèm cảnh báo |
| `item_condition_formula` | Item Condition Formula | Small Text | Điều kiện chọn mã khi mode = Formula | B3 biên dịch (`:240`) và B4 tính; **kết quả không ai đọc**. Chỉ được validate bắt buộc (`al_bom_item.py:161-166`) | ẨN — đi cùng số phận với mode `Formula` |
| `allow_sales_override` | Allow Sales Override? | Check | Ý định cho phép kinh doanh đổi mã nhóm | Không có tham chiếu | ẨN — tính năng sale đổi mã **chưa cài** |
| `override_item_group` | Override Item Group | Link Item Group | Nhóm hàng được đổi | Không có tham chiếu | ẨN — tính năng sale đổi mã **chưa cài** |
| `allow_substitute` | Allow Substitute? | Check | Ý định cho phép thay thế vật tư | Không có tham chiếu | ẨN — tính năng thay thế vật tư **chưa cài** |
| `substitute_item_group` | Substitute Item Group | Link Item Group | Nhóm hàng thay thế | Không có tham chiếu | ẨN — đi kèm `allow_substitute`, **chưa cài** |
| `width` | Width Formula (FB syntax) | Small Text | Công thức rộng | B3 `:2126-2130` truyền làm tham số thứ 2 của `lookup_calc_pattern`; `:2281-2286` dùng cho trace | GIỮ |
| `height` | Height Formula (FB syntax) | Small Text | Công thức cao | B3 `:2126-2130` tham số thứ 3; trace `:2281-2286` | GIỮ |
| `qty` | Qty Formula (FB syntax) | Small Text | Công thức số lượng | B3 `:2140-2143` — `total_qty = unit_qty × qty`; bắt buộc (`al_bom_item.py:136-137`) | GIỮ |
| `calc_pattern` | Calc Pattern | Link AL Quantity Calc Method | Cách quy đổi kích thước → đơn vị | B3 `:2037-2053` nạp biến phụ của pattern; `:2127` gọi `lookup_calc_pattern(code,w,h,tlr)` | GIỮ |
| `input_vars` | Input Vars (extra) | JSON | Giá trị biến phụ cho pattern | B3 `:2164-2179` parse; `:2081-2105` ưu tiên: dòng → biến toàn cục → literal → 0 | GIỮ |
| `price_type` | Price Type | Select Item Price/Rule/Fixed | Ý định chọn nguồn giá | **Engine không đọc** — chính mã ghi rõ ở `al_bom_item.py:101-107`. Chỉ còn tác dụng điều khiển ẩn/hiện ô `price_base_item` | GỘP — gộp vào `price_base_item`: luôn hiện ô giá đại diện, bỏ 2 lựa chọn Rule/Fixed |
| `price_base_item` | Price Base Item | Link Item | Mã đại diện để tra bảng giá composite | B2 `:918-920` gom batch; `:1133-1134` ưu tiên tra theo mã này; bắt buộc theo nhóm (`al_bom_item.py:108-117`) | GIỮ — quyết định **giá đơn vị** của dòng |
| `price_rule` | Price Rule | Link AL Calculation Rule | Ý định tra giá bằng rule | Không có tham chiếu (hidden) | BỎ — giá đi qua `price_base_item`/Item Price |
| `price_list` | Price List | Link Price List | Ý định chọn bảng giá cho dòng | **Engine không đọc field của dòng.** Bảng giá lấy từ `source_config.price_list` của Formula Variable Binding (`bom_orchestrator.py:1628`) hoặc `Selling Settings` (`:165-166`). 36 hit `price_list` trong engine đều là biến cục bộ — **trùng tên, chưa chắc** | BỎ — thay bằng cấu hình binding/Selling Settings |
| `fixed_price` | Fixed Price | Currency | Ý định ghi giá cố định | Không có tham chiếu (hidden) | BỎ — thay bằng Item Price, hoặc dùng `unit_price` của dòng phụ kiện |
| `cut_fee_pct` | Cut Fee (%) | Float | Phí cắt kính | Không được đọc từ DocType này; chỉ xuất hiện ở mẫu công thức `formula_builder/templates.py:69-117` | BỎ — thay bằng dòng công thức trong Cost Template |
| `default_glass_master` | Default Glass Master | Link AL Glass Master | Mã kính mặc định cho dòng kính | B2 `:921-923` gom batch; `:1009-1016` lấy độ dày/loại kính; `:1116-1120` thay `item_code` bằng mã kính đã chọn | GIỮ — quyết định giá và validate khổ kính |
| `ctx_inject_prefix` | CTX Inject Prefix | Data | Tiền tố biến ngữ cảnh (dự kiến) | Không engine nào đọc; chỉ bị bắt buộc bởi `al_bom_item.py:129-134` khi nhóm khai `requires_ctx_inject_prefix` | BỎ — thay bằng tham chiếu `items.<slug>.<field>` đã có |
| `panel_count_formula` | Panel Count Formula | Small Text | Công thức số tấm panel | Không engine nào đọc — `public/js/formula_setup.js:228-230` ghi rõ 2 field này cố ý không đăng ký | ẨN — tính năng panel **chưa cài** |
| `qty_per_panel_formula` | Qty Per Panel Formula | Small Text | Công thức số lượng mỗi panel | Không engine nào đọc (cùng nguồn trên) | ẨN — tính năng panel **chưa cài** |
| `panel_glass_override_allowed` | Panel Glass Override Allowed? | Check | Ý định cho đổi kính theo panel | Không có tham chiếu | ẨN — tính năng đổi kính theo panel **chưa cài** |
| `rule_input_expr` | Rule Input Expression | Small Text | Biểu thức lấy đầu vào cho rule | B2 `:1041` gọi `_resolve_rule_input_for_item`; `:1953-1969` parse `items.<slug>.<field>`; bắt buộc khi mode = Rule (`al_bom_item.py:145-159`) | GIỮ |
| `formula_set` | Formula Set | Link Formula Set | Ý định gắn bộ công thức | Không có tham chiếu (hidden) | BỎ — công thức đi qua `AL Cost Template` |
| `default_color` | Default Color | Link AL Color Standard | Màu đại diện để đổi màu theo vị trí | B2 `:1128-1129`; `:1423-1453` đổi biến màu khi tra giá composite | GIỮ |
| `supplier_location` | Noi cap vat tu | Data | Nơi cấp vật tư | B2 `:1147` → B4 `:2310` → `quotation.js:132` | GIỮ |
| `install_position` | Vi tri lap dat | Data | Vị trí lắp đặt | B2 `:1148` → B4 `:2311` → `quotation.js:133` | GIỮ |
| `cut_angle` | Goc cat | Data | Góc cắt | B2 `:1149` → B4 `:2312` → `quotation.js:134` | GIỮ |
| `note` | Ghi chu | Small Text | Ghi chú dòng | B2 `:1150` → B4 `:2313` → `quotation.js:82` | GIỮ |

**Giảm phức tạp:**
- **Bỏ lựa chọn `Formula` của `item_selection_mode`.** Hiện chỉ `Rule` được xử lý
  (`bom_orchestrator.py:1038,1154`); dòng ở chế độ `Formula` vẫn được tính như dòng thường, và nếu
  dòng không có cả `item_code` lẫn `price_base_item` thì `unit_price = 0` **âm thầm**
  (`:1133-1134`) — không cảnh báo, không chặn.
- **Bỏ 6 field có đường thay thế** (`price_rule`, `price_list`, `fixed_price`, `cut_fee_pct`,
  `formula_set`, `ctx_inject_prefix`) và **ẩn 8 cờ của tính năng chưa cài** (`item_fallback`,
  `allow_sales_override`, `override_item_group`, `allow_substitute`, `substitute_item_group`,
  `panel_count_formula`, `qty_per_panel_formula`, `panel_glass_override_allowed`) — hầu hết đã
  `hidden`, ẩn thêm không đổi phép tính; xoá khỏi schema chỉ nên làm sau khi chốt không cần các
  tính năng đó. Hai field điều kiện `show_condition` / `item_condition_formula` cũng nằm trong
  nhóm ẩn (xem bảng trên).
- `price_list` trên dòng là bẫy tốn tiền: người dùng chọn bảng giá A, engine lại tra bảng giá cấu
  hình trong binding — nên bỏ hoặc nối vào `source_config` của dòng.

---

#### AL Bom Set — doc, 14 field

**Vai trò:** Cấu trúc sản phẩm: danh sách `AL Bom Item` + các cấu hình dùng chung (nhóm sản phẩm,
hệ profile, bộ biến, bộ phụ kiện mặc định, cách dựng công thức).
**Ai dùng:** Engine B1 (resolve biến hệ thống theo `profile_system`/`product_type`), B2 (nạp phụ kiện
mặc định, đọc `formula_fieldnames`), B3 (`apply_scrap_pct`); phần lớn qua **snapshot** của BOM Version.
**Tổng kết:** 14 field · 7 field vào engine · 4 field cấu hình/hiển thị · 3 field không tham chiếu ·
**đề xuất:** giữ 11, ẩn 2, 1 chờ dữ liệu.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `set_code` | Set Code | Data | Mã bộ = tên bản ghi | `al_bom_version.py:132-138` chép vào snapshot; engine chỉ đọc `items` từ snapshot (`bom_orchestrator.py:900`) | GIỮ |
| `set_name` | Set Name | Data | Tên bộ | `api/__init__.py:1372` (hiển thị) | GIỮ |
| `item_code` | Mã sản phẩm | Link Item | Ý định gắn bộ với mã sản phẩm | Không có tham chiếu | ẨN |
| `product_type` | Product Type | Link AL Product Type | Loại sản phẩm | B1 resolve biến hệ thống: `NC_SX_PCT`, `NC_LD_PCT`, `PROFIT_MARGIN` khai `source_doctype=AL Product Type` (`setup/seed_demo_data.py:230-232`); resolver dò field Link (`al_bom_engine/system_variable_resolver.py:60-80`) tại `bom_orchestrator.py:663-685` | GIỮ — quyết định % nhân công/lợi nhuận |
| `brand` | Brand | Link Brand | Hãng nhôm | Không vào tính toán; `api/__init__.py:1136` hiển thị ở dialog | GIỮ |
| `profile_system` | Profile System | Link AL Profile System | Hệ profile (khe hở, offset) | B1: biến `OFFSET_*` khai `source_doctype=AL Profile System` (`setup/seed_demo_data.py:228-231`), resolve cùng đường trên | GIỮ — quyết định kích thước tính toán |
| `variable_set` | Variable Set | Link AL Variable Set | Bộ biến người dùng nhập | `api/__init__.py:1024` (khi BOM trỏ tới bộ này), `:1154-1155` | GIỮ |
| `default_accessory_set` | Default Accessory Set | Link AL Accessory Set | Bộ phụ kiện mặc định | B2 `bom_orchestrator.py:846` — chỉ dùng khi `al_bom_vars` không có `accessory_set` | GIỮ |
| `version` | Version | Data | Nhãn phiên bản của bộ | Không có tham chiếu (phiên bản thật nằm ở `AL BOM Version.version_name`) | ẨN — trùng ý niệm, dễ sửa nhầm |
| `is_active` | Is Active? | Check | Cờ tắt bộ | Không có tham chiếu | CHỜ-DỮ-LIỆU |
| `variable_profile` | Variable Profile | Link AL Variable Profile | Hồ sơ gợi ý biến | `api/variable_catalog.py:63-79` (autocomplete) | GIỮ |
| `formula_fieldnames` | Formula Fieldnames | Small Text (JSON) | Danh sách field được coi là công thức | B2 `bom_orchestrator.py:1172-1178`; B3 `:2017` (`formula_fields = self._formula_fieldnames or DEFAULT_FORMULA_FIELDS`) | GIỮ — quyết định field nào được biên dịch |
| `apply_scrap_pct` | Áp dụng hao hụt cắt vật tư (Scrap %)? | Check | Bật hao hụt cắt | B3 `:2033-2034`; khi bật, `total_qty = unit_qty × qty × (1 + scrap_pct/100)` (`:2138-2141`) | GIỮ — thay đổi tiền thật, đang tắt mặc định |
| `items` | Items | Table AL Bom Item | Danh sách dòng vật tư | Không đọc trực tiếp — `al_bom_version.py:119-130` chụp (bỏ dòng `is_active=0`), engine đọc snapshot (`bom_orchestrator.py:900`) | GIỮ |

**Giảm phức tạp:**
- `version` và `is_active` không có runtime; ẩn khỏi form để người cấu hình không tưởng là có tác dụng.
- `formula_fieldnames` nên có mô tả trên form: đây là danh sách field **được biên dịch**, không phải
  danh sách field hiển thị.

---

#### AL BOM Version — doc, 9 field

**Vai trò:** Ảnh chụp bất biến của một cấu hình BOM tại thời điểm publish. Mỗi báo giá ghim vào một
phiên bản để tái lập được giá đã gửi khách.
**Ai dùng:** Engine B0 (chọn phiên bản), B2 (đọc `bom_set_snapshot` + `pricing_dimension_snapshot`),
B6 (đọc `cost_template_snapshot`). Workflow điều khiển `workflow_state`.
**Tổng kết:** 9 field · 4 field vào engine · 2 field cấu hình/hiển thị · 3 field không tham chiếu ·
**đề xuất:** giữ 6, ẩn 1, bỏ 2 (gồm cả bảng Change Log).

**Ba snapshot — ai ghi, engine đọc ở đâu:**

| Snapshot | Người ghi | Engine đọc | Cảnh báo |
|---|---|---|---|
| `bom_set_snapshot` (JSON) | `al_bom_version.py:19-25` → `_take_snapshots()` `:108-138`, chạy ở `before_insert` | B2 `bom_orchestrator.py:894-900` — **chỉ đọc khoá `items`** | Có người ghi, có người đọc. Header (`set_code`, `set_name`, `product_type`, `profile_system`) được chụp nhưng engine **không đọc** — B1 vẫn lấy `profile_system`/`product_type` **live** từ `AL Bom Set` (`:655-685`, `:771-774`). Sửa Bom Set sau khi publish ⇒ biến `OFFSET_*`/`NC_*` đổi theo ⇒ **báo giá cũ không tái lập được** dù snapshot items đã đóng băng |
| `cost_template_snapshot` (JSON) | Duy nhất `al_bom_version.py:140-159` (`before_insert`), chỉ khi `AL BOM.default_cost_template` có giá trị | B6 `bom_orchestrator.py:2489-2499`; dòng `is_final_price`/`is_pre_vat_price` đọc tiếp ở `:2601-2619` | **Rủi ro cao:** nếu tạo phiên bản lúc BOM chưa có `default_cost_template`, field này **rỗng vĩnh viễn** — không có backfill khi publish (hàm `_backfill_pricing_snapshot_on_publish` chỉ chụp bù *pricing dimension*, `:60-77`). B6 gặp rỗng thì `return` im lặng (`:2489-2490`) ⇒ **giá bán = 0, không có lỗi nào được ném** |
| `pricing_dimension_snapshot` (Long Text) | `before_insert` (`:24-25`) + chụp bù đúng lúc chuyển Published (`:60-77`) | B2 `_get_dim_fieldnames` `:1194-1216` và `_get_dim_mappings_raw` `:1256-1273`; dùng cho tra giá composite và `multiplier_chain` | Có người ghi, có người đọc, có bảo vệ bất biến (`:79-106`). Phiên bản cũ chưa có snapshot sẽ rơi về **cấu hình live** (`:1218-1242`) — mất tính tái lập, có cảnh báo trong log |

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `bom` | BOM | Link AL BOM | BOM cha | B0 `bom_orchestrator.py:362,820-825` — dùng để nạp Bom Set | GIỮ |
| `version_name` | Version Name | Data | Tên phiên bản, nằm trong `autoname` | Không vào phép tính; `al_bom.py:17-32` sinh tên kế tiếp | GIỮ — là một phần định danh |
| `valid_from` | Valid From | Datetime | Ngày bắt đầu hiệu lực | Không ai đọc; chỉ được ghi lúc tạo (`al_bom.py:95`, `al_design_revision.py:28`). 8 hit `valid_from` trong engine đều là của **Item Price** — trùng tên | ẨN — hiệu lực thật do `workflow_state` + `current_version` quyết định |
| `valid_to` | Valid To | Datetime | Ngày hết hiệu lực | Không có tham chiếu (hidden) | BỎ — thay bằng `workflow_state = Retired` |
| `workflow_state` | Workflow State | Select Draft/Pending Approval/Approved/Published/Retired | Trạng thái duyệt | `al_bom_version.py:32-58` chỉ ghi `AL BOM.current_version` khi **vừa** Published; Workflow cấu hình ở `setup/install_workflows.py` | GIỮ |
| `bom_set_snapshot` | BOM Set Snapshot | JSON | Ảnh chụp danh sách dòng vật tư | B2 `:894-900` — bắt buộc, thiếu thì ném "BOM Version không có snapshot" (`:894-895`) | GIỮ |
| `cost_template_snapshot` | Cost Template Snapshot | JSON | Ảnh chụp công thức giá thành | B6 `:2489-2499`; thiếu thì B6 thoát **im lặng** | GIỮ |
| `pricing_dimension_snapshot` | Pricing Dimension Snapshot | Long Text (JSON) | Ảnh chụp trục giá + mapping | B2 `:1194-1216`, `:1256-1273` | GIỮ |
| `items` | Change Log Items | Table AL BOM Change Log | Nhật ký thay đổi | **Không có writer, không có reader** — không dòng mã nào thêm dòng vào bảng này | BỎ (hoặc ẩn) — bảng chết |

**Giảm phức tạp:**
- Thêm chốt ở `before_insert`: nếu `AL BOM.default_cost_template` rỗng thì **chặn tạo phiên bản** kèm
  thông báo, thay vì để B6 trả giá bán 0 im lặng.
- Cân nhắc chụp cả `profile_system`/`product_type` **đã dùng** vào snapshot và cho B1 đọc từ snapshot —
  hiện tại đây là lỗ duy nhất khiến "bất biến" không trọn.
- `valid_from`/`valid_to`/`items` không tham gia gì; ẩn khỏi form.

---

#### AL Cost Bucket — doc, 12 field

**Vai trò:** Một "ngăn" chi phí (nhôm, kính, nhân công, vận chuyển…). Dòng vật tư gán vào ngăn qua
`AL Bom Item.cost_bucket`; ngăn lại được công thức giá thành tham chiếu.
**Ai dùng:** Engine B5 (`bom_orchestrator.py:2351-2463`); danh mục biến (autocomplete) đọc để gợi ý
mã ngăn; validate form đọc `source_config`/`depends_on`.
**Tổng kết:** 12 field · 3 field vào engine · 3 field cấu hình/hiển thị · 6 field không tham chiếu ·
**đề xuất:** giữ 6, ẩn 4, bỏ 1, 1 chờ dữ liệu.

**Đường đi của tiền (bucket → giá bán):**

1. `AL Bom Item.cost_bucket` gán mỗi dòng vào một mã ngăn (`bom_orchestrator.py:2299`).
2. **B5**: engine đọc `AL Cost Bucket` theo `bucket_code` (`:2400-2405`). Nếu `source_type =
   aggregate_from_items` **và** `source_config` khác rỗng → dựng binding và gọi Formula Builder
   (`:2412-2452`); ngược lại cộng tay `line_total` của mọi dòng cùng ngăn (`:2363-2375`).
3. **B6**: mỗi dòng `AL Cost Template Item.calc_formula` được biên dịch thành một biến tên
   `line_code`, chạy tuần tự trên nền `inputs + buckets` (`:2507-2527`, `:2563`).
4. Dòng có `is_final_price = 1` cho ra **giá bán cuối** (ghi `al_gia_vat`); dòng có
   `is_pre_vat_price = 1` cho ra **giá trước VAT** (ghi `al_gia_ban` và `rate`) —
   `:2570`, `:2601-2619`, `:2661-2666`.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `bucket_code` | Bucket Code | Data | Mã ngăn = tên bản ghi | B5 `:2400-2405` truy vấn theo `bucket_code`; `:2434` dùng làm tên biến khi resolve qua FB | GIỮ — cũng là mã công thức tham chiếu; nên viết HOA |
| `bucket_name` | Bucket Name | Data | Tên ngăn cho người đọc | `api/__init__.py:751-758` (gợi ý/ hiển thị), `variable_sources/adapters.py:278-305` | GIỮ |
| `bucket_role` | Bucket Role | Select LEAF/AGGREGATE | Phân loại ngăn | B5 **có select** (`:2404`) nhưng **không dùng để rẽ nhánh** — quyết định chỉ dựa vào `source_type`. Ngăn AGGREGATE chỉ tồn tại như một `line_code` của Cost Template | ẨN — chỉ còn giá trị mô tả |
| `parent_bucket` | Parent Bucket | Link AL Cost Bucket | Ý định dựng cây ngăn | Không engine nào đọc; chỉ seed ghi (`setup/seed_demo_data.py:182`) | BỎ — B5 không dựng cây |
| `is_active` | Is Active? | Check | Cờ tắt ngăn | Không có tham chiếu — B5 không lọc `is_active` | CHỜ-DỮ-LIỆU |
| `source_type` | Source Type | Select 8 giá trị | Cách lấy số cho ngăn | B5 `:2414` — **chỉ `aggregate_from_items` có nhánh xử lý**; 7 giá trị còn lại chỉ sinh cảnh báo `bucket_source_type_chua_ho_tro` (`:2419-2426`) | GIỮ — nhưng phải rút danh sách xuống 1 giá trị (hoặc bổ sung nhánh) |
| `source_config` | Source Config | JSON | Tham số cho `source_type` | B5 `:2428-2439` — rỗng thì rơi về cộng Python. Đường FB cần thêm `rows_source = resolved`, `key_field`, `key_value`, `value_field`/`sum_field`, `aggregate` (contract `formula_builder/docs/aggregate_from_items.md`) | GIỮ — nhưng validate chỉ bắt `sum_field` (`al_cost_bucket.py:39-41`), thiếu khoá thì rơi về fallback |
| `depends_on` | Depends On | JSON | Ý định khai phụ thuộc giữa ngăn | Chỉ được validate là JSON array (`al_cost_bucket.py:49-58`). 7 hit `ui` là thuộc tính `depends_on` của **field khác** trong form JSON — **trùng tên** | ẨN — không có sắp xếp topo nào |
| `batch_group` | Batch Group | Data | Ý định gom nhóm xử lý | Chỉ patch seed ghi chuỗi rỗng (`patches/v28_9/…:88`, `v28_11/…:102`) | ẨN — engine không đọc; gom lô **chưa cài** |
| `default_expense_account` | Default Expense Account | Link Account | Tài khoản chi phí | Không có tham chiếu | BỎ — hạch toán do ERPNext lo, engine không ghi GL |
| `report_group` | Report Group | Data | Nhóm báo cáo | `api/__init__.py:751-758`, `variable_sources/adapters.py:278-280` (nhóm trong autocomplete) | GIỮ |
| `sort_order` | Sort Order | Int | Thứ tự hiển thị | `variable_sources/adapters.py:279-280` (autocomplete); engine **không** đọc | GIỮ — chỉ ảnh hưởng thứ tự gợi ý |

**Giảm phức tạp:**
- Rút `source_type` xuống `aggregate_from_items` (hoặc ẩn 7 lựa chọn) — hiện người cấu hình chọn
  `formula`/`pipeline`… và tin là có tác dụng, nhưng engine chỉ cảnh báo rồi cộng tay.
- Bổ sung validate: nếu `source_type = aggregate_from_items` thì bắt buộc `rows_source`, `value_field`
  (hoặc alias `sum_field`), `aggregate` — nếu không, cấu hình "hợp lệ" vẫn âm thầm rơi về Python.
- `bucket_role`/`parent_bucket` gợi ý một mô hình cây không tồn tại; ẩn/bỏ để khỏi bảo trì.

---

#### AL Cost Template — doc, 6 field

**Vai trò:** Mẫu công thức biến các ngăn chi phí thành giá thành và giá bán. Người cấu hình tạo; BOM
trỏ tới qua `AL BOM.default_cost_template`.
**Ai dùng:** Engine B6 (qua `cost_template_snapshot`); nếu báo giá truyền `_cost_template` thì B6 đọc
**trực tiếp** doc này (`bom_orchestrator.py:2472-2488`). Form có validate công thức.
**Tổng kết:** 6 field · 2 field vào engine · 2 field cấu hình/hiển thị · 2 field không tham chiếu ·
**đề xuất:** giữ 4, 1 ẩn, 1 chờ dữ liệu.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `template_code` | Template Code | Data | Mã mẫu = tên bản ghi | Nhánh override chép vào snapshot (`bom_orchestrator.py:2476`); giá trị này không tham gia phép tính | GIỮ — định danh |
| `template_name` | Template Name | Data | Tên mẫu | `bom_orchestrator.py:2477` (chép vào snapshot); `api/__init__.py:1451` hiển thị | GIỮ |
| `product_type` | Product Type | Link AL Product Type | Phân loại mẫu | Không ai đọc — không có chỗ chọn mẫu theo `product_type` | ẨN |
| `is_active` | Is Active? | Check | Cờ tắt mẫu | Không có tham chiếu | CHỜ-DỮ-LIỆU |
| `variable_profile` | Variable Profile | Link AL Variable Profile | Hồ sơ gợi ý biến | `api/variable_catalog.py:63-79`; `al_cost_template.py:63-94` dùng khi validate công thức | GIỮ |
| `items` | Items | Table AL Cost Template Item | Các dòng công thức | B6 `:2507-2512` (dựng `global_formulas`), `:2585-2589` (trace) | GIỮ |

**Giảm phức tạp:**
- `product_type` trên mẫu không có tác dụng chọn mẫu — người dùng dễ tưởng hệ thống tự chọn theo loại.
- `is_active` nên có tác dụng hoặc ẩn; hiện mẫu "tắt" vẫn dùng được nếu BOM trỏ tới.

---

#### AL Cost Template Item — bảng con, 9 field

**Vai trò:** Một dòng công thức trong mẫu giá thành (VD `TONG_VL`, `NC_SX`, `GIA_BAN`, `GIA_VAT`).
Thuộc `AL Cost Template.items`.
**Ai dùng:** Engine B6 (thứ tự dòng = thứ tự tính), engine xác định giá bán qua 2 cờ; API hiển thị
dùng `line_label`/`cost_bucket`.
**Tổng kết:** 9 field · 4 field vào engine · 4 field cấu hình/hiển thị · 1 field không tham chiếu ·
**đề xuất:** giữ 6, ẩn 2, bỏ 1.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `sort_order` | Sort Order | Int | Thứ tự hiển thị | Engine **không đọc** — B6 chạy theo thứ tự dòng trong bảng (`bom_orchestrator.py:2507`, snapshot `al_bom_version.py:146-158` giữ nguyên thứ tự `ct.items`). Chỉ autocomplete dùng (`variable_sources/adapters.py:571`) | ẨN — dễ tưởng là đổi được thứ tự tính; muốn đổi phải kéo dòng |
| `line_code` | Line Code | Data | Mã dòng = tên biến trong công thức | B6 `:2509-2512` đặt tên công thức; các dòng sau tham chiếu mã này (`:2514-2517`) | GIỮ — quyết định thứ tự phụ thuộc |
| `line_label` | Line Label | Data | Nhãn hiển thị | Không vào phép tính; chép vào snapshot (`al_bom_version.py:148`), hiện ở `api/__init__.py:1555-1578` | GIỮ |
| `calc_formula` | Calc Formula | Small Text | Công thức của dòng | B6 `:2508-2512` (dựng), `:2563` (tính); trace `:2585-2589` | GIỮ — **quyết định giá** |
| `cost_bucket` | Cost Bucket | Link AL Cost Bucket | Ngăn chi phí mà dòng này đại diện | Không tham gia phép tính; chỉ để hiển thị/nhóm (`api/__init__.py:1555-1578`) | GIỮ — nhóm báo cáo |
| `is_subtotal` | Is Subtotal? | Check | Đánh dấu dòng tổng | Chỉ dùng ở preview (`al_cost_template.py:154`). Đường hiển thị thật **bỏ qua** cờ này và tự suy từ tiền tố mã: `api/__init__.py:1722` (`code.startswith(("TONG_","GIA_"))…`) | ẨN — cờ không có hiệu lực trên báo cáo |
| `is_final_price` | Là giá bán cuối cùng | Check | Dòng cho ra giá bán cuối | B6 `:2570` → `_resolve_final_price` `:2601-2609`; ghi `al_gia_vat` (`:2661-2665`). Không có cờ → fallback `line_code = "GIA_VAT"` | GIỮ — **quyết định giá bán** |
| `is_pre_vat_price` | Là giá trước VAT (đơn giá bán) | Check | Dòng cho ra giá trước VAT | `_resolve_pre_vat_price` `:2611-2619`; ghi `al_gia_ban` + `rate` (`:2658-2666`). Không có cờ → fallback `"GIA_BAN"` | GIỮ — **quyết định đơn giá bán** |
| `show_on_quotation` | Show on Quotation? | Check | Ý định hiện dòng trên báo giá | Không có tham chiếu (hidden) | BỎ |

**Giảm phức tạp:**
- Hai cờ `is_final_price`/`is_pre_vat_price` là chuẩn mới; nên cảnh báo trên form nếu không dòng nào
  bật cờ (khi đó engine rơi về tên `GIA_VAT`/`GIA_BAN` — nếu mẫu đặt tên khác thì giá bán = 0).
- `is_subtotal` và `sort_order` đang tạo cảm giác điều khiển được thứ tự/nhóm — nên ẩn hoặc sửa API
  hiển thị để đọc đúng cờ.

---

#### AL Design Revision — doc, 11 field

**Vai trò:** Phiếu đề nghị thay đổi thiết kế/spec. Khi được duyệt và có cờ tạo phiên bản, hệ thống tự
sinh một `AL BOM Version` mới.
**Ai dùng:** **Có runtime phía server** (`al_design_revision.py:8-31`), **form JS rỗng** — mọi thao tác
là form chuẩn của Frappe + Workflow. Không engine nào đọc bảng này.
**Tổng kết:** 11 field · 4 field có runtime · 4 field chỉ là nội dung người đọc · 3 field không tham chiếu ·
**đề xuất:** giữ 7, ẩn 3, 1 chờ dữ liệu.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `revision_code` | Revision Code | Data | Mã phiếu | Không có tham chiếu; `autoname = None` nên **không** phải tên bản ghi (tên là hash) | CHỜ-DỮ-LIỆU — dễ tưởng là định danh |
| `bom` | BOM | Link AL BOM | BOM bị ảnh hưởng | `al_design_revision.py:17-30` — dùng để tạo phiên bản mới cho đúng BOM | GIỮ |
| `requested_by` | Requested By | Link User | Người đề nghị | Không có tham chiếu; Frappe đã có `owner` | GIỮ — nội dung phiếu |
| `revision_type` | Revision Type | Select DIMENSION/MATERIAL/PROFILE_SYSTEM/GLASS_SPEC/ACCESSORY | Loại thay đổi | Không có tham chiếu — chỉ để người đọc phân loại | GIỮ |
| `workflow_state` | Workflow State | Select Draft/Under Review/Approved/Implemented | Trạng thái duyệt | `al_design_revision.py:12` — chỉ khi **vừa** `Approved` mới sinh phiên bản | GIỮ |
| `description` | Description | Text | Mô tả thay đổi | Không vào tính toán (16 hit `description` ở `fb_handlers.py` là mô tả binding — **trùng tên**) | GIỮ |
| `old_spec_json` | Old Spec (JSON) | JSON | Spec cũ | Không có tham chiếu | ẨN |
| `new_spec_json` | New Spec (JSON) | JSON | Spec mới | Không có tham chiếu | ẨN |
| `impact_analysis` | Impact Analysis | Text | Phân tích ảnh hưởng | Không có tham chiếu | ẨN |
| `requires_new_bom_version` | Requires New BOM Version? | Check | Yêu cầu sinh phiên bản mới | `al_design_revision.py:12-13` điều kiện sinh phiên bản | GIỮ |
| `new_bom_version` | New BOM Version | Link AL BOM Version | Phiên bản được sinh | `al_design_revision.py:31` ghi lại sau khi tạo | GIỮ |

**Giảm phức tạp:**
- `revision_code` không phải tên bản ghi và không ai đọc — nên ẩn hoặc chuyển thành `autoname`.
- 3 field spec/impact chưa có consumer: ẩn trước, chỉ xây khi có nhu cầu so sánh spec thật.

---

#### ConfigSnapshot — doc, 8 field

**Vai trò:** Bản lưu cấu hình + kết quả của một dòng báo giá tại thời điểm **submit** Quotation.
**Ai dùng:** **Có runtime phía server, không có form logic** (`configsnapshot.js` chỉ có 2 hàm rỗng) và
**không có ai đọc**. Người ghi duy nhất: `api/quotation_events.py:50-56` (hook `on_submit`).
**Tổng kết:** 8 field · 5 field được ghi · 0 field được đọc · 3 field không tham chiếu ·
**đề xuất:** giữ 5 field đang ghi, ẩn 2 field chưa có nơi ghi, bỏ 1; bổ sung đường đọc hoặc ghi rõ đây là kho lưu trữ.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `snapshot_id` | Snapshot ID | Data | Ý định mã bản lưu | Không có tham chiếu. Mã thật do `autoname()` sinh vào `name` (`configsnapshot.py:17-37`) — `snapshot_id` là field thứ hai cùng ý nghĩa | BỎ — trùng với `name` |
| `fb_snapshot_id` | FB Snapshot ID | Data | Ý định trỏ tới snapshot của Formula Builder | Không có tham chiếu; hook submit không ghi | ẨN — chưa có nơi ghi; giữ chỗ cho snapshot FB |
| `bom_version` | BOM Version | Link AL BOM Version | Phiên bản BOM đã dùng | `api/quotation_events.py:42,51` ghi từ `Quotation Item.al_bom_version` | GIỮ |
| `rule_version_ids` | Rule Version IDs | JSON | Ý định lưu phiên bản các rule | Không có tham chiếu | ẨN — chưa có nơi ghi; giữ chỗ cho ghim phiên bản rule |
| `quotation_item_name` | Quotation Item Name | Data | Dòng báo giá nguồn | `api/quotation_events.py:52` ghi; `configsnapshot.py:25` dùng trong `autoname` | GIỮ |
| `calculation_timestamp` | Calculation Timestamp | Datetime | Thời điểm tính | `api/quotation_events.py:53` ghi (thực chất là thời điểm submit) | GIỮ |
| `inputs_json` | Inputs (JSON) | JSON | Đầu vào đã dùng | `api/quotation_events.py:43,54` ghi `Quotation Item.al_bom_vars`. Hit `al_cost_template.py:134-137` là tham số `inputs_json` của `preview_cost_template` — **trùng tên** | GIỮ |
| `result_json` | Result (JSON) | JSON | Kết quả đã tính | `api/quotation_events.py:38,55` ghi `Quotation Item.al_bom_result`. Hit `bom_orchestrator.py:2644,2664` là **biến cục bộ** `result_json` trong B7 — trùng tên | GIỮ |

**Giảm phức tạp:**
- 3 field chết (`snapshot_id`, `fb_snapshot_id`, `rule_version_ids`) gợi ý một cơ chế chưa tồn tại.
- Cả bảng hiện là **kho ghi một chiều**: không API, không báo cáo nào đọc. Hoặc thêm màn tra cứu,
  hoặc ghi rõ trong mô tả DocType để người sau không tưởng là đã có đường đọc.

---

##### Tổng hợp nhóm

| DocType | Số field | Vào engine | Chỉ cấu hình/hiển thị | 0 tham chiếu | Đề xuất |
|---|---|---|---|---|---|
| AL Accessory Item | 11 | 8 | 3 | 0 | Giữ nguyên |
| AL Accessory Set | 8 | 2 | 3 | 3 | Giữ 5, ẩn 2, 1 chờ dữ liệu |
| AL BOM | 13 | 4 | 3 | 6 | Giữ 7, bỏ 2, ẩn 3, 1 chờ dữ liệu |
| AL BOM Change Log | 7 | 0 | 0 | 7 | Ẩn cả bảng, đếm dữ liệu rồi bỏ |
| AL Bom Item | 38 | 16 (+2 biên dịch mà bỏ kết quả) | 7 | 13 | Giữ 21, bỏ 6, ẩn 10, gộp 1 |
| AL Bom Set | 14 | 7 | 4 | 3 | Giữ 11, ẩn 2, 1 chờ dữ liệu |
| AL BOM Version | 9 | 4 | 2 | 3 | Giữ 6, bỏ 2 (gồm bảng Change Log), ẩn 1 |
| AL Cost Bucket | 12 | 3 | 3 | 6 | Giữ 6, ẩn 4, bỏ 1, 1 chờ dữ liệu |
| AL Cost Template | 6 | 2 | 2 | 2 | Giữ 4, ẩn 1, 1 chờ dữ liệu |
| AL Cost Template Item | 9 | 4 | 4 | 1 | Giữ 6, ẩn 2, bỏ 1 |
| AL Design Revision | 11 | 4 | 4 | 3 | Giữ 7, ẩn 3, 1 chờ dữ liệu |
| ConfigSnapshot | 8 | 5 (chỉ ghi, không đọc) | 0 | 3 | Giữ 5, ẩn 2, bỏ 1 |
| **Tổng** | **146** | **59** | **35** | **50** | — |

> Cột "Vào engine" của `ConfigSnapshot` là 5 field **được hook submit ghi** — không field nào được đọc
> lại. Cột "0 tham chiếu" chỉ tính field không có bất kỳ consumer nào (kể cả validate/hiển thị).
> 59 + 35 + 50 = 144; 2 field còn lại là `show_condition` và `item_condition_formula` của `AL Bom Item`
> (được biên dịch ở B3 nhưng kết quả không ai đọc) ⇒ đủ 146.

**Ba việc nên làm trước trong nhóm này:**

1. **Sửa lỗ hổng tái lập của phiên bản**: B1 vẫn đọc `profile_system`/`product_type` **live** từ
   `AL Bom Set` (`bom_orchestrator.py:655-685, 771-774`) dù snapshot đã chụp chúng
   (`al_bom_version.py:132-138`). Sửa Bom Set sau khi publish là báo giá cũ đổi giá — trong khi cả
   hệ thống được thiết kế để chống đúng điều này.
2. **Chặn phiên bản thiếu `cost_template_snapshot`**: B6 trả về im lặng (`bom_orchestrator.py:2489-2490`)
   ⇒ giá bán 0 không có lỗi. Thêm chốt ở `al_bom_version.py:19-25` khi `default_cost_template` rỗng.
3. **Dọn 14 field chết của `AL Bom Item` + 7 field của `AL BOM Change Log`**: trong đó `price_list`,
   `price_type`, `fixed_price`, `price_rule` khiến người cấu hình tin rằng mình điều khiển được giá
   (thực tế engine lấy giá từ `price_base_item` + bảng giá trong binding, `bom_orchestrator.py:1628`).

**Ba thứ KHÔNG nên đụng:**

1. **Ba snapshot của `AL BOM Version`** — đã có người ghi, người đọc và chốt bất biến
   (`al_bom_version.py:79-106`). Mọi thay đổi ở đây làm sai lịch sử báo giá đã gửi khách.
2. **Chuỗi B4 → B5 → B6**: `line_total` (`bom_orchestrator.py:2148-2151`) → cộng theo `cost_bucket`
   (`:2363-2375`) → `calc_formula` của Cost Template (`:2507-2563`). Đây là toàn bộ đường ra tiền;
   đổi thứ tự hoặc đổi tên biến là lệch giá hàng loạt.
3. **Hai cờ `is_final_price` / `is_pre_vat_price`** và cơ chế fallback `GIA_VAT`/`GIA_BAN`
   (`:2601-2619`): đang là hợp đồng với dữ liệu cũ; bỏ fallback sẽ làm các mẫu cũ trả 0.

---

### 8.3 AL Construction · Stock · Quality — 12 DocType

**Đo trên mã ngày 2026-11-19, repo `alumglass/alumglass` (chỉ đọc). 12 DocType · 101 field.**

**Trạng thái thật của nhóm — đọc trước khi đọc bảng:**

- **0/12 DocType** được engine giá đọc (không bước B0–B7 nào, `engine/bom_orchestrator.py` không nhắc tên DocType nào trong nhóm), **0/12** có mặt trong `api/__init__.py`, **0/12** có test.
- **Không mã nào tạo bản ghi** — toàn bộ 12 DocType chỉ có người dùng nhập tay trên form hoặc qua REST. Grep `new_doc("AL Site Survey|AL Installation…|…)` = **0 hit**; `get_all` duy nhất nhắm vào nhóm là trong hàm chết `get_pending_changes`.
- **7/12 controller chỉ có `pass`**: AL Installation Cost Actual, AL Installation Task, AL Installation Team, AL Punchlist Item, AL Site Survey Item, AL Warranty Policy, AL Project Warehouse Map.
- **5/12 có runtime thật**, nhưng chỉ trong phạm vi nội bộ nhóm: AL Change Order (`validate`), AL Handover Acceptance (`validate` + `on_update`), AL Installation Order (`validate` + `before_save`), AL Installation Progress (`after_insert`), AL Site Survey (`validate`).
- **9 tệp `.js` của nhóm đều là khung rỗng** (`refresh`/`validate` chỉ có comment) — không có nút, không có lọc link, không có cảnh báo.
- **11/12 DocType có `autoname` trống** ⇒ tên bản ghi là **hash ngẫu nhiên** (lõi Frappe: "If no rule defined, use hash" — `frappe/model/naming.py:135`). Chỉ AL Warranty Policy đặt `autoname='field:policy_code'`. Hệ quả: `*_code` là **Data gõ tay, không unique**, và là **nhãn duy nhất** người dùng thấy trong danh sách.
- **Phân quyền do `setup/install_roles.py` cấp** (chạy một lần ở `after_install`, `hooks.py:189`): AL Construction → AL Site Engineer create/write/delete (`install_roles.py:83-90`); AL Stock → BOM Manager + Site Engineer (`:70-73`); AL Quality → BOM Manager + Site Engineer (`:100-105`).

---

#### AL Change Order — doc, 15 field

**Vai trò:** Ghi nhận phát sinh sau khi chốt hợp đồng (đổi phạm vi / thiết kế / vật tư / giá) và lấy 2 chữ ký duyệt. **Ai tạo:** người dùng có role AL Site Engineer hoặc AL Sales User, nhập tay trên form — không có mã nào sinh bản ghi.
**Ai dùng:** chỉ `validate()` của chính nó (`al_change_order.py:8-13`). Hàm whitelist `get_pending_changes` (`:16-21`) **không có người gọi** — đã grep toàn repo = 1 hit duy nhất là định nghĩa. Cấu hình Workflow có trong `setup/install_workflows.py:76-105` nhưng **lệnh cài bị comment ở cả `hooks.py:191` và `hooks.py:235`** ⇒ site chưa chạy tay `install_workflows()` thì **không có Workflow**, `workflow_state` chỉ là Select trơ. Engine giá: **không đọc**.
**Tổng kết:** 15 field · 0 field vào engine giá (3 field được `validate()` đọc) · 2 field chỉ hiển thị · 10 field 0 tham chiếu · **đề xuất:** giữ 4 (2 field duyệt + `workflow_state` + `change_code`), ẩn 3, đếm dữ liệu 8 field còn lại trước khi ẩn.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `change_code` | Change Code | Data | Mã phát sinh người dùng đọc | `al_change_order.py:20` — chỉ nằm trong danh sách `fields` của hàm không ai gọi | GIỮ — mã duy nhất, tên doc là hash |
| `project` | Project | Link | Dự án phát sinh | Không vào tính toán — chỉ làm filter ở `al_change_order.py:19` (hàm chết) | CHỜ-DỮ-LIỆU — khoá nối dự án, có thể đã nhập |
| `sales_order` | Sales Order | Link | Đơn hàng gốc bị ảnh hưởng | Không vào tính toán — `hooks.py:38` là `doctype_js` của ERPNext, trùng tên | CHỜ-DỮ-LIỆU — reqd, chưa ai đọc |
| `requested_by` | Requested By | Link (User) | Người đề xuất | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — reqd, chưa ai đọc |
| `request_date` | Request Date | Date | Ngày đề xuất | `al_change_order.py:21` — chỉ dùng `order_by` của hàm chết | CHỜ-DỮ-LIỆU — có thể đã nhập |
| `change_type` | Change Type | Select | Loại phát sinh | `al_change_order.py:20` — chỉ trong hàm chết | CHỜ-DỮ-LIỆU — chưa có báo cáo nào đọc |
| `workflow_state` | Workflow State | Select | Trạng thái duyệt | `al_change_order.py:9` — `validate` chỉ ném lỗi khi bằng "Approved" | GIỮ — nhưng Workflow chưa được cài (hooks.py:191) |
| `description` | Description | Text | Nội dung thay đổi | Không vào tính toán — 16 hit `fb_handlers.py` là tham số `description=` của decorator | CHỜ-DỮ-LIỆU — reqd, nội dung chính người dùng gõ |
| `impact_scope` | Impact Scope | Text | Phạm vi ảnh hưởng | Không vào tính toán — 0 tham chiếu | ẨN — chồng nghĩa `description`, chưa ai đọc |
| `impact_cost` | Impact Cost | Currency | Tiền phát sinh | `al_change_order.py:20` — chỉ trong hàm chết | CHỜ-DỮ-LIỆU — số tiền thật, phải đếm trước khi ẩn |
| `impact_schedule_days` | Impact Schedule (days) | Int | Số ngày trễ | `al_change_order.py:20` — chỉ trong hàm chết | CHỜ-DỮ-LIỆU — chưa ai đọc |
| `customer_approval` | Customer Approved? | Check | Khách đã duyệt | `al_change_order.py:10` — chặn chuyển Approved; điều kiện Workflow `install_workflows.py:99` | GIỮ — cổng duyệt, permlevel 1 |
| `internal_approval` | Internal Approved? | Check | Nội bộ đã duyệt | `al_change_order.py:12` — chặn chuyển Approved; điều kiện Workflow `install_workflows.py:99` | GIỮ — cổng duyệt, permlevel 1 |
| `revised_quotation` | Revised Quotation | Link | Báo giá sửa lại | Không vào tính toán — 0 tham chiếu | ẨN — tính năng dự kiến, chưa nối |
| `revised_sales_order` | Revised Sales Order | Link | Đơn hàng sửa lại | Không vào tính toán — 0 tham chiếu | ẨN — tính năng dự kiến, chưa nối |

**Giảm phức tạp:**
- Bật `install_workflows()` hoặc bỏ hẳn cấu hình Workflow — hiện cả hai đầu đều là mã chết, người dùng thấy Select 5 giá trị mà không có nút chuyển.
- Gộp `impact_scope` vào `description`; `impact_cost` / `impact_schedule_days` chỉ giữ nếu có báo cáo tổng hợp phát sinh theo dự án.
- Hai field `revised_quotation` / `revised_sales_order` ẩn khỏi form tới khi có luồng sửa báo giá.
- Bỏ hàm `get_pending_changes` hoặc nối nó vào form (hiện là API mở không ai gọi).

---

#### AL Handover Acceptance — doc, 11 field

**Vai trò:** Biên bản nghiệm thu bàn giao, chốt hoàn thành thi công và mở mốc bảo hành. **Ai tạo:** người dùng AL Site Engineer nhập tay — không có mã nào sinh.
**Ai dùng:** `validate()` (`al_handover_acceptance.py:9-12`) và `on_update()` (`:14-21`) — `on_update` **ghi thẳng** `status = "Completed"` lên AL Installation Order qua `frappe.db.set_value` (bỏ qua `before_save` của lệnh thi công). Engine giá: **không đọc**. Đây là 1 trong 2 DocType của nhóm có mã ghi sang DocType khác.
**Tổng kết:** 11 field · 0 field vào engine giá (4 field được mã đọc/ghi) · 1 field chỉ hiển thị · 6 field 0 tham chiếu · **đề xuất:** giữ 5, đếm dữ liệu 6 field còn lại trước khi ẩn (không có field nào bỏ được ngay).

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `handover_code` | Handover Code | Data | Mã biên bản | Không vào tính toán — 0 tham chiếu | GIỮ — mã duy nhất, tên doc là hash |
| `project` | Project | Link | Dự án bàn giao | Không vào tính toán — 12 hit `setup/custom_fields.py` là field `project` của Quotation/SO/SE khác | CHỜ-DỮ-LIỆU — reqd, chưa ai đọc |
| `installation_order` | Installation Order | Link | Lệnh thi công được nghiệm thu | `al_handover_acceptance.py:18-21` — đích của `db.set_value` khi nghiệm thu đạt | GIỮ — cầu nối duy nhất sang lệnh thi công |
| `handover_date` | Handover Date | Date | Ngày bàn giao | `al_handover_acceptance.py:12` — fallback cho `warranty_start_date` | GIỮ — có mã đọc |
| `customer_representative` | Customer Representative | Data | Người đại diện khách ký | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — reqd, tên người ký thật |
| `company_representative` | Company Representative | Link (Employee) | Người đại diện công ty ký | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — reqd, chưa ai đọc |
| `acceptance_status` | Acceptance Status | Select | Kết quả nghiệm thu | `al_handover_acceptance.py:10,16,17` — quyết định có đóng lệnh thi công hay không | GIỮ — công tắc chính của DocType |
| `customer_signature` | Customer Signature | Attach Image | Ảnh chữ ký khách | Không vào tính toán — 0 tham chiếu, không print format nào in | CHỜ-DỮ-LIỆU — kiểm số bản ghi có tệp trước khi ẩn |
| `company_representative_signature` | Company Representative Signature | Attach Image | Ảnh chữ ký công ty | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — kiểm số bản ghi có tệp trước khi ẩn |
| `warranty_start_date` | Warranty Start Date | Date | Mốc bắt đầu bảo hành | `al_handover_acceptance.py:11-12` — tự điền khi nghiệm thu đạt | GIỮ — có mã ghi |
| `items` | Punchlist Items | Table (AL Punchlist Item) | Danh sách lỗi cần sửa | Không vào tính toán — **không dòng mã nào đọc bảng này** | CHỜ-DỮ-LIỆU — quan hệ cha–con đủ, thiếu người đọc |

**Quan hệ cha–con:** `items` là bảng con **AL Punchlist Item**; phía con Frappe tự ghi `parent` = tên biên bản, `parentfield` = `items`, nên đường nối cha→con **đủ**. Chỗ đứt: **không mã nào duyệt bảng `items`** — `on_update` đóng lệnh thi công mà **không kiểm** còn dòng punchlist nào OPEN, và AL Punchlist Item không có link ngược về `project` nên không truy vấn được "lỗi của dự án X" nếu không join qua bảng cha.

**Giảm phức tạp:**
- Thêm một dòng chặn: không cho `acceptance_status = ACCEPTED` khi còn punchlist `OPEN`/`IN_PROGRESS` — hiện chốt xong vẫn đóng lệnh thi công.
- Ghi luôn `actual_end_date` cho lệnh thi công ở `on_update` (hiện chỉ ghi `status`, `actual_end_date` chỉ có khi bảng Tasks đủ Completed).
- Ẩn 2 field chữ ký nếu không có print format in biên bản — hiện ảnh chữ ký không xuất hiện ở đâu.

---

#### AL Installation Cost Actual — doc, 9 field

**Vai trò:** Ghi chi phí thi công thực tế theo lệnh thi công (nhân công / vật tư / máy / vận chuyển / khác). **Ai tạo:** người dùng AL Site Engineer nhập tay — không có mã nào sinh.
**Ai dùng:** **không có consumer.** Controller là `pass` (`al_installation_cost_actual.py:5-7`); không engine, không API, không báo cáo, không test nào đọc. 4 hit `installation_order` trong input đều thuộc controller **của DocType khác** (AL Installation Progress, AL Handover Acceptance) — trùng tên, chưa chắc. Tài liệu `gia-ban-gia-dinh-muc-thuc-te.md:84` mô tả DocType này là "nguồn chi phí lắp đặt thực tế" — **đó là kế hoạch, chưa có mã**.
**Tổng kết:** 9 field · 0 field vào engine giá · 0 field chỉ hiển thị · 9 field 0 tham chiếu · **đề xuất:** đếm dữ liệu 7 field tiền trước khi đụng, ẩn 2 field nối chứng từ.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `installation_order` | Installation Order | Link | Lệnh thi công chịu chi phí | Không vào tính toán — 4 hit là `self.installation_order` của controller khác | CHỜ-DỮ-LIỆU — khoá cha, chưa ai đọc |
| `cost_date` | Cost Date | Date | Ngày phát sinh | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — reqd, có thể đã nhập |
| `cost_type` | Cost Type | Select | Loại chi phí | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — reqd, dùng cho phân loại tương lai |
| `amount` | Amount | Currency | Số tiền | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — **tiền thật**, tuyệt đối đếm trước khi ẩn |
| `paid_by` | Paid By | Select | Ai trả tiền | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — ảnh hưởng công nợ, có thể đã nhập |
| `description` | Description | Data | Diễn giải | Không vào tính toán — 19 hit `fb_handlers.py` là decorator, trùng tên | CHỜ-DỮ-LIỆU — reqd |
| `reference_doctype` | Reference DocType | Link (DocType) | Nối chứng từ gốc | Không vào tính toán — 0 tham chiếu | ẨN — tính năng dự kiến (nối PI/JE) |
| `reference_docname` | Reference Document | Dynamic Link | Bản ghi gốc | Không vào tính toán — 0 tham chiếu | ẨN — đi kèm `reference_doctype` |
| `receipt` | Receipt | Attach Image | Ảnh chứng từ | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — kiểm số bản ghi có tệp trước khi ẩn |

**Giảm phức tạp:**
- Cả DocType đang là "sổ tay tiền" — hoặc nối `amount` vào cost bucket như tài liệu hứa, hoặc ẩn khỏi menu trước khi người dùng nhập hàng loạt số liệu không ai đọc.
- 2 field `reference_*` là cặp dự kiến; nếu chưa nối chứng từ thì ẩn cả cặp.
- Nếu giữ: thêm ràng buộc `amount > 0` và `cost_date` không vượt hôm nay — hiện không có kiểm nào.

---

#### AL Installation Order — doc, 10 field

**Vai trò:** Lệnh thi công — giao việc cho một đội, giữ lịch kế hoạch/thực tế và danh sách công việc. **Ai tạo:** người dùng AL Site Engineer nhập tay — không có mã nào sinh từ Sales Order dù trường `sales_order` có.
**Ai dùng:** `validate()` (`al_installation_order.py:9-12`) kiểm thứ tự ngày; `before_save()` (`:14-26`) **tự chuyển `status`** theo số dòng Tasks đã Completed và tự điền `actual_start_date`/`actual_end_date`. Đây là DocType được nối nhiều nhất trong nhóm: bị ghi bởi AL Installation Progress (`al_installation_progress.py:14-20`) và AL Handover Acceptance (`al_handover_acceptance.py:18-21`). Engine giá: **không đọc**.
**Tổng kết:** 10 field · 0 field vào engine giá (6 field được mã đọc/ghi) · 1 field chỉ hiển thị · 3 field 0 tham chiếu · **đề xuất:** giữ 7, đếm dữ liệu 3 field còn lại (không bỏ field nào).

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `order_code` | Order Code | Data | Mã lệnh thi công | Không vào tính toán — 0 tham chiếu | GIỮ — mã duy nhất, tên doc là hash |
| `project` | Project | Link | Dự án thi công | Không vào tính toán — 12 hit `custom_fields.py` là `project` của DocType ERPNext khác | CHỜ-DỮ-LIỆU — reqd, chưa ai đọc |
| `sales_order` | Sales Order | Link | Đơn hàng nguồn | Không vào tính toán — `hooks.py:38` là `doctype_js` của Sales Order, trùng tên | CHỜ-DỮ-LIỆU — reqd, chưa ai đọc |
| `installation_team` | Installation Team | Link | Đội thi công | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — reqd, chưa ai đọc |
| `status` | Status | Select | Trạng thái lệnh | `al_installation_order.py:20,23` — tự đặt; bị ghi ngoài bởi `al_installation_progress.py:14,17` và `al_handover_acceptance.py:21` | GIỮ — có 3 nơi cùng ghi, xem cảnh báo bên dưới |
| `planned_start_date` | Planned Start Date | Date | Khởi công dự kiến | `al_installation_order.py:10-11` — kiểm không sau ngày kết thúc | GIỮ — có mã đọc |
| `planned_end_date` | Planned End Date | Date | Kết thúc dự kiến | `al_installation_order.py:10-11` — kiểm không trước ngày bắt đầu | GIỮ — có mã đọc |
| `actual_start_date` | Actual Start Date | Date | Khởi công thật | `al_installation_order.py:25-26` — tự điền lần đầu có task Completed; `al_installation_progress.py:19` ghi thêm | GIỮ — 2 nơi ghi |
| `actual_end_date` | Actual End Date | Date | Kết thúc thật | `al_installation_order.py:22` — đặt khi mọi task Completed; `al_installation_progress.py:15` đặt khi tiến độ 100% | GIỮ — 2 nơi ghi, không nơi nào xoá |
| `items` | Tasks | Table (AL Installation Task) | Danh sách công việc | `al_installation_order.py:16-19` — đếm dòng có `status == "Completed"` để chuyển trạng thái | GIỮ — nguồn duy nhất của `before_save` |

**Quan hệ cha–con:** `items` là bảng con **AL Installation Task** — đường nối cha→con đủ (Frappe ghi `parent`/`parentfield`). Đứt ở chỗ: **chỉ đúng một field của dòng con được đọc** là `status` (`al_installation_order.py:18`); 6 field còn lại của Task không ai đọc. Ngoài ra `status` của lệnh có **3 người ghi độc lập** (`before_save` theo Tasks, `after_insert` của Progress theo `progress_pct`, `on_update` của Handover) — không có thứ tự ưu tiên, nên lệnh có thể "Completed" trong khi Tasks còn dở (Progress đặt 100% ⇒ `order.save()` chạy `before_save` nhưng `completed < total` nên không đổi lại).

**Giảm phức tạp:**
- Chốt **một** nguồn sự thật cho `status`/`actual_*` (đề xuất: Tasks là chính, Progress chỉ ghi nhật ký) — hiện 3 chỗ ghi chồng.
- Không có mã nào tạo lệnh thi công từ Sales Order dù `sales_order` là reqd — nếu không định nối thì hạ xuống không bắt buộc.
- Thêm kiểm `planned_end_date >= planned_start_date` phía JS để báo ngay, hiện chỉ báo lúc lưu.

---

#### AL Installation Progress — doc, 8 field

**Vai trò:** Nhật ký tiến độ thi công, ghi theo từng ngày (được thiết kế append-only). **Ai tạo:** người dùng AL Site Engineer nhập tay — không có mã nào sinh.
**Ai dùng:** `after_insert()` (`al_installation_progress.py:8-20`) — đọc `installation_order` + `progress_pct` rồi **lưu** lệnh thi công để đổi `status`, `actual_start_date`, `actual_end_date`. Đây là luồng sống duy nhất giữa 2 DocType trong nhóm. Engine giá: **không đọc**.
**Tổng kết:** 8 field · 0 field vào engine giá (2 field được mã đọc) · 0 field chỉ hiển thị · 6 field 0 tham chiếu · **đề xuất:** giữ 2, ẩn 1 (`next_steps`), đếm dữ liệu 5 field còn lại.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `installation_order` | Installation Order | Link | Lệnh được báo cáo | `al_installation_progress.py:9-11` — nạp lệnh để cập nhật | GIỮ — khoá của luồng |
| `report_date` | Report Date | Date | Ngày báo cáo | Không vào tính toán — 0 tham chiếu (không sắp xếp, không chặn trùng ngày) | CHỜ-DỮ-LIỆU — reqd, người dùng thật gõ |
| `reported_by` | Reported By | Link (Employee) | Người báo cáo | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — reqd, chưa ai đọc |
| `progress_pct` | Progress (%) | Float | % hoàn thành | `al_installation_progress.py:12-17` — ≥100 ⇒ Completed; >0 ⇒ In Progress | GIỮ — công tắc chính |
| `description` | Description | Text | Diễn biến trong ngày | Không vào tính toán — 19 hit `fb_handlers.py` là decorator, trùng tên | CHỜ-DỮ-LIỆU — nội dung nhật ký |
| `issues` | Issues | Text | Vướng mắc | Không vào tính toán — 4 hit `quotation.js` là biến `issues` của bảng lỗi tính giá | CHỜ-DỮ-LIỆU — có thể đã ghi vướng mắc thật |
| `next_steps` | Next Steps | Text | Kế hoạch tiếp | Không vào tính toán — 0 tham chiếu | ẨN — chồng nghĩa `description`, chưa ai đọc |
| `attachments` | Attachments | Attach Image | Ảnh hiện trường | Không vào tính toán — 0 tham chiếu, không print/report nào hiện | CHỜ-DỮ-LIỆU — kiểm số bản ghi có tệp trước khi ẩn |

**Giảm phức tạp:**
- `progress_pct` không bị chặn khoảng: gõ 150 hay -5 đều lưu, và 150 vẫn đóng lệnh. Thêm ràng buộc 0–100.
- Không kiểm trùng `report_date` cho cùng một lệnh — nhật ký "append-only" nhưng lưu được nhiều dòng cùng ngày.
- `attachments` là Attach **single**: một ảnh cho cả báo cáo; nếu cần nhiều ảnh phải đổi sang bảng con.

---

#### AL Installation Task — bảng con, 7 field

**Vai trò:** Dòng công việc trong lệnh thi công (thuộc **AL Installation Order** qua field `items`). **Ai tạo:** người dùng thêm dòng trên lưới của lệnh thi công — không có mã nào sinh dòng.
**Ai dùng:** chỉ **một** field được đọc: `status`, tại `al_installation_order.py:18` (`completed = sum(1 for t in self.items if t.status == "Completed")`). Engine giá: **không đọc**; không API, không test.
**Tổng kết:** 7 field · 0 field vào engine giá (1 field được mã đọc) · 1 field chỉ hiển thị · 5 field 0 tham chiếu · **đề xuất:** giữ 2, ẩn 2, đếm dữ liệu 3 field còn lại.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `task_name` | Task Name | Data | Tên công việc | Không vào tính toán — 0 tham chiếu; là nhãn duy nhất của dòng trên lưới | GIỮ — không có nó dòng trống nghĩa |
| `location_code` | Location Code | Data | Vị trí thi công | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — người dùng có thể đã gõ |
| `bom_slug` | BOM Slug | Data | Nối dòng BOM | Không vào tính toán — 0 tham chiếu, không phải Link tới AL Slug Library | ẨN — dự kiến nối BOM, làm bằng Data nên không nối được |
| `planned_hours` | Planned Hours | Float | Giờ kế hoạch | Không vào tính toán — 0 tham chiếu | ẨN — không có nguồn định mức giờ |
| `actual_hours` | Actual Hours | Float | Giờ thực tế | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — đội có thể đã ghi giờ thật |
| `status` | Status | Select | Trạng thái dòng | `al_installation_order.py:18` — đếm dòng "Completed" để chuyển trạng thái lệnh | GIỮ — field duy nhất của bảng con có người đọc |
| `assigned_to` | Assigned To | Link (Employee) | Người phụ trách | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — có thể đã gán người |

**Giảm phức tạp:**
- `bom_slug` nên là Link → AL Slug Library nếu muốn nối BOM; để Data là nối sai kiểu, gõ tự do.
- `status` mặc định trống ⇒ lệnh không bao giờ tự Completed nếu người dùng không chọn; thêm default "Pending".
- Gộp `planned_hours`/`actual_hours` vào một cặp có nguồn (định mức vs chấm công) hoặc ẩn tới khi có.

---

#### AL Installation Team — doc, 5 field

**Vai trò:** Danh mục đội thi công (master data), được Sales Order trỏ tới qua custom field `al_installation_team` (`setup/custom_fields.py:52-53`) và AL Installation Order trỏ tới qua `installation_team`. **Ai tạo:** người dùng AL Site Engineer nhập tay.
**Ai dùng:** **không có consumer.** Controller `pass` (`al_installation_team.py:5-7`); 5 hit `is_active` trong input đều là `is_active` của **AL Profile System / AL Variable Dimension Mapping** (`engine/bom_orchestrator.py:698,1227`), không phải field này. Engine giá: **không đọc**.
**Tổng kết:** 5 field · 0 field vào engine giá · 1 field chỉ hiển thị · 4 field 0 tham chiếu · **đề xuất:** giữ 1, ẩn 3, đếm dữ liệu 1.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `team_name` | Team Name | Data | Tên đội | Không vào tính toán — 0 tham chiếu; là nhãn duy nhất (tên doc là hash) | GIỮ — người dùng chọn đội theo tên này |
| `team_leader` | Team Leader | Link (Employee) | Đội trưởng | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — có thể đã nhập |
| `capacity_m2_per_day` | Capacity (m2/day) | Float | Năng lực/ngày | Không vào tính toán — 0 tham chiếu, không dùng để xếp lịch | ẨN — dự kiến xếp lịch, chưa có mã |
| `is_active` | Is Active? | Check | Còn dùng? | Không vào tính toán — **không bộ lọc link nào đọc**; ô chọn đội vẫn hiện đội đã tắt | ẨN — hoặc nối `get_query` nếu muốn giữ |
| `members` | Members | Table (Employee) | Thành viên đội | Không vào tính toán — 0 tham chiếu; **`Employee` là DocType thường, không phải bảng con** | ẨN — sai kiểu, cần dựng bảng con trước khi dùng |

**Giảm phức tạp:**
- `members` trỏ vào `Employee` (không phải child table) — Frappe cần options là bảng con; dựng `AL Installation Team Member` (Link Employee + vai trò) nếu thật sự cần, ngược lại ẩn.
- `is_active` chỉ có nghĩa nếu ô chọn đội lọc theo nó — thêm `get_query` ở Sales Order và Installation Order.
- `capacity_m2_per_day` hiện là số không ai đọc; ẩn tới khi có bài toán xếp lịch.

---

#### AL Punchlist Item — bảng con, 9 field

**Vai trò:** Dòng lỗi cần sửa khi nghiệm thu (thuộc **AL Handover Acceptance** qua field `items`). **Ai tạo:** người dùng thêm dòng trên lưới biên bản nghiệm thu — không có mã nào sinh.
**Ai dùng:** **không có consumer.** Controller `pass` (`al_punchlist_item.py:5-7`); 13 hit `severity`/`status` trong input là biến cục bộ và nhãn của `quotation.js` (bảng lỗi tính giá) — trùng tên, chưa chắc. Engine giá: **không đọc**.
**Tổng kết:** 9 field · 0 field vào engine giá · 1 field chỉ hiển thị · 8 field 0 tham chiếu · **đề xuất:** giữ 1, đếm dữ liệu 8 field còn lại (không ẩn field nào trước khi đếm — đây là bản ghi lỗi thật).

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `item_description` | Description | Data | Mô tả lỗi | Không vào tính toán — 0 tham chiếu; là nội dung duy nhất của dòng | GIỮ — không có nó dòng trống nghĩa |
| `location` | Location | Data | Vị trí lỗi | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — vị trí thật người dùng gõ |
| `severity` | Severity | Select | Mức độ | Không vào tính toán — 11 hit `quotation.js:334-397` là biến `severity` của bảng lỗi giá | CHỜ-DỮ-LIỆU — có thể đã phân loại |
| `corrective_action` | Corrective Action | Text | Cách khắc phục | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — nội dung khắc phục thật |
| `due_date` | Due Date | Date | Hạn sửa | Không vào tính toán — 0 tham chiếu, không có nhắc hạn | CHỜ-DỮ-LIỆU — có thể đã đặt hạn |
| `assigned_to` | Assigned To | Link (Employee) | Người sửa | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — có thể đã gán |
| `status` | Status | Select | Trạng thái sửa | Không vào tính toán — `status` ở `api/__init__.py` là của DocType khác, trùng tên | CHỜ-DỮ-LIỆU — quy trình 4 bước đang gõ tay |
| `resolved_by` | Resolved By | Link (Employee) | Người xác nhận sửa | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — có thể đã nhập |
| `verified_by` | Verified By | Link (Employee) | Người kiểm lại | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — có thể đã nhập |

**Giảm phức tạp:**
- Chưa có mã nào đọc bảng này: `resolved_by`/`verified_by` không được điền tự động khi đổi `status`, nên nếu người dùng không gõ thì trống vĩnh viễn.
- 4 trạng thái OPEN→VERIFIED là quy trình thủ công hoàn toàn; nếu muốn dùng thật phải có nút chuyển trạng thái + kiểm người thực hiện.
- Trước khi ẩn bất kỳ field nào: đếm số dòng có dữ liệu (đây là lỗi nghiệm thu thật, không phải field trang trí).

---

#### AL Site Survey — doc, 7 field

**Vai trò:** Khảo sát công trình — đối chiếu kích thước thực tế với thiết kế. **Ai tạo:** người dùng AL Site Engineer nhập tay; không có mã nào sinh từ Sales Order dù có trường `sales_order`.
**Ai dùng:** `validate()` → `_calculate_deviations()` (`al_site_survey.py:8-38`) — đọc dung sai từ **AL Cutting Standard** (`:18-19`) rồi ghi sai lệch/dung sai/hành động cho từng dòng con. Engine giá: **không đọc**; và **không có `doc_events`** cho AL Site Survey trong `hooks.py` (khối `doc_events` ở `hooks.py:57-76` chỉ có Quotation, AL Bom Item, AL Quantity Calc Method). Tài liệu `CAU_TRUC_MODULE_VA_DOCTYPE.md:1031,1697` mô tả hook `instantiate_production_bom` khi Approved — **hàm này không tồn tại trong repo** (grep = 0).
**Tổng kết:** 7 field · 0 field vào engine giá (1 field được mã đọc: `items`) · 1 field chỉ hiển thị · 5 field 0 tham chiếu · **đề xuất:** giữ 2, đếm dữ liệu 5 field còn lại.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `survey_code` | Survey Code | Data | Mã phiếu khảo sát | Không vào tính toán — 0 tham chiếu | GIỮ — mã duy nhất, tên doc là hash |
| `project` | Project | Link | Dự án khảo sát | Không vào tính toán — 12 hit `custom_fields.py` là `project` của DocType khác | CHỜ-DỮ-LIỆU — reqd, chưa ai đọc |
| `sales_order` | Sales Order | Link | Đơn hàng liên quan | Không vào tính toán — `hooks.py:38` là `doctype_js`, trùng tên | CHỜ-DỮ-LIỆU — không bắt buộc, chưa ai đọc |
| `survey_date` | Survey Date | Date | Ngày khảo sát | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — reqd |
| `surveyor` | Surveyor | Link (Employee) | Người khảo sát | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — chưa ai đọc |
| `status` | Status | Select | Draft / Completed / Approved | Không vào tính toán — **không mã nào đọc `status`**; đặt "Approved" không kích hoạt gì | CHỜ-DỮ-LIỆU — trạng thái trang trí, đừng tin |
| `items` | Items | Table (AL Site Survey Item) | Các vị trí đo | `al_site_survey.py:14,21` — vòng lặp tính sai lệch cho từng dòng | GIỮ — nguồn duy nhất của `validate` |

**Giảm phức tạp:**
- Dung sai lấy bằng `frappe.db.get_value("AL Cutting Standard", {"applies_to": "NHOM_PROFILE"}, ...)` (`:18-19`): nếu có nhiều dòng NHOM_PROFILE, lõi Frappe lấy **dòng sửa gần nhất** và bỏ qua `profile_code` — nên dung sai có thể không phải của hệ nhôm đang dùng. Cần lọc thêm `profile_code`.
- Không có mã nối "Approved" với BOM/miễn phí sản xuất — tài liệu hứa đường này nhưng code không có; hoặc gỡ khỏi tài liệu, hoặc viết hook.
- `sales_order` có nhưng `project` mới là reqd; nếu chỉ dùng một khoá thì bỏ khoá kia.

---

#### AL Site Survey Item — bảng con, 10 field

**Vai trò:** Dòng vị trí đo của phiếu khảo sát (thuộc **AL Site Survey** qua field `items`). **Ai tạo:** người dùng thêm dòng trên lưới; 6 field kết quả do **mã cha ghi**, không phải người dùng.
**Ai dùng:** `al_site_survey.py:21-38` — vòng lặp của phiếu cha đọc 4 field đo, ghi 4 field kết quả. Engine giá: **không đọc**. Đây là bảng con **duy nhất** trong nhóm có mã đọc nhiều field.
**Tổng kết:** 10 field · 0 field vào engine giá (8 field được mã đọc/ghi) · 0 field chỉ hiển thị · 2 field 0 tham chiếu · **đề xuất:** giữ 8, đếm dữ liệu 2 field còn lại.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `location_code` | Location Code | Data | Mã vị trí đo | Không vào tính toán — 0 tham chiếu; không dùng làm khoá ghép | CHỜ-DỮ-LIỆU — người dùng thật gõ |
| `design_width_mm` | Design Width (mm) | Float | Rộng thiết kế | `al_site_survey.py:22-23` — trừ vào sai lệch rộng | GIỮ — đầu vào tính toán |
| `design_height_mm` | Design Height (mm) | Float | Cao thiết kế | `al_site_survey.py:27-28` — trừ vào sai lệch cao | GIỮ — đầu vào tính toán |
| `actual_width_mm` | Actual Width (mm) | Float | Rộng thực tế | `al_site_survey.py:22-23` — bị trừ khỏi thiết kế | GIỮ — đầu vào tính toán |
| `actual_height_mm` | Actual Height (mm) | Float | Cao thực tế | `al_site_survey.py:27-28` — bị trừ khỏi thiết kế | GIỮ — đầu vào tính toán |
| `width_deviation_mm` | Width Deviation (mm) | Float (ro) | Sai lệch rộng | `al_site_survey.py:23,25` ghi; `:33` đọc để so dung sai | GIỮ — kết quả tự tính |
| `height_deviation_mm` | Height Deviation (mm) | Float (ro) | Sai lệch cao | `al_site_survey.py:28,30` ghi; `:34` đọc để so dung sai | GIỮ — kết quả tự tính |
| `within_tolerance` | Within Tolerance? | Check (ro) | Trong dung sai? | `al_site_survey.py:32-35` ghi; `:37` đọc để đặt hành động | GIỮ — kết quả tự tính |
| `action_required` | Action Required | Select | NONE/RESIZE/REDESIGN/CHANGE_ORDER | `al_site_survey.py:37-38` — tự đặt CHANGE_ORDER khi lệch; **không read_only nên người dùng ghi đè được** | GIỮ — nhưng không có nơi nào đọc lại |
| `note` | Note | Small Text | Ghi chú vị trí | Không vào tính toán — 3 hit `bom_orchestrator.py:887,1150,2313` là `note` của dòng BOM, trùng tên | CHỜ-DỮ-LIỆU — ghi chú khảo sát thật |

**Giảm phức tạp:**
- `action_required` không read_only như 3 field kết quả khác — người dùng sửa được kết quả máy tính, và **không có báo cáo nào đọc lại** nó (không sinh Change Order dù có giá trị CHANGE_ORDER).
- `location_code` là Data không unique, không liên kết AL Slug Library — không truy vấn được "vị trí X đã đo mấy lần".
- Nếu cần nối sang sản xuất: đây là chỗ duy nhất trong nhóm gần với BOM (`design_*`/`actual_*`), nên ưu tiên nối thay vì thêm field mới.

---

#### AL Warranty Policy — doc, 5 field

**Vai trò:** Chính sách bảo hành theo loại sản phẩm. **Ai tạo:** người dùng AL BOM Manager / AL Site Engineer nhập tay. `autoname='field:policy_code'` — đây là DocType **duy nhất** trong nhóm có tên bản ghi đọc được.
**Ai dùng:** **không có consumer.** Controller `pass` (`al_warranty_policy.py:5-7`). Được Warranty Claim trỏ tới qua custom field `al_warranty_policy` (`setup/custom_fields.py:148-149`), nhưng **không mã nào tính hạn bảo hành** từ `warranty_months`; `al_covered_by_warranty` (`custom_fields.py:150-151`) là **ô Check gõ tay**, không suy ra từ chính sách. 12 hit `is_active` là của DocType khác (dòng biến của AL Profile System / AL Variable Dimension Mapping / scope binding — `engine/bom_orchestrator.py:698,1227,1277,1335`). Engine giá: **không đọc**.
**Tổng kết:** 5 field · 0 field vào engine giá · 1 field chỉ hiển thị · 4 field 0 tham chiếu · **đề xuất:** giữ 1, ẩn 1, đếm dữ liệu 3 field còn lại.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `policy_code` | Policy Code | Data | Mã chính sách | Không vào tính toán — nhưng là `autoname` nên chính là tên bản ghi | GIỮ — định danh duy nhất |
| `product_type` | Product Type | Link (AL Product Type) | Áp cho loại sản phẩm nào | Không vào tính toán — 1 hit `bom_orchestrator.py:746` là docstring nói về AL Product Type, không đọc field này | CHỜ-DỮ-LIỆU — chưa ai tra theo loại |
| `warranty_months` | Warranty (months) | Int | Số tháng bảo hành | Không vào tính toán — **0 tham chiếu**; không cộng vào ngày bàn giao để ra hạn | CHỜ-DỮ-LIỆU — nội dung chính của chính sách |
| `is_active` | Is Active? | Check | Còn hiệu lực? | Không vào tính toán — không ô chọn nào lọc theo cờ này (kể cả `al_warranty_policy` trên Warranty Claim) | ẨN — hoặc nối `get_query` nếu muốn giữ |
| `coverage_scope` | Coverage Scope | Small Text | Phạm vi bảo hành | Không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — nội dung chính sách |

**Giảm phức tạp:**
- Đây là chính sách **treo**: `warranty_start_date` có trên Handover Acceptance nhưng không nơi nào cộng `warranty_months` để ra hạn bảo hành, và Warranty Claim không tra chính sách để tự đặt `al_covered_by_warranty`.
- Nếu chưa nối: ẩn `is_active` và thêm mô tả "chính sách chỉ để tra cứu" — tránh người dùng tin hệ thống đang áp chính sách.
- Nếu nối: đặt compute hạn bảo hành ở Warranty Claim (handover date + months), và chặn chọn 2 chính sách cùng `product_type` khi cả hai active.

---

#### AL Project Warehouse Map — doc, 5 field

**Vai trò:** Ánh xạ dự án → kho tạm thời (kho công trình). **Ai tạo:** người dùng AL BOM Manager / AL Site Engineer nhập tay.
**Ai dùng:** **không có consumer.** Controller `pass` (`al_project_warehouse_map.py:5-7`); không engine, không API, không báo cáo, không test. Stock Entry và Delivery Note chỉ có custom field `al_installation_order` (`setup/custom_fields.py:114-115,120-121`) — **không truy vấn bảng ánh xạ này**. `al_review.md:498` ghi đây là "code tự viết" — thực tế chưa có code. Engine giá: **không đọc**.
**Tổng kết:** 5 field · 0 field vào engine giá · 0 field chỉ hiển thị · 5 field 0 tham chiếu · **đề xuất:** ẩn toàn bộ khỏi menu tới khi có mã đọc, sau khi đếm dữ liệu (2 field dữ liệu người dùng).

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `project` | Project | Link | Dự án | Không vào tính toán — 12 hit `custom_fields.py` là `project` của DocType khác | CHỜ-DỮ-LIỆU — nửa khoá ghép, chưa ai đọc |
| `warehouse` | Warehouse | Link | Kho tạm của dự án | Không vào tính toán — **0 tham chiếu**, không phiếu kho nào tra | CHỜ-DỮ-LIỆU — dữ liệu khai báo thật có thể đã có |
| `is_temporary` | Is Temporary? | Check | Kho tạm hay kho thật | Không vào tính toán — 0 tham chiếu | ẨN — không có mã phân biệt |
| `activation_date` | Activation Date | Date | Ngày bắt đầu dùng | Không vào tính toán — 0 tham chiếu | ẨN — không có mã so ngày |
| `deactivation_date` | Deactivation Date | Date | Ngày ngừng dùng | Không vào tính toán — 0 tham chiếu | ẨN — không có mã so ngày |

**Giảm phức tạp:**
- Cả DocType là khung rỗng: `project` + `warehouse` không có bộ lọc unique — cùng dự án có thể có nhiều kho "đang dùng" cùng lúc và không ai phân xử.
- Nếu muốn dùng thật: nối vào Stock Entry / Delivery Note (mặc định kho theo `project`), khi đó 3 field ngày + `is_temporary` mới có nghĩa.
- Nếu không: ẩn khỏi menu trước khi người dùng khai hàng loạt — dữ liệu khai vào hiện không ảnh hưởng bất kỳ phiếu kho nào.

---

##### Tổng hợp nhóm

| DocType | Số field | Vào engine | Chỉ cấu hình/hiển thị | 0 tham chiếu | Đề xuất |
|---|---|---|---|---|---|
| AL Change Order | 15 | 3 | 2 | 10 | Giữ 4 · ẩn 3 · đếm dữ liệu 8; **bật hoặc bỏ Workflow** |
| AL Handover Acceptance | 11 | 4 | 1 | 6 | Giữ 5 · đếm dữ liệu 6; chặn đóng khi còn punchlist |
| AL Installation Cost Actual | 9 | 0 | 0 | 9 | **Không có consumer** — nối vào giá thành hoặc ẩn khỏi menu |
| AL Installation Order | 10 | 6 | 1 | 3 | Giữ 7 · đếm dữ liệu 3; chốt 1 nguồn ghi `status` |
| AL Installation Progress | 8 | 2 | 0 | 6 | Giữ 2 · ẩn 1 · đếm dữ liệu 5; chặn `progress_pct` ngoài 0–100 |
| AL Installation Task | 7 | 1 | 1 | 5 | Giữ 2 · ẩn 2 · đếm dữ liệu 3; `bom_slug` đổi sang Link |
| AL Installation Team | 5 | 0 | 1 | 4 | Giữ 1 · đếm dữ liệu 1 · **`members` sai kiểu, ẩn** |
| AL Punchlist Item | 9 | 0 | 1 | 8 | Giữ 1 · đếm dữ liệu 8; cả bảng không có mã đọc |
| AL Site Survey | 7 | 1 | 1 | 5 | Giữ 2 · đếm dữ liệu 5; **"Approved" không kích hoạt gì** |
| AL Site Survey Item | 10 | 8 | 0 | 2 | Giữ 8 · đếm dữ liệu 2; `action_required` nên read_only |
| AL Warranty Policy | 5 | 0 | 1 | 4 | Giữ 1 · ẩn 1 · đếm dữ liệu 3; chính sách đang treo |
| AL Project Warehouse Map | 5 | 0 | 0 | 5 | **Không có consumer** — ẩn khỏi menu hoặc nối vào phiếu kho |
| **Tổng** | **101** | **25** | **9** | **67** | Giữ 33 · ẩn 15 · đếm dữ liệu 53 |

> *Cột "Vào engine" ở nhóm này đếm **field có mã đọc/ghi để tính hoặc để quyết định trạng thái** (validate, before_save, after_insert, ghi chéo DocType). **Không field nào** trong 12 DocType đi vào engine giá B0–B7 — con số 25 không phải "field vào giá thành".*

**Ba việc nên làm trước trong nhóm này:**

1. **Chốt số phận Workflow AL Change Order.** `setup/install_workflows.py:76-105` khai đủ 5 trạng thái + 6 chuyển tiếp, nhưng lệnh cài bị comment ở **cả hai** chỗ (`hooks.py:191` trong `_after_install`, `hooks.py:235` trong `_after_migrate`). Trên site chưa chạy tay, `workflow_state` là Select trơ: đặt "Approved" chỉ bị `validate()` chặn, không có nút duyệt, không có khoá theo vai. Hoặc bật, hoặc gỡ cấu hình để khỏi có hai nguồn sự thật.

2. **Quyết "treo hay nối" cho 3 DocType 0 consumer**: AL Installation Cost Actual (tiền thi công), AL Warranty Policy (hạn bảo hành), AL Project Warehouse Map (kho dự án). Cả ba đang cho người dùng nhập dữ liệu mà **không mã nào đọc** — nguy hiểm nhất là Cost Actual: số tiền thật rơi vào chỗ không vào giá thành, và Warranty Policy: `al_covered_by_warranty` trên Warranty Claim là ô gõ tay (`setup/custom_fields.py:150`), người dùng dễ tưởng hệ thống tự xét theo chính sách.

3. **Đếm dữ liệu trước khi ẩn/xoá 53 field CHỜ-DỮ-LIỆU**, và sửa `AL Installation Team.members` (`Table` trỏ `Employee` — không phải bảng con, không thể dùng như thiết kế). Đếm bằng một truy vấn `count(non-null)` cho từng field; field 0 bản ghi có dữ liệu thì ẩn được ngay, field có dữ liệu thì phải quyết "giữ hay chuyển sang chỗ tiêu thụ" trước.

**Ba thứ KHÔNG nên đụng:**

1. **`AL Site Survey` + `AL Site Survey Item` (8 field tính toán).** Đây là mã thật duy nhất của nhóm: `al_site_survey.py:21-38` tính sai lệch, so dung sai, đặt hành động. Sửa công thức hay đổi kiểu field (`design_*`/`actual_*`) là làm lệch dữ liệu khảo sát đã lưu.

2. **Ba chỗ cùng ghi trạng thái lệnh thi công** — `al_installation_order.py:16-26` (theo Tasks), `al_installation_progress.py:12-20` (theo %), `al_handover_acceptance.py:14-21` (theo nghiệm thu). Sửa một chỗ mà không xem hai chỗ kia sẽ tạo trạng thái mâu thuẫn, khó truy ngược ai ghi.

3. **`customer_approval` / `internal_approval` (permlevel 1) và override ở `setup/install_roles.py:166-179, 272-281`.** Hai ô này là cổng duy nhất chặn tự duyệt phát sinh; bỏ `permlevel` hoặc gộp quyền vào permlevel 0 là mở đường cho người tạo tự tick duyệt.

> **Lưu ý về tài liệu hiện có:** `CAU_TRUC_MODULE_VA_DOCTYPE.md:1031,1697` và `gia-ban-gia-dinh-muc-thuc-te.md:84` mô tả các đường chạy (khảo sát → BOM, chi phí thi công → giá thành) **chưa có mã trong repo**. Khi cập nhật tài liệu, phải ghi rõ đây là kế hoạch, không phải tính năng đang chạy.

---

### 8.4 AL Manufacturing · Buying — 11 DocType

> Phạm vi: `AL Cutting Plan Aluminum`, `AL Cutting Plan Glass`, `AL Cutting Plan Item`,
> `AL Glass Cutting Item`, `AL Cutting Standard`, `AL Production Order Bridge` (AL Manufacturing)
> và `AL Cost Variance`, `AL Material Plan`, `AL Material Plan Item`,
> `AL Supplier Price List`, `AL Supplier Price List Item` (AL Buying).
>
> **Cách đọc file này**
> - Đường dẫn mã tính từ gốc app: `/home/nxc/myfrappe/apps/alumglass/alumglass/`
>   (ví dụ `engine/bom_orchestrator.py` = `/home/nxc/myfrappe/apps/alumglass/alumglass/engine/bom_orchestrator.py`).
>   Tệp tài liệu ở **gốc repo** (`CAU_TRUC_MODULE_VA_DOCTYPE.md`, `alumglass_workspace_sidebar.json`)
>   ghi đúng tên tệp, không tính theo gốc app.
> - Cột **Nhãn** là nhãn **đang hiện trên form** (toàn bộ nhóm này đang để tiếng Anh); nghĩa tiếng Việt ở cột Mục đích.
> - **Đếm trong "Tổng kết"** là đếm **tham chiếu trong mã**, không phải đánh giá:
>   `a` = có mã đọc field để tính ra số khác (kể cả `validate`, kể cả engine B0–B7) ·
>   `b` = có mã chỉ để sinh mã / đổi trạng thái / hiển thị ·
>   `c` = **0 dòng mã nào** đọc hoặc ghi.
> - Một field có thể `c` (0 tham chiếu) mà vẫn **GIỮ**, nếu người dùng buộc phải thấy nó.
> - Cả 11 DocType đều `autoname=None`, `title_field=None` ⇒ bản ghi mang **tên hash**, ô liên kết
>   chỉ hiện chuỗi hash. Đây là lỗi hiển thị chung của cả nhóm, không nhắc lại ở từng field.

---

##### AL Manufacturing

#### AL Cutting Plan Aluminum — doc, 12 field

**Vai trò:** Bảng ghi kế hoạch cắt thanh nhôm (1 chiều) cho một phiên bản BOM. Người lập kế hoạch sản xuất mở form và nhập tay; hiện **không có bộ phận mã nào sinh ra bản ghi**.
**Ai dùng:** **không có consumer**. Controller rỗng (`al_manufacturing/doctype/al_cutting_plan_aluminum/al_cutting_plan_aluminum.py:5-7` chỉ `pass`), JS rỗng (`.../al_cutting_plan_aluminum.js:4-11` là khung trống), không phase B0–B7 nào đọc, không API nào đọc.
**Tổng kết:** 12 field · **0** field vào engine tính toán · **0** field chỉ cấu hình/hiển thị · **12** field không có tham chiếu · **đề xuất:** giữ khung form làm phiếu ghi tay, nhưng **ẩn 3 field tổng** cho tới khi có thuật toán.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `plan_code` | Plan Code | Data (reqd, in_list_view) | Mã kế hoạch cắt do người dùng gõ | không vào tính toán — 2 hit `al_buying/doctype/al_material_plan/al_material_plan.py:22,24` là `plan_code` của **AL Material Plan**, không phải field này | GIỮ — mã người dùng nhập, bắt buộc, hiện trên danh sách |
| `bom_version` | BOM Version | Link → AL BOM Version (reqd) | Phiên bản BOM nguồn của kế hoạch | không vào tính toán — `engine/bom_orchestrator.py:322-344,820` đọc `Quotation Item.al_bom_version` / `self.bom_version`, trùng tên | GIỮ — đầu vào dự kiến của thuật toán cắt |
| `project` | Project | Link → Project | Dự án/công trình | không vào tính toán — `setup/custom_fields.py:9-16` là field `project` của **Quotation**, không đọc field này | GIỮ — khoá nhóm/lọc của người dùng |
| `sales_order` | Sales Order | Link → Sales Order | Đơn bán phát sinh nhu cầu | không vào tính toán — hit `hooks.py:38` là khoá `"Sales Order"` trong `doctype_js`, trùng tên | GIỮ — truy vết đơn, người dùng cần thấy |
| `status` | Status | Select Draft/In Progress/Completed | Vòng đời kế hoạch | không vào tính toán — `api/__init__.py:225,278,290` là khoá `"status"` của phản hồi job BOM, trùng tên | GIỮ — trạng thái tự giải thích, người dùng đổi tay |
| `stock_bar_length_mm` | Stock Bar Length (mm) | Float (reqd) | Chiều dài phôi chuẩn (6000 mm) | không vào tính toán — `formula_builder/templates.py:252,254,256` chỉ là **công thức mẫu** gán `stock_bar_length_mm = stock_bar_len`; không DocType nào đọc | GIỮ — tham số cắt người dùng nhập |
| `saw_kerf_mm` | Saw Kerf (mm) | Float (reqd) | Hao hụt do lưỡi cưa | không vào tính toán — `formula_builder/templates.py:253,254,257` là công thức mẫu, không đọc DocType | GIỮ — tham số cắt người dùng nhập |
| `min_offcut_reusable_mm` | Min Offcut Reusable (mm) | Float | Ngưỡng đoạn dư còn dùng lại được | không vào tính toán — 0 tham chiếu | GIỮ — tham số phân loại phế liệu, người dùng nhập |
| `total_bars_required` | Total Bars Required | Int | Tổng số thanh phôi cần | không vào tính toán — 0 tham chiếu; **không có mã nào tính ra số này** | ẨN — số máy phải tính; gõ tay là dữ liệu sai |
| `total_waste_mm` | Total Waste (mm) | Float | Tổng hao hụt (mm) | không vào tính toán — 0 tham chiếu; không có mã tính | ẨN — kết quả phải sinh từ bảng cắt |
| `waste_pct` | Waste (%) | Float | % hao hụt | không vào tính toán — `formula_builder/templates.py:272` và `formula_builder/examples/03_du_toan.py:160` là `waste_pct` của **công thức kính**, trùng tên | ẨN — kết quả phải sinh, hiện gõ tay |
| `items` | Items | Table → AL Cutting Plan Item (reqd) | Danh sách thanh cắt | không vào tính toán — các hit `engine/bom_orchestrator.py:256`… là thuộc tính `items` của engine (`self.bom_items`), không đọc bảng này | GIỮ — chỗ chứa kết quả cắt, người dùng cần thấy |

**Giảm phức tạp:**
- **Không có thuật toán cắt.** Toàn bộ phần "tính" của DocType này chỉ là 9 dòng công thức mẫu ở `formula_builder/templates.py:251-261` (`bars_needed = ceil(total_cut_length_mm / (stock_bar_length_mm − saw_kerf_mm))`) — và **không DocType nào gọi**. Đó cũng chỉ là phép chia tổng chiều dài, **không phải thuật toán xếp thanh**: nó bỏ qua việc mỗi thanh chỉ chứa được một số đoạn vừa chiều dài.
- Ẩn 3 field tổng (`total_bars_required`, `total_waste_mm`, `waste_pct`) khỏi form ngay: để trống thì vô nghĩa, gõ tay thì ra số không khớp bảng cắt.
- `plan_code` + `name` là **hai mã cho cùng một thứ**: `name` là hash, `plan_code` người dùng gõ. Đặt `title_field = plan_code` hoặc `autoname` để ô liên kết hiện mã đọc được.
- Chưa có mục nào trong menu trái (`alumglass_workspace_sidebar.json` không có `AL Cutting Plan Aluminum`) ⇒ người dùng không mở được từ menu, chỉ mở được bằng URL.

#### AL Cutting Plan Glass — doc, 10 field

**Vai trò:** Bảng ghi kế hoạch cắt kính (2 chiều) từ tấm jumbo cho một phiên bản BOM. Người lập kế hoạch nhập tay; **không mã nào sinh bản ghi**.
**Ai dùng:** **không có consumer**. Controller rỗng (`al_manufacturing/doctype/al_cutting_plan_glass/al_cutting_plan_glass.py:5-7` = `pass`), JS rỗng, không phase B0–B7 nào đọc.
**Tổng kết:** 10 field · **0** vào engine · **0** chỉ cấu hình/hiển thị · **10** không có tham chiếu · **đề xuất:** giữ khung phiếu ghi tay, ẩn 3 field tổng, tách `jumbo_sheet_size` thành 2 số.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `plan_code` | Plan Code | Data (reqd, in_list_view) | Mã kế hoạch cắt kính | không vào tính toán — hit là `plan_code` của AL Material Plan (`al_material_plan.py:22,24`), trùng tên | GIỮ — mã người dùng nhập, hiện trên danh sách |
| `bom_version` | BOM Version | Link → AL BOM Version (reqd) | Phiên bản BOM nguồn | không vào tính toán — `engine/bom_orchestrator.py:322-344` đọc `Quotation Item.al_bom_version`, trùng tên | GIỮ — đầu vào dự kiến của thuật toán |
| `project` | Project | Link → Project | Dự án/công trình | không vào tính toán — `setup/custom_fields.py:9-16` là field của Quotation | GIỮ — khoá nhóm/lọc |
| `status` | Status | Select Draft/In Progress/Completed | Vòng đời kế hoạch | không vào tính toán — `api/__init__.py:225`… là khoá `"status"` của phản hồi job, trùng tên | GIỮ — trạng thái người dùng đổi tay |
| `jumbo_sheet_size` | Jumbo Sheet Size | Data (reqd) | Khổ tấm jumbo, dạng chuỗi `"3210x2250"` | không vào tính toán — 0 tham chiếu | GIỮ — đầu vào bắt buộc; **nên tách `jumbo_w_mm` + `jumbo_h_mm`** |
| `edge_trim_mm` | Edge Trim (mm) | Float (reqd) | Trừ hao mép tấm | không vào tính toán — `formula_builder/templates.py:266,295` là công thức mẫu + tham số mặc định, không đọc DocType | GIỮ — tham số cắt người dùng nhập |
| `total_sheets_required` | Total Sheets Required | Int | Tổng số tấm cần | không vào tính toán — 0 tham chiếu; không có mã tính | ẨN — kết quả phải do máy tính |
| `total_waste_m2` | Total Waste (m2) | Float | Hao hụt (m²) | không vào tính toán — 0 tham chiếu; không có mã tính | ẨN — kết quả phải do máy tính |
| `waste_pct` | Waste (%) | Float | % hao hụt | không vào tính toán — `formula_builder/templates.py:272` là tên công thức mẫu, không đọc DocType | ẨN — kết quả phải do máy tính |
| `items` | Items | Table → AL Glass Cutting Item (reqd) | Danh sách tấm cắt | không vào tính toán — hit là `self.bom_items` của engine (`engine/bom_orchestrator.py:256`), không đọc bảng này | GIỮ — chỗ chứa kết quả cắt |

**Giảm phức tạp:**
- **Không có thuật toán cắt kính.** Công thức mẫu ở `formula_builder/templates.py:263-273` cần **hai số** `jumbo_w_mm` và `jumbo_h_mm`, nhưng DocType chỉ có **một chuỗi** `jumbo_sheet_size` ⇒ muốn nối vào là phải parse chuỗi. Đây là lý do cụ thể phải tách khổ tấm thành 2 field số.
- Công thức mẫu cũng chỉ ước lượng `estimated_sheets = max(1, ceil(tổng_m2 / diện tích_tấm))` — **không xếp được hình chữ nhật lên tấm**, nên `total_waste_m2` tính theo nó là cận dưới, không phải phế liệu thật.
- Ẩn 3 field tổng khỏi form; tách `jumbo_sheet_size`; đặt `title_field = plan_code`.

#### AL Cutting Plan Item — bảng con, 11 field

**Vai trò:** Từng đoạn nhôm cắt ra từ một thanh phôi — thuộc **AL Cutting Plan Aluminum** qua field `items`.
**Ai dùng:** **không có consumer**. Engine không đọc bảng này; bảng chỉ tồn tại để chứa kết quả của một thuật toán chưa viết.
**Tổng kết:** 11 field · **0** vào engine · **0** chỉ cấu hình/hiển thị · **11** không có tham chiếu · **đề xuất:** giữ 3 field đo đạc để ghi tay, ẩn 5 field bố trí, 3 field chờ dữ liệu.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `bar_number` | Bar Number | Int (in_list_view) | Số thứ tự thanh phôi chứa đoạn này | không vào tính toán — 0 tham chiếu | ẨN — kết quả xếp thanh, máy phải sinh |
| `slug` | Slug | Data (in_list_view) | Mã dòng BOM mà đoạn này lấy từ đó | không vào tính toán — `engine/bom_orchestrator.py:276` là comment về `slug` của dòng BOM, không đọc bảng này | GIỮ — mối nối về BOM, người dùng cần thấy |
| `item_code` | Item Code | Link → Item (in_list_view) | Mã nhôm thanh | không vào tính toán — `fb_handlers.py:97`… đọc `item_code` của dòng BOM, trùng tên | GIỮ — vật tư của dòng, không có thì dòng vô nghĩa |
| `cut_length_mm` | Cut Length (mm) | Float (in_list_view) | Chiều dài đoạn cần cắt | không vào tính toán — 0 tham chiếu | GIỮ — số đo cốt lõi, người dùng nhập tay được |
| `angle_start` | Angle Start (deg) | Float | Góc cắt đầu (0/45/90°) | không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — chưa rõ có dùng góc thật, đếm dữ liệu trước |
| `angle_end` | Angle End (deg) | Float | Góc cắt cuối | không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — cùng lý do `angle_start` |
| `position_from_mm` | Position From (mm) | Float | Vị trí bắt đầu trên thanh | không vào tính toán — 0 tham chiếu | ẨN — kết quả bố trí, máy phải sinh |
| `position_to_mm` | Position To (mm) | Float | Vị trí kết thúc trên thanh | không vào tính toán — 0 tham chiếu | ẨN — kết quả bố trí, máy phải sinh |
| `offcut_length_mm` | Offcut Length (mm) | Float | Chiều dài đoạn dư còn lại | không vào tính toán — 0 tham chiếu | ẨN — kết quả trừ chiều dài, máy phải sinh |
| `offcut_reusable` | Offcut Reusable? | Check (default 0) | Đoạn dư có dùng lại được không | không vào tính toán — 0 tham chiếu | ẨN — phải suy từ `min_offcut_reusable_mm`, không cho tích tay |
| `offcut_serial_no` | Offcut Serial No | Link → Serial No | Serial của đoạn dư nhập lại kho | không vào tính toán — 0 tham chiếu; không có mã sinh Serial No | CHỜ-DỮ-LIỆU — chưa có luồng sinh Serial No |

**Giảm phức tạp:**
- Bảng có 11 cột nhưng **không cột nào được mã đọc** — đây là bảng chờ thuật toán. Ẩn 5 cột kết quả (`bar_number`, `position_from_mm`, `position_to_mm`, `offcut_length_mm`, `offcut_reusable`) để người dùng không gõ tay số máy lẽ ra phải tính; 3 cột `angle_*` và `offcut_serial_no` chờ đếm dữ liệu rồi quyết.
- `slug` là **Data tự do**, trong khi `AL Slug Library` là DocType riêng ⇒ gõ sai chính tả không ai bắt. Nên đổi sang Link → AL Slug Library nếu giữ.
- `offcut_reusable` và `offcut_serial_no` chỉ có nghĩa khi đã có luồng nhập lại kho của đoạn dư; hiện chưa có ⇒ đừng để trống trên form.

#### AL Glass Cutting Item — bảng con, 10 field

**Vai trò:** Từng tấm kính cắt ra từ một tấm jumbo — thuộc **AL Cutting Plan Glass** qua field `items`.
**Ai dùng:** **không có consumer**. Không engine/API nào đọc; bảng chờ thuật toán xếp tấm.
**Tổng kết:** 10 field · **0** vào engine · **0** chỉ cấu hình/hiển thị · **10** không có tham chiếu · **đề xuất:** giữ 4 field đo, ẩn 6 field bố trí/phế liệu.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `sheet_number` | Sheet Number | Int (in_list_view) | Số thứ tự tấm jumbo chứa miếng này | không vào tính toán — 0 tham chiếu | ẨN — kết quả xếp tấm, máy phải sinh |
| `slug` | Slug | Data (in_list_view) | Mã dòng BOM nguồn | không vào tính toán — `engine/bom_orchestrator.py:276` là comment về `slug` dòng BOM, không đọc bảng này | GIỮ — mối nối về BOM |
| `item_code` | Item Code | Link → Item (in_list_view) | Mã loại kính | không vào tính toán — `fb_handlers.py:97`… là dòng BOM, trùng tên | GIỮ — vật tư của dòng |
| `cut_width_mm` | Cut Width (mm) | Float (in_list_view) | Chiều rộng miếng cắt | không vào tính toán — 0 tham chiếu | GIỮ — số đo cốt lõi, nhập tay được |
| `cut_height_mm` | Cut Height (mm) | Float (in_list_view) | Chiều cao miếng cắt | không vào tính toán — 0 tham chiếu | GIỮ — số đo cốt lõi, nhập tay được |
| `pos_x_mm` | Position X (mm) | Float | Toạ độ X trên tấm | không vào tính toán — 0 tham chiếu | ẨN — kết quả bố trí, máy phải sinh |
| `pos_y_mm` | Position Y (mm) | Float | Toạ độ Y trên tấm | không vào tính toán — 0 tham chiếu | ẨN — kết quả bố trí, máy phải sinh |
| `offcut_width_mm` | Offcut Width (mm) | Float | Chiều rộng miếng dư | không vào tính toán — 0 tham chiếu | ẨN — kết quả cắt, máy phải sinh |
| `offcut_height_mm` | Offcut Height (mm) | Float | Chiều cao miếng dư | không vào tính toán — 0 tham chiếu | ẨN — kết quả cắt, máy phải sinh |
| `offcut_reusable` | Offcut Reusable? | Check (default 0) | Miếng dư có dùng lại được | không vào tính toán — 0 tham chiếu | ẨN — phải suy từ ngưỡng, không tích tay |

**Giảm phức tạp:**
- Cùng bệnh với bảng nhôm: 10 cột, **0 cột có mã đọc**. Ẩn 6 cột kết quả (`sheet_number`, `pos_*`, `offcut_*`).
- Đổi `slug` sang Link → AL Slug Library để gõ đúng.
- Nếu chỉ muốn người dùng ghi tay "cắt miếng gì, khổ bao nhiêu", giữ đúng 4 cột (`slug`, `item_code`, `cut_width_mm`, `cut_height_mm`) — đủ để dùng như phiếu cắt giấy.

#### AL Cutting Standard — doc, 9 field

**Vai trò:** Danh mục **quy cách cắt chuẩn** cho nhôm (profile) và kính — nơi đặt chiều dài phôi, hao lưỡi cưa, trừ mép, ngưỡng phế liệu dùng lại. Do quản lý sản xuất khai.
**Ai dùng:** chỉ **một** consumer thật: `al_construction/doctype/al_site_survey/al_site_survey.py:18-19` đọc `survey_tolerance_mm` với điều kiện `applies_to = "NHOM_PROFILE"` để tính sai lệch khảo sát. Không phase B0–B7 nào đọc.
**Tổng kết:** 9 field · **2** field vào tính toán · **0** field chỉ cấu hình/hiển thị · **7** field không có tham chiếu · **đề xuất:** giữ 2 field khảo sát, ẩn 7 field cắt cho tới khi có thuật toán đọc chúng.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `applies_to` | Applies To | Select NHOM_PROFILE/KINH (reqd) | Bản ghi này cho nhôm hay cho kính | `al_construction/doctype/al_site_survey/al_site_survey.py:18-19` — dùng làm khoá lọc khi tra dung sai khảo sát | GIỮ — có mã đọc thật, quyết định nửa form |
| `profile_code` | Profile Code | Data (depends_on NHOM_PROFILE) | Mã hệ profile nhôm áp dụng | không vào tính toán — `patches/v28_14/seed_bom_profile.py:108` là `profile_code` của **AL Variable Profile**, trùng tên | ẨN — 0 đọc; bật lại khi có thuật toán cắt |
| `item_group` | Item Group | Link → Item Group (depends_on KINH) | Nhóm kính áp dụng | không vào tính toán — `setup/custom_fields.py:62` và `api/__init__.py:1463,1494` là `item_group` của **Item**, trùng tên | ẨN — 0 đọc; bật lại khi có thuật toán cắt |
| `stock_bar_length_mm` | Stock Bar Length (mm) | Float (depends_on NHOM_PROFILE) | Chiều dài phôi nhôm chuẩn | không vào tính toán — `formula_builder/templates.py:252-256` là công thức mẫu, không DocType nào đọc | ẨN — 0 đọc; hiện là bản sao của field trên kế hoạch cắt |
| `saw_kerf_mm` | Saw Kerf (mm) | Float (depends_on NHOM_PROFILE) | Hao lưỡi cưa | không vào tính toán — `formula_builder/templates.py:253-257` là công thức mẫu | ẨN — 0 đọc; bản sao của kế hoạch cắt |
| `jumbo_sheet_size` | Jumbo Sheet Size | Data (depends_on KINH) | Khổ tấm kính jumbo | không vào tính toán — 0 tham chiếu | ẨN — 0 đọc; chuỗi tự do, không parse được |
| `edge_trim_mm` | Edge Trim (mm) | Float (depends_on KINH) | Trừ mép tấm kính | không vào tính toán — `formula_builder/templates.py:266,295` + `examples/03_du_toan.py:151` là công thức mẫu/giá trị demo | ẨN — 0 đọc; bản sao của kế hoạch cắt |
| `min_offcut_reusable_mm` | Min Offcut Reusable (mm) | Float | Ngưỡng đoạn dư dùng lại được | không vào tính toán — 0 tham chiếu | ẨN — 0 đọc; trùng ý với field trên kế hoạch cắt |
| `survey_tolerance_mm` | Survey Tolerance (mm) | Float | Sai lệch tối đa cho phép khi khảo sát | `al_construction/doctype/al_site_survey/al_site_survey.py:18-19` — đọc làm trần sai lệch; mặc định 10.0 nếu không có bản ghi | GIỮ — có mã đọc thật, ảnh hưởng quyết định đổi đơn |

**Giảm phức tạp:**
- **Đang có 2 bản của cùng bộ tham số cắt**: ở đây và trên `AL Cutting Plan Aluminum/Glass`. **Không bản nào được đọc.** Chọn một: khuyến nghị giữ **ở đây** làm nguồn cấu hình, cho kế hoạch cắt đọc mặc định từ đây thay vì bắt người dùng gõ lại.
- 7 field ẩn phải ẩn **đồng thời** với việc giữ 2 field khảo sát — đừng xoá, vì `applies_to` + `survey_tolerance_mm` đang chạy thật.
- Đặt `title_field` (ví dụ nhãn `applies_to + profile_code`) để ô liên kết không hiện hash.
- `jumbo_sheet_size` dạng chuỗi `3210x2250` không dùng được cho bất kỳ phép tính nào — nếu giữ thì tách thành 2 số.

#### AL Production Order Bridge — doc, 7 field

**Vai trò:** Dự kiến nối một phiên bản BOM với lệnh sản xuất (Work Order) và 2 kế hoạch cắt. **Đã bị đánh dấu bỏ ở v28.9** (`CAU_TRUC_MODULE_VA_DOCTYPE.md:943,1507`: thay bằng core BOM instantiated), nhưng mã và menu vẫn còn.
**Ai dùng:** **không có consumer**. Controller rỗng (`al_manufacturing/doctype/al_production_order_bridge/al_production_order_bridge.py:5-7` = `pass`), JS rỗng. Chỉ tồn tại dưới dạng **đích của 2 field liên kết**: `setup/custom_fields.py:97-98` (Work Order) và `:125-126` (Quality Inspection) — mà cũng không mã nào đọc 2 field đó.
**Tổng kết:** 7 field · **0** vào engine · **0** chỉ cấu hình/hiển thị · **7** không có tham chiếu · **đề xuất:** đếm bản ghi rồi **bỏ cả DocType** cùng 2 custom field trỏ vào nó.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `al_bom_version` | BOM Version | Link → AL BOM Version (reqd, in_list_view) | Phiên bản BOM nguồn của lệnh sản xuất | không vào tính toán — `engine/bom_orchestrator.py:318` đọc `Quotation Item.al_bom_version`; `engine/engine_cache.py:17` chỉ nhắc trong docstring | CHỜ-DỮ-LIỆU — đếm bản ghi trước; cả DocType đã có đường thay thế |
| `work_order` | Work Order | Link → Work Order (in_list_view) | Lệnh sản xuất tương ứng | không vào tính toán — 0 tham chiếu (chiều ngược lại: Work Order trỏ về đây, không ai đọc) | CHỜ-DỮ-LIỆU — đếm bản ghi trước khi xoá |
| `status` | Status | Select Draft/In Progress/Completed | Vòng đời cầu nối | không vào tính toán — `api/__init__.py:225`… là khoá `"status"` của phản hồi job, trùng tên | CHỜ-DỮ-LIỆU — đếm bản ghi trước khi xoá |
| `start_date` | Start Date | Datetime | Bắt đầu sản xuất | không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — đếm bản ghi trước khi xoá |
| `end_date` | End Date | Datetime | Kết thúc sản xuất | không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — đếm bản ghi trước khi xoá |
| `al_cutting_plan_aluminum` | Cutting Plan Aluminum | Link → AL Cutting Plan Aluminum | Kế hoạch cắt nhôm của lệnh | không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — đếm bản ghi trước khi xoá |
| `al_cutting_plan_glass` | Cutting Plan Glass | Link → AL Cutting Plan Glass | Kế hoạch cắt kính của lệnh | không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — đếm bản ghi trước khi xoá |

**Giảm phức tạp:**
- Quyết định đã có trong tài liệu kiến trúc: **BỎ** (`CAU_TRUC_MODULE_VA_DOCTYPE.md:943,1027,1489`). Việc còn lại là **đếm bản ghi** rồi xoá — đừng để DocType "đã tuyên bố bỏ" tiếp tục hiện trong menu.
- Trước khi xoá phải gỡ 2 custom field trỏ vào nó (`setup/custom_fields.py:97-98`, `:125-126`), nếu không form Work Order / Quality Inspection sẽ trỏ vào DocType không còn.
- Đừng thay bằng cách viết thêm mã vào đây — đường thay thế đã chốt là core BOM instantiated.

---

##### AL Buying

#### AL Cost Variance — doc, 8 field

**Vai trò:** Dự kiến đối chiếu **dự toán vs thực tế** theo dự án và nhóm chi phí. Người tạo dự kiến: kế toán/quản lý dự án. Hiện **không mã nào tạo bản ghi**.
**Ai dùng:** **không có consumer**. Controller rỗng (`al_buying/doctype/al_cost_variance/al_cost_variance.py:5-7` = `pass`), JS rỗng. Không phải phase B0–B7, không API. Tài liệu kiến trúc nói sẽ nối core Budget + report Budget Variance (`CAU_TRUC_MODULE_VA_DOCTYPE.md:861`) nhưng **chưa có mã**.
**Tổng kết:** 8 field · **0** vào engine · **0** chỉ cấu hình/hiển thị · **8** không có tham chiếu · **đề xuất:** giữ 2 field khoá, ẩn 3 field chênh lệch (máy phải tính), 3 field còn lại đếm dữ liệu.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `project` | Project | Link → Project (in_list_view) | Dự án được đối chiếu | không vào tính toán — `setup/custom_fields.py:9-16` là `project` của Quotation, trùng tên | GIỮ — khoá nhóm của mọi báo cáo chênh lệch |
| `cost_bucket` | Cost Bucket | Link → AL Cost Bucket (in_list_view) | Nhóm chi phí (nhôm/kính/nhân công/OH) | không vào tính toán — `engine/bom_orchestrator.py:871,2299,2349,2352` là `cost_bucket` của dòng BOM / docstring B5, không đọc field này | GIỮ — khoá nhóm, cần để so với bảng giá thành |
| `period_from` | Period From | Date | Kỳ bắt đầu lấy số thực tế | không vào tính toán — 0 tham chiếu; không có mã truy vấn GL theo kỳ | CHỜ-DỮ-LIỆU — 0 đọc; đếm bản ghi trước khi xoá |
| `period_to` | Period To | Date | Kỳ kết thúc | không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — 0 đọc; đếm bản ghi trước khi xoá |
| `estimated_amount` | Estimated Amount | Currency | Chi phí dự toán của nhóm | không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — 0 đọc; chưa nối dự toán từ ConfigSnapshot |
| `actual_amount` | Actual Amount (from GL) | Currency | Chi phí thực tế | không vào tính toán — 0 tham chiếu; **nhãn hứa "from GL" nhưng không có dòng mã nào đọc GL** | ẨN — nhãn hứa số máy lấy, thực tế bắt gõ tay |
| `variance_amount` | Variance Amount | Currency | Chênh lệch tuyệt đối | không vào tính toán — 0 tham chiếu, không có phép trừ nào | ẨN — số máy phải tính; gõ tay là sai |
| `variance_pct` | Variance (%) | Float | Chênh lệch % | không vào tính toán — 0 tham chiếu | ẨN — số máy phải tính; gõ tay là sai |

**Giảm phức tạp:**
- Đây là DocType **chỉ có form, không có máy**. Có 3 field mà bản chất là **kết quả** (`variance_amount`, `variance_pct`, `actual_amount`) đang để người dùng gõ tay ⇒ ẩn ngay, đừng để phát sinh dữ liệu sai không kiểm được.
- Trước khi nối core Budget: xác định ai ghi `estimated_amount` (từ `ConfigSnapshot` hay từ Budget) và ai ghi `actual_amount` (GL theo `project` + `cost_bucket` + kỳ). Chưa chốt 2 nguồn này thì đừng mở form.
- Đặt `title_field`/`autoname` để ô liên kết hiện "Dự án · Nhóm · Kỳ" thay vì hash.

#### AL Material Plan — doc, 5 field

**Vai trò:** Dự kiến tổng hợp nhu cầu vật tư từ nhiều đơn bán và tính thiếu hụt. Người tạo dự kiến: mua hàng. **Tài liệu kiến trúc đã đánh dấu BỎ ở v28.9** (`CAU_TRUC_MODULE_VA_DOCTYPE.md:812,1507`: thay bằng core Material Request), nhưng mã và menu vẫn còn.
**Ai dùng:** chỉ **chính nó**: `validate()` gọi `_calculate_shortfalls()` để tính thiếu hụt (`al_buying/doctype/al_material_plan/al_material_plan.py:9-19`). Hàm whitelisted `aggregate_requirements` (`:27-45`) **không có ai gọi** (không JS, không API, không patch nào gọi tên). Không phase B0–B7.
**Tổng kết:** 5 field · **1** field vào tính toán · **1** field chỉ cấu hình/hiển thị · **3** field không có tham chiếu · **đề xuất:** chốt sống/chết; nếu giữ thì `sales_orders` phải sửa kiểu, nếu bỏ thì xoá cùng Item.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `plan_code` | Plan Code | Data (reqd, in_list_view) | Mã kế hoạch, tự sinh dạng `MP-.#####` | `al_buying/doctype/al_material_plan/al_material_plan.py:21-24` — `before_save` sinh mã nếu trống; **không dùng để tính gì** | GIỮ — mã người dùng đọc; đặt `title_field` để hiện thay hash |
| `plan_date` | Plan Date | Date (reqd, in_list_view) | Ngày lập kế hoạch | không vào tính toán — 0 tham chiếu | GIỮ — dữ liệu bắt buộc người dùng phải thấy |
| `project` | Project | Link → Project (lọc chuẩn) | Dự án của kế hoạch | không vào tính toán — `setup/custom_fields.py:9-16` là `project` của Quotation | GIỮ — khoá lọc/nhóm |
| `sales_orders` | Sales Orders | **Table MultiSelect** → Sales Order | Danh sách đơn bán lấy nhu cầu | không vào tính toán — 0 dòng mã đọc field này; `aggregate_requirements` nhận **mảng tên SO truyền vào**, không đọc field | ẨN — sai kiểu bảng (xem ghi chú), chưa có mã đọc |
| `items` | Items | Table → AL Material Plan Item (reqd) | Các dòng vật tư và thiếu hụt | `al_material_plan.py:10-19` — `validate` duyệt từng dòng, ghi `stock_qty`/`shortfall_qty` | GIỮ — bảng nghiệp vụ chính; **nhưng chưa có gì ghi dòng vào** |

**Giảm phức tạp:**
- **`sales_orders` khai `Table MultiSelect` nhưng `options = Sales Order`** — `Sales Order` là DocType thường (`istable` rỗng), không phải bảng con; Frappe coi Table MultiSelect là bảng (`frappe/model/__init__.py:96`) nên mỗi dòng sẽ bị lưu như một bản ghi Sales Order gắn cha. Muốn giữ phải tạo DocType bảng con `AL Material Plan Sales Order {sales_order}`.
- Đường nạp dữ liệu **đứt ở 3 chỗ**: (1) `aggregate_requirements` không ai gọi; (2) hàm đó không ghi vào bảng `items` mà chỉ trả dict; (3) phép nhân `(bi.get("qty",1) or 1) * item.qty` tại `:43` nhân **chuỗi công thức** (`qty` trên `AL Bom Item` là `Small Text` chứa công thức FB) với số ⇒ lỗi kiểu. Muốn dùng phải tính `qty` bằng `FormulaEngine` trước.
- Vì `required_qty` không có gì điền, `shortfall_qty` thực tế luôn = 0 (`max(0, 0 − tồn − đã đặt)`).
- Chốt sống/chết trước khi làm gì thêm: menu vẫn có mục này (`alumglass_workspace_sidebar.json:1419`).

#### AL Material Plan Item — bảng con, 10 field

**Vai trò:** Từng dòng vật tư của **AL Material Plan**, gồm nhu cầu, tồn kho, đã đặt và thiếu hụt.
**Ai dùng:** chỉ `AL Material Plan.validate()` → `_calculate_shortfalls()` (`al_buying/doctype/al_material_plan/al_material_plan.py:13-19`). Không engine B0–B7, không API.
**Tổng kết:** 10 field · **5** field vào tính toán · **0** field chỉ cấu hình/hiển thị · **5** field không có tham chiếu · **đề xuất:** giữ 5 field đang được tính, ẩn/đếm dữ liệu 5 field còn lại.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `item_code` | Item Code | Link → Item (in_list_view) | Mã vật tư | `al_material_plan.py:15-17` — dùng làm khoá tra `Bin`; dòng không có mã thì bị bỏ qua | GIỮ — khoá của dòng |
| `required_qty` | Required Qty | Float (in_list_view) | Số lượng cần | `al_material_plan.py:19` — trừ vào thiếu hụt; **không có mã nào ghi field này** | GIỮ — người dùng nhập; cần nút nạp từ BOM thay vì gõ tay |
| `required_date` | Required Date | Date | Ngày cần vật tư | không vào tính toán — 0 tham chiếu | CHỜ-DỮ-LIỆU — 0 đọc; đếm dữ liệu trước khi xoá |
| `source_bom` | Source BOM | Data | BOM sinh ra nhu cầu | không vào tính toán — 0 tham chiếu (hàm tổng hợp có trả `sources[].bom` nhưng **không ghi vào field này**) | CHỜ-DỮ-LIỆU — 0 đọc, chưa từng được ghi |
| `source_slug` | Source Slug | Data | Dòng BOM sinh ra nhu cầu | không vào tính toán — 0 tham chiếu (trả `sources[].slug`, nhưng không ghi) | CHỜ-DỮ-LIỆU — 0 đọc, chưa từng được ghi |
| `stock_qty` | Stock Qty | Float | Tồn kho hiện tại | `al_material_plan.py:17` — `frappe.db.get_value("Bin", {"item_code": …}, "actual_qty")`, ghi đè mỗi lần `validate` | GIỮ — máy tính; **xem cảnh báo đa kho bên dưới** |
| `ordered_qty` | Ordered Qty | Float | Số lượng đã đặt mua | `al_material_plan.py:18-19` — chỉ đặt mặc định 0 rồi trừ vào thiếu hụt; **không cộng từ Purchase Order nào** | GIỮ — người dùng nhập tay, phải nói rõ là nhập tay |
| `shortfall_qty` | Shortfall Qty | Float | Số còn thiếu | `al_material_plan.py:19` — `max(0, required_qty − stock_qty − ordered_qty)` | GIỮ — máy tính, đúng công thức |
| `purchase_order` | Purchase Order | Link → Purchase Order | Phiếu đặt mua tương ứng | không vào tính toán — 0 tham chiếu; không mã nào đọc để cộng `ordered_qty` | CHỜ-DỮ-LIỆU — 0 đọc; hoặc bỏ nếu `ordered_qty` lấy từ SO/PO |
| `supplier` | Supplier | Link → Supplier | Nhà cung cấp dự kiến | không vào tính toán — `api/excel_io.py:269` là **docstring ví dụ**, không phải mã đọc; 2 hit còn lại là `supplier` của AL Supplier Price List | CHỜ-DỮ-LIỆU — 0 đọc; đếm dữ liệu trước khi xoá |

**Giảm phức tạp:**
- **Công thức thiếu hụt đúng, nguồn số sai**: `stock_qty` lấy `frappe.db.get_value("Bin", {"item_code": …}, "actual_qty")`. Phiên bản Frappe này thêm `limit=1` (`frappe/database/database.py:580`) ⇒ **chỉ lấy một dòng Bin bất kỳ**, không cộng dồn nhiều kho. Vật tư nằm ở 2 kho sẽ báo thiếu sai. Phải `sum` theo `item_code` (hoặc gọi `get_all` rồi cộng).
- `ordered_qty` **trông như máy tính nhưng là người dùng gõ** — nhãn không nói điều đó. Đổi nhãn/description hoặc tính từ Purchase Order.
- `required_qty` không có nguồn: 3 field `source_bom`/`source_slug`/`purchase_order` chờ đúng cái nút "nạp từ đơn bán" chưa viết. Hoặc viết nút đó, hoặc bỏ 3 field.

#### AL Supplier Price List — doc, 8 field

**Vai trò:** Bảng giá nhà cung cấp theo hiệu lực, kèm so sánh với bảng giá liền trước. **Tài liệu kiến trúc đã đánh dấu BỎ ở v28.9** (`CAU_TRUC_MODULE_VA_DOCTYPE.md:1478,1507`: thay bằng core `Item Price` với `buying=1` + `supplier`).
**Ai dùng:** **chỉ chính nó** — `validate()` so ngày (`al_buying/doctype/al_supplier_price_list/al_supplier_price_list.py:9-12`), `before_save()` đổi trạng thái + nạp giá trước đó (`:14-19`, `:21-68`). **Không đi vào engine tính giá bán** (xem mục 3 bên dưới).
**Tổng kết:** 8 field · **5** field vào tính toán · **1** field chỉ cấu hình/hiển thị · **2** field không có tham chiếu · **đề xuất:** đếm bản ghi rồi xoá theo v28.9; nếu giữ tạm thì đếm dữ liệu `brand` + `exchange_rate_snapshot` trước khi ẩn/xoá.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `supplier` | Supplier | Link → Supplier (reqd, in_list_view) | Nhà cung cấp của bảng giá | `al_supplier_price_list.py:38-48` — dùng làm điều kiện tìm bảng giá liền trước cùng nhà cung cấp | GIỮ — khoá tra giá trước, có mã đọc thật |
| `brand` | Brand | Link → Brand | Nhãn hiệu áp dụng | không vào tính toán — `setup/seed_demo_data.py:79,87,282,344,474` là `brand` của Brand / AL Profile System / Item / AL BOM, không đọc field này | CHỜ-DỮ-LIỆU — 0 đọc; đếm dữ liệu trước khi xoá |
| `effective_date` | Effective Date | Date (reqd, in_list_view) | Ngày bắt đầu hiệu lực | `al_supplier_price_list.py:10-11,43,47` — so với `expiry_date` và dùng làm điều kiện `effective_date <` khi tìm bảng giá trước | GIỮ — có mã đọc, quyết định bảng giá nào là "trước" |
| `expiry_date` | Expiry Date | Date | Ngày hết hiệu lực | `al_supplier_price_list.py:10-11,15` — chặn ngày hết hạn trước ngày hiệu lực; quá hạn thì đặt `Expired` | GIỮ — có mã đọc, điều khiển trạng thái |
| `currency_type` | Currency | Link → Currency (reqd) | Loại tiền của bảng giá | `al_supplier_price_list.py:23,29,42` — điều kiện tìm bảng giá trước (không so giá khác loại tiền) | GIỮ — có mã đọc, tránh so lẫn tỷ giá |
| `exchange_rate_snapshot` | Exchange Rate Snapshot | Float | Tỷ giá ghi lại tại thời điểm lập | không vào tính toán — dòng duy nhất nhắc tới là **docstring** `al_supplier_price_list.py:30`; **không mã nào ghi, không mã nào đọc** | CHỜ-DỮ-LIỆU — 0 đọc/0 ghi; nhiều khả năng luôn trống |
| `status` | Status | Select Draft/Active/Expired | Trạng thái hiệu lực | `al_supplier_price_list.py:14-18` — `before_save` tự đặt `Expired`/`Active` theo `expiry_date` | GIỮ — máy tính, người dùng cần thấy |
| `items` | Items | Table → AL Supplier Price List Item | Các dòng giá vật tư | `al_supplier_price_list.py:35-36,53-59,61-68` — đọc bảng giá trước để nạp giá cũ, rồi ghi đè `previous_unit_price`/`base_price_change_pct` lên dòng hiện tại | GIỮ — bảng nghiệp vụ chính |

**Giảm phức tạp:**
- **Giá nhà cung cấp KHÔNG vào giá bán.** Không có dòng mã nào trong `engine/`, `api/`, `al_*` đọc DocType này ngoài chính file controller của nó. Giá bán lấy từ `Item Price` (xem mục 3). Nếu nghiệp vụ cần giá NCC ảnh hưởng giá bán, đó là **việc phải thiết kế**, không phải chỉnh field.
- `exchange_rate_snapshot` và `fx_change_pct` (bảng con) là cặp **chưa có công thức**: docstring `:27-33` nói rõ cố ý không tính vì chưa chốt quy ước. Đừng để người dùng thấy ô trống — ẩn cả hai.
- Nếu giữ tạm trước khi bỏ: đặt `title_field = supplier` (hiện liên kết chỉ hiện hash), và thêm `description` cho `status` nói rằng máy tự đổi.

#### AL Supplier Price List Item — bảng con, 5 field

**Vai trò:** Từng dòng giá vật tư của **AL Supplier Price List**.
**Ai dùng:** chỉ controller cha — `_backfill_previous_price_and_change_pct()` (`al_buying/doctype/al_supplier_price_list/al_supplier_price_list.py:21-68`) đọc bảng giá trước và ghi 2 field so sánh.
**Tổng kết:** 5 field · **4** field vào tính toán · **0** field chỉ cấu hình/hiển thị · **1** field không có tham chiếu · **đề xuất:** giữ 4 field, ẩn `fx_change_pct` (chưa có công thức).

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `item_code` | Item Code | Link → Item (in_list_view) | Mã vật tư | `al_supplier_price_list.py:53-59,62` — khoá đối chiếu giữa bảng giá trước và hiện tại | GIỮ — khoá của phép so sánh |
| `unit_price` | Unit Price | Currency (in_list_view) | Đơn giá nhà cung cấp | `al_supplier_price_list.py:56,62,66-68` — đọc từ bảng trước và dùng tính % thay đổi giá gốc | GIỮ — số liệu chính; **chỉ dùng nội bộ DocType, không vào giá bán** |
| `previous_unit_price` | Previous Unit Price | Currency (read_only) | Đơn giá lần báo trước | `al_supplier_price_list.py:65` — máy ghi từ bảng giá gần nhất cùng NCC + cùng tiền tệ | GIỮ — máy tính, người dùng cần đối chiếu |
| `fx_change_pct` | FX Change (%) | Float (read_only) | Phần thay đổi do tỷ giá | không vào tính toán — không mã nào ghi; docstring `:27-33` nói **cố ý chưa tính** vì chưa chốt quy ước | ẨN — read_only mà không ai ghi ⇒ luôn trống |
| `base_price_change_pct` | Base Price Change (%) | Float (read_only) | % thay đổi giá gốc (đã loại tỷ giá) | `al_supplier_price_list.py:24,66-68` — `round((unit_price − prev)/prev*100, 4)` | GIỮ — máy tính, đúng mục đích |

**Giảm phức tạp:**
- `fx_change_pct` là field **read_only không có người ghi** — trên form nó luôn trống và không giải thích được vì sao. Ẩn (hoặc bỏ) cho tới khi chốt công thức tỷ giá.
- Cả bảng con đã có logic chạy thật (so giá liền trước) — nếu xoá DocType theo v28.9 thì **mất phần so giá này**; core `Item Price` không có `previous_unit_price`/`base_price_change_pct`. Cân nhắc trước khi xoá.
- Đặt `in_list_view` cho `previous_unit_price`/`base_price_change_pct` để người dùng thấy ngay mức tăng khi mở bảng.

---

##### Tổng hợp nhóm

| DocType | Số field | Vào tính toán | Chỉ cấu hình/hiển thị | 0 tham chiếu | Đề xuất |
|---|---|---|---|---|---|
| AL Cost Variance | 8 | 0 | 0 | 8 | Giữ 2 field khoá; ẩn 3 field chênh lệch; đếm dữ liệu 3 field |
| AL Material Plan | 5 | 1 | 1 | 3 | Chốt sống/chết; sửa `sales_orders`; nối hoặc bỏ `aggregate_requirements` |
| AL Material Plan Item | 10 | 5 | 0 | 5 | Giữ 5 field đang tính; sửa tồn kho đa kho; bỏ/ẩn 5 field chờ |
| AL Supplier Price List | 8 | 5 | 1 | 2 | Đếm bản ghi rồi bỏ theo v28.9; hoặc ẩn `brand` + `exchange_rate_snapshot` |
| AL Supplier Price List Item | 5 | 4 | 0 | 1 | Giữ 4 field; ẩn `fx_change_pct` |
| AL Cutting Plan Aluminum | 12 | 0 | 0 | 12 | Giữ khung ghi tay; ẩn 3 field tổng; chưa có thuật toán |
| AL Cutting Plan Glass | 10 | 0 | 0 | 10 | Giữ khung ghi tay; ẩn 3 field tổng; tách khổ tấm thành 2 số |
| AL Cutting Plan Item | 11 | 0 | 0 | 11 | Giữ 4 cột đo; ẩn 5 cột bố trí; 3 cột chờ dữ liệu |
| AL Glass Cutting Item | 10 | 0 | 0 | 10 | Giữ 4 cột đo; ẩn 6 cột bố trí/phế liệu |
| AL Cutting Standard | 9 | 2 | 0 | 7 | Giữ 2 field khảo sát; ẩn 7 field cắt; chọn một nơi giữ tham số |
| AL Production Order Bridge | 7 | 0 | 0 | 7 | Đếm bản ghi rồi bỏ cả DocType + 2 custom field trỏ vào |
| **Tổng** | **95** | **17** | **2** | **76** | |

> **Vì sao không field nào nhận nhãn GỘP hay BỎ:** trong từng DocType không có hai field trùng nghĩa
> (điều kiện của GỘP). Và dù 5 DocType đã bị tuyên bố bỏ, **chưa field nào có đường thay thế đã tồn tại
> trong mã** — kể cả 2 link kế hoạch cắt trên `AL Production Order Bridge`, vì tài liệu kiến trúc nói
> Work Order có field tương ứng (`CAU_TRUC_MODULE_VA_DOCTYPE.md:1054-1055`) nhưng
> `setup/custom_fields.py:96-101` **chưa tạo** 2 field đó. Vì vậy toàn bộ nhóm dừng ở mức
> GIỮ / ẨN / CHỜ-DỮ-LIỆU; muốn dùng BỎ phải làm bước thay thế trước.

##### Trả lời 5 câu hỏi về nhóm này

**1. Bài toán cắt đã có mã giải chưa?**
**Chưa. Không có một dòng thuật toán cắt nào.** 4 DocType liên quan cắt + `AL Cutting Standard` đều có controller chỉ `pass` và JS khung trống; không file nào trong `al_manufacturing/` được `engine/`, `api/`, `patches/` gọi tới. Thứ duy nhất giống thuật toán là **thư viện công thức mẫu** `formula_builder/templates.py:251-273`, và nó **không được DocType nào đọc** (chỉ `formula_builder/examples/03_du_toan.py:126,146` chạy demo). Ngay cả công thức mẫu cũng không phải thuật toán xếp thanh/tấm — nó chia tổng chiều dài cho chiều dài khả dụng.

Phân loại field theo vai trò dự kiến:

| | Đầu vào (người dùng nhập) | Kết quả (máy phải sinh) |
|---|---|---|
| Nhôm | `bom_version`, `stock_bar_length_mm`, `saw_kerf_mm`, `min_offcut_reusable_mm`, `items[].slug`, `items[].item_code`, `items[].cut_length_mm`, `items[].angle_start/end` | `total_bars_required`, `total_waste_mm`, `waste_pct`, `items[].bar_number`, `items[].position_from_mm/to_mm`, `items[].offcut_length_mm`, `items[].offcut_reusable`, `items[].offcut_serial_no` |
| Kính | `bom_version`, `jumbo_sheet_size`, `edge_trim_mm`, `items[].slug`, `items[].item_code`, `items[].cut_width_mm`, `items[].cut_height_mm` | `total_sheets_required`, `total_waste_m2`, `waste_pct`, `items[].sheet_number`, `items[].pos_x_mm/y_mm`, `items[].offcut_width_mm/height_mm`, `items[].offcut_reusable` |

Điểm chặn: `items[].cut_length_mm` / `cut_width_mm` / `cut_height_mm` **lẽ ra phải sinh từ BOM theo kích thước**, nhưng không mã nào đọc BOM để điền ⇒ hiện người dùng phải gõ tay toàn bộ.

**2. Đường đọc `bom_set_snapshot` và cách tính thiếu hụt**

*Ghi:* `al_bom_engine/doctype/al_bom_version/al_bom_version.py:130-138` dựng JSON
`{"set_code","set_name","product_type","profile_system","items":[ {...} ]}` từ các dòng `AL Bom Set`;
mỗi dòng là **toàn bộ field dữ liệu** của `AL Bom Item` (`_snapshot_item_row`, `:207-214`).

*Đọc (đường duy nhất):* `al_buying/doctype/al_material_plan/al_material_plan.py:33-44` —
với mỗi dòng Sales Order có `al_bom_version`, nạp `AL BOM Version`, parse `bom_set_snapshot`,
duyệt `snap["items"]`, cộng dồn `qty × SO qty` vào `required_qty`, gom `sources`.
Engine cũng đọc đúng chuỗi JSON đó nhưng theo đường riêng: `engine/bom_orchestrator.py:894-899`.

*Ai tính gì:*

| Field | Ai ghi | Công thức / nguồn |
|---|---|---|
| `required_qty` | **người dùng** | không có mã nào ghi; `aggregate_requirements` chỉ trả dict, không ghi vào bảng |
| `stock_qty` | **máy** | `al_material_plan.py:17` — `frappe.db.get_value("Bin", {"item_code": …}, "actual_qty") or 0` |
| `ordered_qty` | **người dùng** | `al_material_plan.py:18` — chỉ `or 0`, không cộng từ Purchase Order |
| `shortfall_qty` | **máy** | `al_material_plan.py:19` — `max(0, required_qty − stock_qty − ordered_qty)` |

Ba lỗi làm đường này **chưa chạy được**: (a) `aggregate_requirements` không có ai gọi; (b) `bi.get("qty")` là **chuỗi công thức** (`AL Bom Item.qty` kiểu `Small Text`) đem nhân với số ⇒ lỗi kiểu; (c) `Bin` chỉ lấy 1 dòng (`frappe/database/database.py:580` thêm `limit=1`) nên tồn đa kho bị cắt.

**3. Giá nhà cung cấp có đi vào engine tính giá bán không?**

**KHÔNG.** Dứt khoát, có bằng chứng:
- `grep -rn "AL Supplier Price List" --include=*.py` toàn app chỉ trả **2 dòng**, cả hai nằm trong chính `al_buying/doctype/al_supplier_price_list/al_supplier_price_list.py:39,54` (truy vấn bảng giá liền trước của chính nó). Không có dòng nào ở `engine/`, `api/`, `al_bom_engine/`.
- Đơn giá engine dùng lấy từ **`Item Price`**, không phải bảng NCC: `engine/bom_orchestrator.py:1133-1134` (`"unit_price": prices.get(pbi, 0) … prices.get(ic, 0)`) và `:1160` sau khi resolve item rule; riêng dòng phụ kiện được ghi đè bằng `AL Accessory Item.unit_price` (`:866`, `:1166-1167`).
- `api/excel_io.py:269` là **docstring ví dụ** (`vd {company, supplier} đang chọn trên dialog`), không phải mã đọc.
- Kiến trúc đã chốt thay bằng core `Item Price` (`CAU_TRUC_MODULE_VA_DOCTYPE.md:938-956`): *"Field cũ (AL Supplier Price List / Item) được giữ trong thiết kế v28.8 để tham chiếu nhưng không triển khai."*

⇒ DocType này hiện chỉ để **tham khảo/thu mua nội bộ**, và ngay cả vai trò đó cũng chỉ phục vụ chính nó (so giá liền trước). Không có đường nào từ đây sang giá bán.

**4. `AL Cost Variance` và `AL Production Order Bridge` có runtime không?**

**Không, cả hai.**
- Controller: `al_buying/doctype/al_cost_variance/al_cost_variance.py:5-7` = `pass`;
  `al_manufacturing/doctype/al_production_order_bridge/al_production_order_bridge.py:5-7` = `pass`.
- JS: cả hai chỉ có `refresh`/`validate` rỗng.
- Không dòng nào trong app gọi `frappe.get_doc/get_all("AL Cost Variance")`; tương tự với Bridge.
  Các hit "cost_bucket"/"al_bom_version" trong engine là **thuộc tính của dòng BOM / của Quotation Item**, trùng tên.
- Cái duy nhất "chạy" là **sự tồn tại của bản ghi**: Bridge còn là đích của Link field trên Work Order (`setup/custom_fields.py:97-98`) và Quality Inspection (`:125-126`) — người dùng chọn được một bản ghi mà không mã nào đọc lại.
- Bridge **đã bị tuyên bố bỏ** (`CAU_TRUC_MODULE_VA_DOCTYPE.md:943`) nhưng vẫn nằm trong menu (`alumglass_workspace_sidebar.json:2046`).

**5. Field chỉ có trong seed/patch/test** — đã ghi rõ trong từng dòng. Tổng hợp các trường hợp dễ nhầm:
- `AL Cutting Standard.profile_code`: chỉ xuất hiện ở `patches/v28_14/seed_bom_profile.py:108` và `seed_variable_catalog.py:177,200,247,253` — nhưng đó là `profile_code` của **AL Variable Profile**, không phải của DocType này.
- `AL Supplier Price List.brand`: chỉ có ở `setup/seed_demo_data.py` — và là `brand` của **Brand / AL Profile System / Item / AL BOM**.
- `AL Supplier Price List Item.fx_change_pct`: chỉ có trong **docstring** của chính nó.
- `AL Cutting Plan *.waste_pct`: chỉ có trong `formula_builder/templates.py:272` + `examples/03_du_toan.py:160` (công thức mẫu/demo).
- Các field `stock_bar_length_mm`, `saw_kerf_mm`, `edge_trim_mm` của 3 DocType cắt: chỉ có trong `formula_builder/templates.py` (thư viện mẫu) + `DEFAULT_PARAMS` — **không DocType nào đọc**.

---

**Ba việc nên làm trước trong nhóm này:**
1. **Chốt sống/chết 5 DocType đã bị tuyên bố bỏ ở v28.9** (Supplier Price List + Item, Material Plan + Item, Production Order Bridge). Chúng vẫn còn trong mã, trong menu (`alumglass_workspace_sidebar.json:1374,1419,2046`) và Bridge còn là đích Link trên Work Order / Quality Inspection. Đếm bản ghi rồi hoặc xoá gọn, hoặc gỡ dòng "BỎ" khỏi tài liệu kiến trúc — đừng để lửng lơ.
2. **Sửa hoặc gỡ `aggregate_requirements`** (`al_material_plan.py:27-45`): không ai gọi, và nếu gọi sẽ lỗi vì nhân chuỗi công thức `qty` với số. Đồng thời sửa `stock_qty` để cộng dồn `Bin` theo `item_code` thay vì lấy 1 dòng.
3. **Ẩn các field là "kết quả máy phải tính" nhưng đang cho gõ tay**: 3 field tổng của mỗi kế hoạch cắt, 11 cột bố trí/phế liệu của 2 bảng cắt (5 + 6), 3 field chênh lệch của Cost Variance, `fx_change_pct`. Đây là loại dữ liệu sai không kiểm được, sinh ra ngay khi có người dùng đầu tiên.

**Ba thứ KHÔNG nên đụng:**
1. **`AL Cutting Standard.applies_to` và `survey_tolerance_mm`** — 2 field duy nhất của cả nhóm Manufacturing có consumer thật (`al_site_survey.py:18-19`), đang quyết định "đạt/không đạt dung sai" của khảo sát. Xoá là hỏng luồng khảo sát.
2. **Logic so giá liền trước của `AL Supplier Price List`** (`al_supplier_price_list.py:21-68`) — dù DocType bị đánh dấu bỏ, phần `previous_unit_price`/`base_price_change_pct` **không có tương đương trong core `Item Price`**. Xoá DocType là mất năng lực này; cần quyết định trước.
3. **Công thức thiếu hụt `max(0, required − stock − ordered)`** (`al_material_plan.py:19`) — công thức đúng; lỗi nằm ở nguồn số (`stock_qty` một kho, `required_qty` không ai điền). Đừng sửa công thức khi sửa nguồn.

---

### 8.5 AL Formula Rules · AI · Account — 13 DocType

**13 DocType · 84 field.** Repo đọc: `/home/nxc/myfrappe/apps/alumglass` (`alumglass/`).
Mọi đường dẫn `file:dòng` tính từ gốc repo.


Nhóm này trả lời **hai câu hỏi khác nhau**, và hay bị nhầm là một:

| Câu hỏi | DocType chịu trách nhiệm | Đọc ở bước |
|---|---|---|
| "Dòng này **lấy mã vật tư nào**?" | `AL Dynamic Item Rule` (+ 2 bảng con của nó) | **B2** (chọn mã), áp dụng ở **B4** |
| "Dòng này **tính số lượng bao nhiêu**?" | `AL Quantity Calc Method` (+ `calc_fn` / `input_vars`) | **B3** dựng công thức, **B4** chạy |
| "Công thức lấy **hệ số / ngưỡng** ở đâu?" | `AL Calculation Rule` (+ 2 bảng con của nó) | **B1** (dự phòng hằng số), **B4/B6** (qua `lookup_rule`) |

##### A.1 Ba DocType "Rule" khác nhau ở đâu

**`AL Calculation Rule` — trả về một CON SỐ.**
Engine không tự tìm rule này. Nó chỉ được gọi khi **công thức của người dùng** viết
`lookup_rule('RULE-XXX', giá_trị)` (hàm được tiêm vào FormulaEngine tại
`alumglass/engine/bom_orchestrator.py:137`), hoặc làm **lưới dự phòng cuối** ở B1
(`alumglass/engine/bom_orchestrator.py:727-735`): biến hệ thống `H_mm` chưa resolve được thì
thử `AL Calculation Rule` tên `H-MM`, và chỉ nhận nếu `rule_type == "CONSTANT"`.
Kết quả trả về là **số** hoặc **chuỗi** (`result_value` kiểu Data) — dùng trong phép tính.

**`AL Dynamic Item Rule` — trả về một MÃ ITEM.**
Engine tự tìm rule này: dòng BOM có `item_selection_mode = "Rule"` + `item_rule` thì B2 gom mã
(`alumglass/engine/bom_orchestrator.py:924-925`), gọi `doc.resolve(input)` (`:1046` → `:1997`),
rồi B4 ghi đè `item_code` / `unit_price` / `weight_per_unit` của dòng (`:1155-1161`).
Kết quả là **mã Item** (Link tới `Item`), không phải số.

**`AL Dynamic Item Rule Version` — bản đóng băng của `AL Dynamic Item Rule`.**
Theo thiết kế: mỗi lần rule đổi thì tạo một version, duyệt Draft → Approved → Published → Retired
(`alumglass/setup/install_workflows.py:106-129`), và `AL Dynamic Item Rule.current_version` trỏ tới
bản đang dùng. **Trên mã hiện tại, cơ chế này không chạy** — xem phát hiện #1 ở cuối tài liệu.

##### A.2 Field nào là ĐIỀU KIỆN, field nào là KẾT QUẢ

| DocType | Điều kiện (so khớp) | Kết quả (trả về) | Quy ước biên |
|---|---|---|---|
| `AL Calculation Rule` — THRESHOLD | `AL Rule Threshold Row.from_value` / `to_value` | `AL Rule Threshold Row.result_value` (Float) | nửa mở `[from, to)`; nếu trượt hết thì thử lại `val == to` để chịu dữ liệu cũ (`al_calculation_rule.py:89-94`) |
| `AL Calculation Rule` — LOOKUP | `AL Rule Lookup Row.key_field` (Data, so **chuỗi**) | `AL Rule Lookup Row.result_value` (Data) | khớp tuyệt đối `str()==str()` (`al_calculation_rule.py:66-68`) |
| `AL Calculation Rule` — CONSTANT | không có điều kiện | `constant_value` (Float) | — |
| `AL Dynamic Item Rule` — THRESHOLD | `AL Dynamic Item Rule Threshold Row.from_value` / `to_value` | `...Threshold Row.result_item` (Link Item) | nửa mở `[from, to)`, cùng lưới chịu lỗi (`al_dynamic_item_rule.py:94-100`) |
| `AL Dynamic Item Rule` — LOOKUP | `...Lookup Row.key_field` (Data, so **chuỗi**) | `...Lookup Row.result_item` (Link Item) | khớp tuyệt đối (`al_dynamic_item_rule.py:72-75`) |

**Giá trị đem đi so khớp** lấy từ `AL Bom Item.rule_input_expr` — biểu thức dạng
`items.<slug>.<field>` (ví dụ `items.kinh_tren.glass_thick`), phân giải tại
`alumglass/engine/bom_orchestrator.py:1962-1979`. Không khớp regex thì rơi về
`glass_thick` rồi `glass_type` (`:1976-1979`).

##### A.3 Engine đọc nhóm này ở bước nào (B1–B4)

| Bước | Việc xảy ra | Dòng |
|---|---|---|
| **B1** — Gather inputs | Biến hệ thống thiếu giá trị → thử `AL Calculation Rule` CONSTANT, mã = tên biến đổi `_`→`-` | `engine/bom_orchestrator.py:727-735` |
| **B2** — Prefetch master data | Dòng có `item_selection_mode="Rule"` → gom `item_rule`; resolve từng cặp `(rule_code, input)` qua `AL Dynamic Item Rule.resolve()`; nạp weight/giá của mã vừa chọn | `engine/bom_orchestrator.py:924-925`, `:1044-1048`, `:1052-1060` |
| **B3** — Build formulas | Đọc `AL Quantity Calc Method.input_vars` của từng `calc_pattern`; dựng công thức `lookup_calc_pattern(<pattern>, w, h, weight, {biến phụ})` | `engine/bom_orchestrator.py:2036-2053`, `:2123-2130` |
| **B4** — Calculate BOM items | FormulaEngine gọi `lookup_calc_pattern` → đọc `calc_fn` trong DB; gọi `lookup_rule` → `AL Calculation Rule.resolve()`; sau khi tính, đọc `output_unit` để điền cột ĐVT | `engine/bom_orchestrator.py:125-142` (tiêm hàm), `:2257-2268` (ĐVT) |

**B6** (tính giá thành) dùng **chung** bộ hàm `lookup_rule` / `lookup_calc_pattern` với B4 —
xem `alumglass/engine/bom_orchestrator.py:120-142`.

##### A.4 `AL Quantity Calc Method` — field nào điều khiển công thức số lượng

Số lượng đơn vị của một dòng BOM **không** do field trên dòng quyết định, mà do **mã pattern**:

```
AL Bom Item.calc_pattern  ──(Link)──►  AL Quantity Calc Method.name (= calc_pattern_code)
                                              │
                                              ├─ calc_fn        ← công thức THẬT (đọc DB lúc B4)
                                              └─ input_vars     ← danh sách biến phụ cần truyền (đọc B3)
```

| Field | Vai trò trong phép tính số lượng | Dòng |
|---|---|---|
| `calc_pattern_code` | **Chính là `name` của bản ghi** (autoname `field:calc_pattern_code`) — mọi tham chiếu đi qua tên này | `formula_handlers.py:248`; `engine/bom_orchestrator.py:2045`, `:2266` |
| `calc_fn` | **Chuỗi lambda chứa công thức**. Đây là field duy nhất engine dùng để tính số lượng. Đọc từ DB, biên dịch qua `compile_expression` (safe_eval), cache lại | `formula_handlers.py:248-251` |
| `input_vars` | JSON **danh sách tên** biến phụ (vd `["piece_length"]`, `["depth"]`). B3 truyền giá trị theo danh sách này vào lời gọi `lookup_calc_pattern` | `engine/bom_orchestrator.py:2043-2053`, `:2082-2110`; backfill khi lưu dòng BOM: `al_bom_item.py:55-71` |
| `output_unit` | Chỉ là **ĐVT hiển thị** (m², m, cái…) gắn vào kết quả sau khi tính, không tham gia phép tính | `engine/bom_orchestrator.py:2264-2268` |
| `calc_formula` (Display Formula) | **Không được engine đọc.** Chỉ là chuỗi mô tả cho người đọc | seed `setup/seed_demo_data.py:152`; mọi `calc_formula` trong engine là của `AL Cost Template` |

Cơ chế dự phòng: `calc_fn` rỗng → dùng 14 pattern built-in trong `PATTERN_FORMULAS`
(`formula_handlers.py:34-56`). Mã không có ở cả hai nơi → `ValueError`
(`formula_handlers.py:262-265`).

> ⚠️ **Sửa `calc_formula` không đổi số lượng.** Chỉ `calc_fn` mới đổi. Xem phát hiện #3.

##### A.5 Bảng con `* Lookup Row` / `* Threshold Row`: chứa gì, ai sinh dòng

| Bảng con | Thuộc cha | Chứa gì | Ai sinh dòng | Engine đọc qua |
|---|---|---|---|---|
| `AL Rule Threshold Row` | `AL Calculation Rule` | Dải số `[from, to)` → một **số** (`result_value`) | Người khai rule nhập tay trên form cha; bộ demo do `setup/seed_demo_data.py:268-279` | `al_calculation_rule.py:32-34` (sắp theo `from_value`) → `:88-94` |
| `AL Rule Lookup Row` | `AL Calculation Rule` | Cặp `key → số/chuỗi` (`key_field` → `result_value`), so khớp **chuỗi** | Nhập tay trên form; seed `setup/seed_demo_data.py:298` | `al_calculation_rule.py:66-68` |
| `AL Dynamic Item Rule Threshold Row` | `AL Dynamic Item Rule` | Dải số `[from, to)` → một **mã Item** (`result_item`) | Nhập tay; seed `setup/seed_demo_data.py:293-295` (nẹp theo độ dày kính) | `al_dynamic_item_rule.py:41-43` → `:94-100` |
| `AL Dynamic Item Rule Lookup Row` | `AL Dynamic Item Rule` | Cặp `key → mã Item`, so khớp **chuỗi** | Nhập tay; seed `setup/seed_demo_data.py:297-299` (keo theo loại kính) | `al_dynamic_item_rule.py:72-75` |

**Không có tác nhân tự động nào sinh dòng.** Không scheduler, không patch định kỳ — chỉ người dùng
bấm "Add row" trên form cha, và script seed dựng bộ demo.

**Kiểm tra khi lưu** (chạy ở cả 2 rule, dùng chung quy ước):

- chồng lấp (`to` dòng trước > `from` dòng sau) ⇒ **chặn lưu** (`al_calculation_rule.py:25-29`, `al_dynamic_item_rule.py:34-38`);
- khe hở (`to` < `from` dòng sau) ⇒ **chỉ cảnh báo**, vẫn lưu (`al_calculation_rule.py:36-57`);
- LOOKUP/THRESHOLD không có dòng nào ⇒ chặn lưu (`al_calculation_rule.py:11-16`, `al_dynamic_item_rule.py:11-18`).

---


#### AL Calculation Rule — doc, 7 field

**Vai trò:** Bảng tra **một con số** (hệ số, khe hở, số bản lề) cho công thức. Kỹ thuật viên khai trên form; engine không tự tìm mà chỉ gọi khi công thức viết `lookup_rule('MÃ', giá_trị)`.
**Ai dùng:** B4 + B6 qua `lookup_rule` (`engine/bom_orchestrator.py:137`); B1 làm lưới dự phòng CONSTANT (`:727-735`).
**Tổng kết:** 7 field · **5** field vào engine · **1** field chỉ cấu hình/hiển thị · **1** field không tham chiếu · **đề xuất:** giữ nguyên, ẩn 1 field (`is_active`).

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `rule_code` | Rule Code | Data | Mã rule — cũng là `name` bản ghi | `engine/bom_orchestrator.py:83` — `frappe.get_cached_doc("AL Calculation Rule", rule_code)`; B1 dựng mã từ tên biến tại `:730-733` | GIỮ — khóa tra cứu, đổi mã là gãy mọi công thức đang gọi |
| `rule_name` | Rule Name | Data | Nhãn tiếng Việt để người khai rule đọc | Không vào tính toán — chỉ seed (`setup/seed_demo_data.py:258`); engine không đọc | GIỮ — nhãn người dùng, không phải ô nhập thừa |
| `rule_type` | Rule Type | Select | Chọn CONSTANT / THRESHOLD / LOOKUP | `al_calculation_rule.py:61,63,65` — rẽ nhánh `resolve()`; `engine/bom_orchestrator.py:734` chỉ nhận CONSTANT ở nhánh dự phòng | GIỮ — quyết định cả cách đọc dữ liệu |
| `constant_value` | Constant Value | Float | Giá trị khi rule là hằng số | `al_calculation_rule.py:62` — `return self.constant_value`; `engine/bom_orchestrator.py:735` | GIỮ |
| `is_active` | Is Active? | Check | Ý định: tắt rule | **Không vào tính toán** — `resolve()` (`al_calculation_rule.py:59-68`) và `_lookup_rule` (`engine/bom_orchestrator.py:76-83`) đều không kiểm. Các hit `engine:1227`, `fb_handlers.py:115` là của `AL Variable Dimension Mapping` | ẨN — bỏ tick **không** ngừng dùng rule, dễ gây hiểu nhầm |
| `threshold_rows` | Threshold Rows | Table | Dải số → giá trị | `al_calculation_rule.py:12` (bắt buộc ≥1 dòng), `:64` → `:88-94` (duyệt `from_value` tăng dần, biên nửa mở) | GIỮ |
| `lookup_rows` | Lookup Rows | Table | Khóa chuỗi → giá trị | `al_calculation_rule.py:15` (bắt buộc ≥1 dòng), `:66-68` | GIỮ |

**Giảm phức tạp:**
- Ẩn `is_active` khỏi form ngay — nó là công tắc giả.
- Ghi chú ngay trên form: `lookup_rule` chỉ đọc **AL Calculation Rule**, không đọc `AL Dynamic Item Rule` — gõ nhầm loại sẽ nhận cảnh báo "không tìm thấy" và tính **0** (`engine/bom_orchestrator.py:86-95`), không báo lỗi đỏ.
- `AL Bom Item.price_rule` (Link tới DocType này, hiện khi `price_type='Rule'`) **không có mã nào đọc** — xem ghi chú ở phần `AL Dynamic Item Rule`.

---

#### AL Rule Threshold Row — bảng con, 3 field

**Vai trò:** Một dải số `[from, to)` ánh xạ sang một con số. Thuộc `AL Calculation Rule.threshold_rows`.
**Ai dùng:** B4/B6, gián tiếp qua `AL Calculation Rule.resolve()` → `_resolve_threshold()`.
**Tổng kết:** 3 field · **3** field vào engine · **0** field chỉ cấu hình/hiển thị · **0** field không tham chiếu · **đề xuất:** giữ nguyên.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `from_value` | From Value | Float | Cận dưới của dải | `al_calculation_rule.py:90` — `if row.from_value <= val < row.to_value`; sắp xếp theo field này ở `:34` | GIỮ |
| `to_value` | To Value | Float | Cận trên (không tính) | `al_calculation_rule.py:90`, `:93` (lưới chịu lỗi: khớp đúng biên trên); kiểm chồng lấp `:25` | GIỮ |
| `result_value` | Result Value | Float | Số trả về khi rơi vào dải | `al_calculation_rule.py:91` — `return row.result_value` | GIỮ |

**Giảm phức tạp:**
- Giữ nguyên. Không có field thừa.
- Quy ước `[from, to)` là **hợp đồng chung** với bảng con của Dynamic Item Rule — đừng đổi một bên.

---

#### AL Rule Lookup Row — bảng con, 2 field

**Vai trò:** Một cặp "khóa → số" để tra cứu danh nghĩa. Thuộc `AL Calculation Rule.lookup_rows`.
**Ai dùng:** B4/B6 qua `AL Calculation Rule.resolve()` nhánh LOOKUP.
**Tổng kết:** 2 field · **2** field vào engine · **0** field chỉ cấu hình/hiển thị · **0** field không tham chiếu · **đề xuất:** giữ nguyên.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `key_field` | Key Value | Data | Khóa cần khớp | `al_calculation_rule.py:67` — `if str(row.key_field) == str(input_value)`; so **chuỗi**, `"20"` khác `"20.0"` | GIỮ |
| `result_value` | Result Value | Data | Giá trị trả về | `al_calculation_rule.py:68` — `return row.result_value` | GIỮ — nhưng kiểu **Data**: chèn chữ vào đây sẽ làm công thức số học gãy |

**Giảm phức tạp:**
- Kiểu `Data` của `result_value` là điểm yếu: nên đổi sang `Float` nếu chỉ dùng số, hoặc thêm validate chặn chữ.

---

#### AL Dynamic Item Rule — doc, 7 field

**Vai trò:** Chọn **mã Item** theo điều kiện (độ dày kính → loại nẹp; loại kính → loại keo). Kỹ thuật viên khai; engine tự tìm khi dòng BOM ở chế độ `Rule`.
**Ai dùng:** B2 chọn mã (`engine/bom_orchestrator.py:924-925`, `:1044-1048`); B4 áp vào dòng (`:1155-1161`); API `alumglass.api.resolve_item_rule` (`api/__init__.py:318-325`) → `resolve_item()` (`al_dynamic_item_rule.py:104-114`).
**Tổng kết:** 7 field · **4** field vào engine · **1** field chỉ cấu hình/hiển thị · **2** field không tham chiếu · **đề xuất:** bỏ `current_version`, ẩn `is_active`.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `rule_code` | Rule Code | Data | Mã rule — cũng là `name` bản ghi | `engine/bom_orchestrator.py:1997` — `frappe.get_cached_doc("AL Dynamic Item Rule", rule_code)`; khóa lấy từ `AL Bom Item.item_rule` (`:924-925`) | GIỮ |
| `rule_name` | Rule Name | Data | Nhãn tiếng Việt | Không vào tính toán — chỉ seed (`setup/seed_demo_data.py:293,297`) | GIỮ — nhãn người dùng |
| `rule_type` | Rule Type | Select | Chỉ có THRESHOLD / LOOKUP (không CONSTANT) | `al_dynamic_item_rule.py:70,72` — rẽ nhánh `resolve()` | GIỮ |
| `current_version` | Current Version | Link (read-only) | Ý định: trỏ tới bản version đang dùng | **Không vào tính toán** — không lệnh nào ghi, không lệnh nào đọc. Các hit `engine:326-332` và `run_test.py:15` là `current_version` của **AL BOM**; `engine:1997` luôn đọc rule **sống** | BỎ — đường thay thế: `AL Dynamic Item Rule Version` không có runtime; cần lịch sử thì dùng Version của Frappe (`track_changes`) |
| `is_active` | Is Active? | Check (mặc định 1) | Ý định: tắt rule | **Không vào tính toán** — `resolve()` (`al_dynamic_item_rule.py:66-76`) và `_resolve_dynamic_item` (`engine/bom_orchestrator.py:1982-1998`) không kiểm | ẨN — bỏ tick không ngừng chọn rule |
| `threshold_rows` | Threshold Rows | Table | Dải số → mã Item | `al_dynamic_item_rule.py:13` (≥1 dòng), `:71` → `:94-100` | GIỮ |
| `lookup_rows` | Lookup Rows | Table | Khóa chuỗi → mã Item | `al_dynamic_item_rule.py:17` (≥1 dòng), `:72-75` | GIỮ |

**Giảm phức tạp:**
- Xoá `current_version` và ẩn cả DocType `AL Dynamic Item Rule Version` khỏi menu — cặp này không có runtime (phát hiện #1).
- Ẩn `is_active`.
- Ghi chú: `resolve()` trả `None` khi không khớp dải/khóa (`:69,76`) — engine **bỏ qua** dòng đó, không cảnh báo. Khe hở trong bảng dòng chính là nguồn "mất mã" âm thầm.

---

#### AL Dynamic Item Rule Threshold Row — bảng con, 3 field

**Vai trò:** Dải số `[from, to)` → một mã Item. Thuộc `AL Dynamic Item Rule.threshold_rows`.
**Ai dùng:** B2, gián tiếp qua `AL Dynamic Item Rule.resolve()` → `_resolve_threshold()`.
**Tổng kết:** 3 field · **3** field vào engine · **0** field chỉ cấu hình/hiển thị · **0** field không tham chiếu · **đề xuất:** giữ nguyên.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `from_value` | From Value | Float | Cận dưới | `al_dynamic_item_rule.py:96` — `if row.from_value <= val < row.to_value`; sắp xếp `:43` | GIỮ |
| `to_value` | To Value | Float | Cận trên (không tính) | `al_dynamic_item_rule.py:96`, `:99`; kiểm chồng lấp `:34` | GIỮ |
| `result_item` | Result Item | Link (Item) | Mã vật tư trả về | `al_dynamic_item_rule.py:97` — `return row.result_item`; bắt buộc khác rỗng ở `:23-24` | GIỮ |

**Giảm phức tạp:**
- Giữ nguyên; validate đã chặn dòng thiếu Item và `from > to` (`:23-26`).

---

#### AL Dynamic Item Rule Lookup Row — bảng con, 2 field

**Vai trò:** Cặp "khóa → mã Item" để tra danh nghĩa. Thuộc `AL Dynamic Item Rule.lookup_rows`.
**Ai dùng:** B2 qua `AL Dynamic Item Rule.resolve()` nhánh LOOKUP.
**Tổng kết:** 2 field · **2** field vào engine · **0** field chỉ cấu hình/hiển thị · **0** field không tham chiếu · **đề xuất:** giữ nguyên.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `key_field` | Key Value | Data | Khóa cần khớp | `al_dynamic_item_rule.py:74` — `str(row.key_field) == str(input_value)`; so **chuỗi**, phân biệt hoa/thường | GIỮ |
| `result_item` | Result Item | Link (Item) | Mã vật tư trả về | `al_dynamic_item_rule.py:75` | GIỮ |

**Giảm phức tạp:**
- Giữ nguyên. Lưu ý cho người khai: khóa `"LOWE"` không khớp `"lowe"`.

---

#### AL Dynamic Item Rule Version — doc, 5 field

**Vai trò:** Bản đóng băng của một `AL Dynamic Item Rule`, có workflow duyệt Draft → Approved → Published → Retired. **Hiện không có runtime** — không engine/API nào đọc.
**Ai dùng:** Chỉ Frappe Workflow (cài bởi `setup/install_workflows.py:106-129`) và sidebar. **Không có consumer nghiệp vụ.**
**Tổng kết:** 5 field · **1** field vào engine (chỉ workflow đọc trạng thái) · **0** field chỉ cấu hình/hiển thị · **4** field không tham chiếu · **đề xuất:** ẩn/ngừng dùng cả DocType, hoặc gắn vào engine nếu thật sự cần đóng băng rule.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `rule` | Rule | Link (AL Dynamic Item Rule) | Rule cha | **Không vào tính toán** — không lệnh nào đọc; `engine:1997` đọc rule sống theo `rule_code`, không qua version | CHỜ-DỮ-LIỆU — nếu bật lại cơ chế pin thì đây là khóa nối |
| `version_name` | Version Name | Data | Nhãn phiên bản (vd `v1.0`) | Không có consumer — các hit `setup/seed_demo_data.py:347,481` và `patches/v28_10:56,58` là `AL BOM Version` | CHỜ-DỮ-LIỆU |
| `valid_from` | Valid From | Datetime | Hiệu lực từ | Không có consumer — `fb_handlers.py:135`, `engine:1073,1711` là `Item Price` / `AL BOM Version` | CHỜ-DỮ-LIỆU |
| `workflow_state` | Workflow State | Select | Trạng thái duyệt | `setup/install_workflows.py:174` — Frappe Workflow dùng field này làm state field (`doc.workflow_state_field`); `:108` gắn workflow vào DocType | GIỮ — nhưng chỉ giữ nếu giữ DocType; workflow chỉ chặn chuyển trạng thái, **không** ảnh hưởng giá |
| `rule_snapshot_json` | Rule Snapshot (JSON) | JSON (reqd) | Bản chụp rule | Không có consumer — không lệnh nào ghi, không lệnh nào đọc | BỎ — bắt người dùng dán JSON tay mà không ai dùng; nếu cần thì sinh tự động trong `on_update` |

**Giảm phức tạp:**
- Cách rẻ nhất: ẩn DocType khỏi sidebar (`alumglass_workspace_sidebar.json:973-977`) và ẩn `current_version` trên rule cha. Cơ chế "pin phiên bản rule" hiện **không tồn tại trong mã**.
- Nếu muốn làm thật: engine phải đọc snapshot từ version đã Published thay vì `get_cached_doc` rule sống (`engine/bom_orchestrator.py:1997`) — đó là việc của DEV, không phải đổi tài liệu.
- Bỏ `rule_snapshot_json` dạng nhập tay dù chọn hướng nào.

---

#### AL Quantity Calc Method — doc, 8 field

**Vai trò:** Danh mục **công thức tính số lượng** theo đơn vị (m², m, cái, bộ…). Dòng BOM trỏ tới bằng `calc_pattern`. Chỉ `AL Technical Admin` / `System Manager` được sửa `calc_fn` (`al_quantity_calc_method.py:44-52`).
**Ai dùng:** B3 đọc `input_vars` (`engine/bom_orchestrator.py:2043-2053`); B4 gọi `lookup_calc_pattern` → đọc `calc_fn` (`formula_handlers.py:248-251`); B4 đọc `output_unit` để điền ĐVT (`engine/bom_orchestrator.py:2264-2268`).
**Tổng kết:** 8 field · **4** field vào engine · **1** field chỉ cấu hình/hiển thị · **3** field không tham chiếu · **đề xuất:** giữ nguyên phần lõi, ẩn `sort_order` + `group` + `calc_pattern_name` cho tới khi nối dropdown.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `calc_pattern_code` | Calc Pattern Code | Data | Mã pattern — cũng là `name` bản ghi | `formula_handlers.py:248` — tra `calc_fn` **theo tên bản ghi**; B3/B4 lọc theo `name` (`engine:2045`, `:2266`); dòng BOM trỏ tới ở `al_bom_item.json` field `calc_pattern` | GIỮ — đổi mã là gãy mọi dòng BOM đang dùng |
| `calc_pattern_name` | Calc Pattern Name | Data | Nhãn tiếng Việt cho dropdown | Không vào tính toán. `formula_handlers.py:327` có đọc, nhưng hàm `get_available_patterns` **không có nơi nào gọi** trong repo | ẨN — nhãn đúng chỗ, nhưng chưa nối vào UI nào |
| `output_unit` | Output Unit | Data | ĐVT kết quả (m2, m, cái…) | `engine/bom_orchestrator.py:2264-2268` — batch đọc theo `calc_pattern`, gắn vào cột ĐVT của kết quả | GIỮ |
| `sort_order` | Sort Order | Int | Thứ tự trong dropdown | Không vào tính toán. Chỉ dùng ở `formula_handlers.py:320,330,355` trong `get_available_patterns` — **hàm không có caller** | ẨN — bật lại khi nối dropdown |
| `group` | Group | Data | Nhóm hiển thị (A-Tuyến tính…) | Không vào tính toán. Chỉ `formula_handlers.py:328,341,355` — cùng hàm không caller. Mã còn có `_GROUP_BY_KEY` dự phòng (`:59-74`) | ẨN — giá trị trong DB trùng bảng hằng trong mã |
| `calc_formula` | Display Formula | Small Text | Công thức dạng đọc được | **Không vào tính toán** — engine không đọc field này ở bất kỳ đâu; mọi `calc_formula` trong engine (`:2481,2508,2511,2515,2587`) là của `AL Cost Template`. Chỉ seed ghi (`setup/seed_demo_data.py:152`) | GIỮ — là tài liệu tại chỗ cho người sửa `calc_fn`; phải ghi rõ "chỉ để đọc" |
| `calc_fn` | Python Lambda | Small Text | **Công thức số lượng thật** | `formula_handlers.py:248-251` — `frappe.db.get_value(..., "calc_fn")` → `_compile_calc_fn` (safe_eval); rỗng thì rơi về `PATTERN_FORMULAS` (`:256-261`); đổi/xoá thì xoá cache (`al_quantity_calc_method.py:54-73`, nối qua `hooks.py:72-75`) | GIỮ — field lõi |
| `input_vars` | Input Variables | JSON | Danh sách **tên** biến phụ pattern cần | `engine/bom_orchestrator.py:2045-2052` — B3 batch đọc; `:2082` lặp danh sách để truyền giá trị; `al_bom_item.py:62-68` backfill key còn thiếu khi lưu dòng BOM | GIỮ |

**Giảm phức tạp:**
- Ghi rõ trên form: `calc_formula` là **chú thích**, `calc_fn` mới là công thức (phát hiện #3).
- Ẩn `sort_order` + `group` cho tới khi có màn chọn pattern — hiện chúng chỉ tốn công nhập.
- Nếu bỏ `get_available_patterns` (không caller), xoá luôn 3 field phụ thuộc; nhưng **giữ** `output_unit` vì engine đọc thật.

---

#### AL Alert Config — doc, 9 field

**Vai trò:** Cấu hình một loại cảnh báo (BOM hết hạn, lệch chi phí, tồn kho…). **Chỉ có phần kiểm tra cú pháp công thức là chạy**; không có bộ máy nào bắn cảnh báo.
**Ai dùng:** `validate()` kiểm cú pháp `trigger_condition` (`al_alert_config.py:11-14`). Không có consumer khác — `scheduler_events` trong `hooks.py:105-118` **bị comment**, không có job nào quét `AL Alert Config`.
**Tổng kết:** 9 field · **1** field vào engine (chỉ validate) · **2** field chỉ cấu hình/hiển thị (tên bản ghi + nhãn) · **6** field không tham chiếu · **đề xuất:** ẩn phần lớn; chỉ giữ `trigger_condition` nếu còn dùng form để soạn công thức.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `alert_code` | Alert Code | Data | Mã cảnh báo — cũng là `name` (autoname `field:alert_code`) | Không vào tính toán. Là định danh bản ghi; không lệnh nào tra theo mã này | GIỮ — là tên bản ghi; bỏ phải đổi `autoname` |
| `alert_name` | Alert Name | Data | Nhãn cảnh báo | Không có consumer | GIỮ — nhãn người dùng trên form/list |
| `alert_type` | Alert Type | Select | Loại cảnh báo | **Không có consumer** — không nhánh mã nào đọc `alert_type` | ẨN — giữ cho tới khi làm engine cảnh báo |
| `is_active` | Is Active? | Check | Ý định: bật/tắt | **Không có consumer** — không nơi nào lọc (`engine:698,1227,1277` là Profile System / Variable Dimension Mapping) | ẨN — công tắc giả |
| `cooldown_minutes` | Cooldown (minutes) | Int | Giãn cách giữa 2 lần bắn | Không có consumer | CHỜ-DỮ-LIỆU |
| `variable_profile` | Variable Profile | Link (AL Variable Profile) | Mô tả ghi: "lọc danh sách biến gợi ý cho Trigger Condition" | **Không có consumer** — `al_alert_config.py:11` gọi `build_known_names("AL Alert Config", self.name)` **không truyền** `fieldname`/profile. Các hit `patches/v28_14/seed_bom_profile.py:38,150` là `AL Bom Set` | ẨN — mô tả field đang hứa điều mã không làm |
| `trigger_condition` | Trigger Condition (FB formula) | Small Text | Biểu thức quyết định khi nào bắn | `al_alert_config.py:12` — `check_formula(...)` chặn lưu nếu sai cú pháp; đăng ký widget công thức tại `patches/v28_14/seed_variable_catalog.py:135` | GIỮ — field duy nhất có tiêu thụ thật |
| `recipients` | Recipients | Table MultiSelect (options=`User`) | Người nhận | Không có consumer. **Và không lưu được dòng**: `Table MultiSelect` đòi `options` là DocType bảng con (`istable=1`); `User` không phải bảng con | BỎ — đường thay thế: bảng con riêng `AL Alert Recipient` (Link User) hoặc `Small Text` danh sách email |
| `notification_channel` | Notification Channel | Select | Kênh gửi | Không có consumer | CHỜ-DỮ-LIỆU |

**Giảm phức tạp:**
- Nói thẳng trên form: **cấu hình này chưa bắn cảnh báo** — không có scheduler.
- Sửa `recipients` sang bảng con trước khi ai đó nhập liệu vào (hiện sẽ lỗi khi lưu dòng).
- Bỏ hoặc cập nhật mô tả `variable_profile` cho khớp mã.

---

#### AL AI Suggestion Log — doc, 13 field

**Vai trò:** Ý định ghi lại gợi ý do AI sinh (giá, vật tư thay thế, thiết kế…) kèm người duyệt. **Không có runtime**: controller rỗng (`al_ai_suggestion_log.py:5-7`), không lệnh nào `insert`/`get_all` DocType này trong toàn repo.
**Ai dùng:** **Không có consumer.** Form và validate mặc định của Frappe.
**Tổng kết:** 13 field · **0** field vào engine · **0** field chỉ cấu hình/hiển thị · **13** field không tham chiếu · **đề xuất:** ẩn cả DocType khỏi menu cho tới khi có luồng AI thật.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `suggestion_code` | Suggestion Code | Data (reqd) | Mã gợi ý | Không có consumer. `autoname=None` ⇒ Frappe vẫn tự sinh `name`, field này là mã **nhập tay thứ hai** | ẨN — nếu bật lại thì bỏ field, dùng `name` |
| `created_by_ai` | Created by AI? | Check (reqd, default 1) | Đánh dấu nguồn | Không có consumer | CHỜ-DỮ-LIỆU |
| `ai_model` | AI Model | Data | Tên model | Không có consumer | CHỜ-DỮ-LIỆU |
| `suggestion_type` | Suggestion Type | Select (reqd) | Loại gợi ý | Không có consumer | CHỜ-DỮ-LIỆU |
| `status` | Status | Select | PENDING/APPROVED/REJECTED/IMPLEMENTED | **Không có consumer** — hit `api/__init__.py:33,225,237,278,290` là dict trạng thái job BOM (`"status": "Queued"`, `"Running"`…) | CHỜ-DỮ-LIỆU |
| `confidence_score` | Confidence Score (0-1) | Float | Độ tin cậy | Không có consumer | CHỜ-DỮ-LIỆU |
| `target_doctype` | Target DocType | Link (DocType) | Đối tượng được gợi ý | **Không có consumer** — hit `variable_sources/adapters.py:79-85` là **tham số** `target_doctype` của hàm `_first_link_field` | CHỜ-DỮ-LIỆU |
| `target_docname` | Target Document | Data | Bản ghi được gợi ý | Không có consumer | CHỜ-DỮ-LIỆU |
| `suggestion_content` | Suggestion Content | JSON (reqd) | Nội dung gợi ý | Không có consumer | CHỜ-DỮ-LIỆU |
| `rationale` | Rationale | Text | Lý do | Không có consumer | CHỜ-DỮ-LIỆU |
| `approved_by` | Approved By | Link (User) | Người duyệt | Không có consumer | CHỜ-DỮ-LIỆU |
| `approved_on` | Approved On | Datetime | Lúc duyệt | Không có consumer | CHỜ-DỮ-LIỆU |
| `implementation_result` | Implementation Result | Text | Kết quả áp dụng | Không có consumer | CHỜ-DỮ-LIỆU |

**Giảm phức tạp:**
- Ẩn DocType khỏi sidebar — không có đường nào tạo bản ghi.
- Nếu quyết định bật: bỏ `suggestion_code` (dùng `name`), và đừng mô tả `created_by_ai` như đang chạy.

---

#### AL AI Interaction Log — doc, 10 field

**Vai trò:** Ý định ghi lại một lượt hỏi–đáp với AI (câu hỏi, câu trả lời, thời gian, phản hồi người dùng). **Không có runtime**: controller rỗng (`al_ai_interaction_log.py:5-7`), không lệnh nào ghi/đọc.
**Ai dùng:** **Không có consumer.**
**Tổng kết:** 10 field · **0** field vào engine · **0** field chỉ cấu hình/hiển thị · **10** field không tham chiếu · **đề xuất:** ẩn cả DocType khỏi menu.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `interaction_code` | Interaction Code | Data (reqd) | Mã lượt hỏi | Không có consumer. `autoname=None` ⇒ Frappe vẫn tự sinh `name` | ẨN — bỏ field nếu bật lại |
| `user` | User | Link (User, reqd) | Người hỏi | **Không có consumer** — hit `engine:291,374-381` là biến cục bộ `_user_provided` / tham số `user` của hàm api | CHỜ-DỮ-LIỆU |
| `interaction_date` | Interaction Date | Datetime (reqd) | Thời điểm | Không có consumer | CHỜ-DỮ-LIỆU |
| `query_type` | Query Type | Select | Loại câu hỏi | Không có consumer | CHỜ-DỮ-LIỆU |
| `ai_model` | AI Model | Data | Model đã trả lời | Không có consumer | CHỜ-DỮ-LIỆU |
| `response_time_ms` | Response Time (ms) | Int | Độ trễ | Không có consumer | CHỜ-DỮ-LIỆU |
| `query_text` | Query Text | Text (reqd) | Câu hỏi | Không có consumer | CHỜ-DỮ-LIỆU |
| `ai_response` | AI Response | Text | Câu trả lời | Không có consumer | CHỜ-DỮ-LIỆU |
| `user_feedback` | User Feedback | Select | Đánh giá | Không có consumer | CHỜ-DỮ-LIỆU |
| `feedback_note` | Feedback Note | Text | Ghi chú | Không có consumer | CHỜ-DỮ-LIỆU |

**Giảm phức tạp:**
- Ẩn DocType khỏi sidebar cùng `AL AI Suggestion Log` — hai DocType này là cặp "ghi log AI" chưa có nguồn ghi.
- Nếu bật thật: `interaction_code` phải chuyển thành `autoname` chuỗi, đừng bắt người dùng gõ mã.

---

#### AL Project Financial Config — doc, 6 field

**Vai trò:** Ý định khai tham số tài chính theo dự án (overhead, dự phòng, điều khoản thanh toán, giữ lại). **Không có runtime**: controller rỗng (`al_project_financial_config.py:5-7`); không lệnh nào đọc.
**Ai dùng:** **Không có consumer.**
**Tổng kết:** 6 field · **0** field vào engine · **0** field chỉ cấu hình/hiển thị · **6** field không tham chiếu · **đề xuất:** ẩn cả DocType khỏi menu; nếu bật thì đặt ràng buộc duy nhất cho `project`.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `project` | Project | Link (Project) | Dự án áp cấu hình | Không có consumer — hit `setup/custom_fields.py:9-16,51` là custom field `project` của **Quotation** và `al_project_id` của **Sales Order** | ẨN — là khóa nghiệp vụ, nhưng chưa ai đọc; và **không unique** nên tạo được 2 cấu hình cho cùng dự án |
| `overhead_pct` | Overhead (%) | Float | Tỷ lệ chi phí chung | Không có consumer | CHỜ-DỮ-LIỆU |
| `contingency_pct` | Contingency (%) | Float | Tỷ lệ dự phòng | Không có consumer | CHỜ-DỮ-LIỆU |
| `payment_terms_template` | Payment Terms Template | Link | Điều khoản thanh toán | Không có consumer | CHỜ-DỮ-LIỆU |
| `retention_pct` | Retention (%) | Float | Tỷ lệ giữ lại | Không có consumer | CHỜ-DỮ-LIỆU |
| `retention_release_days` | Retention Release (days) | Int | Số ngày hoàn giữ lại | Không có consumer | CHỜ-DỮ-LIỆU |

**Giảm phức tạp:**
- Ẩn DocType; nếu dự định dùng thật: thêm ràng buộc duy nhất trên `project` trước khi có dữ liệu.
- Đừng mô tả nhóm này là "đang dùng" trong tài liệu cho người vận hành — chưa có engine nào đọc.

---

#### AL Project Profitability Snapshot — doc, 9 field

**Vai trò:** Ý định chụp lại lãi/lỗ một dự án tại một ngày. **Không có runtime**: controller rỗng (`al_project_profitability_snapshot.py:5-7`); không lệnh nào tính hoặc ghi các con số.
**Ai dùng:** **Không có consumer.**
**Tổng kết:** 9 field · **0** field vào engine · **0** field chỉ cấu hình/hiển thị · **9** field không tham chiếu · **đề xuất:** ẩn cả DocType khỏi menu cho tới khi có job tính.

| Field | Nhãn | Kiểu | Mục đích | Vào tính toán thế nào | Đánh giá |
|---|---|---|---|---|---|
| `project` | Project | Link (Project, reqd) | Dự án | Không có consumer (hit `setup/custom_fields.py` là Quotation/Sales Order) | ẨN |
| `snapshot_date` | Snapshot Date | Date (reqd) | Ngày chụp | Không có consumer | ẨN |
| `total_revenue` | Total Revenue | Currency | Doanh thu | Không có consumer — **không có chỗ nào tính ra số này** | CHỜ-DỮ-LIỆU |
| `total_estimated_cost` | Total Estimated Cost | Currency | Chi phí dự toán | Không có consumer | CHỜ-DỮ-LIỆU |
| `total_actual_cost` | Total Actual Cost (from GL) | Currency | Chi phí thực tế | Không có consumer — nhãn "from GL" **sai**: không có truy vấn GL nào trong repo ghi field này | CHỜ-DỮ-LIỆU |
| `gross_profit` | Gross Profit | Currency | Lãi gộp | Không có consumer | CHỜ-DỮ-LIỆU |
| `gross_margin_pct` | Gross Margin (%) | Float | Biên lãi | Không có consumer | CHỜ-DỮ-LIỆU |
| `cost_breakdown_json` | Cost Breakdown (JSON) | JSON | Cơ cấu chi phí | Không có consumer | CHỜ-DỮ-LIỆU |
| `notes` | Notes | Text | Ghi chú | Không có consumer | CHỜ-DỮ-LIỆU |

**Giảm phức tạp:**
- Ẩn DocType — 100 % field là số phải do máy tính, mà chưa có máy nào tính.
- Sửa nhãn `Total Actual Cost (from GL)` trước khi đưa cho người dùng: chưa có nguồn GL.
- Nếu bật thật: thêm job tính + `autoname` theo `project + snapshot_date`, tránh trùng.

---


##### Tổng hợp nhóm

| DocType | Số field | Vào engine | Chỉ cấu hình/hiển thị | 0 tham chiếu | Đề xuất |
|---|---|---|---|---|---|
| AL Calculation Rule | 7 | 5 | 1 | 1 | Giữ lõi; ẩn `is_active` |
| AL Rule Threshold Row | 3 | 3 | 0 | 0 | Giữ nguyên |
| AL Rule Lookup Row | 2 | 2 | 0 | 0 | Giữ; cân nhắc đổi `result_value` sang Float |
| AL Dynamic Item Rule | 7 | 4 | 1 | 2 | Bỏ `current_version`; ẩn `is_active` |
| AL Dynamic Item Rule Threshold Row | 3 | 3 | 0 | 0 | Giữ nguyên |
| AL Dynamic Item Rule Lookup Row | 2 | 2 | 0 | 0 | Giữ nguyên |
| AL Dynamic Item Rule Version | 5 | 1 | 0 | 4 | Ẩn/ngừng dùng cả DocType |
| AL Quantity Calc Method | 8 | 4 | 1 | 3 | Giữ `calc_fn`/`input_vars`/`output_unit`; ẩn `sort_order`+`group`+`calc_pattern_name` |
| AL Alert Config | 9 | 1 | 2 | 6 | Chỉ giữ `trigger_condition`; sửa/bỏ `recipients` |
| AL AI Suggestion Log | 13 | 0 | 0 | 13 | Ẩn cả DocType |
| AL AI Interaction Log | 10 | 0 | 0 | 10 | Ẩn cả DocType |
| AL Project Financial Config | 6 | 0 | 0 | 6 | Ẩn cả DocType |
| AL Project Profitability Snapshot | 9 | 0 | 0 | 9 | Ẩn cả DocType |
| **Tổng** | **84** | **25** | **5** | **54** | |

**Ba việc nên làm trước trong nhóm này:**

1. **Ẩn 4 DocType không có runtime** (AI Suggestion Log, AI Interaction Log, Project Financial Config, Project Profitability Snapshot) + `AL Dynamic Item Rule Version` khỏi sidebar. Đây là 43/84 field — hơn nửa nhóm — mà không có một lệnh nào đọc. Người dùng đang nhìn thấy menu dẫn vào form không làm gì.
2. **Bỏ `is_active` khỏi 3 form rule** (`AL Calculation Rule`, `AL Dynamic Item Rule`, `AL Alert Config`) hoặc nối nó vào engine. Giữ nguyên công tắc không có tác dụng là dạy người dùng một thói quen sai: "tắt rule là ngừng dùng".
3. **Ghi rõ `calc_formula` là chú thích, `calc_fn` mới là công thức** trên `AL Quantity Calc Method` — và chặn quyền sửa `calc_formula` gây hiểu nhầm (hiện chỉ `calc_fn` bị chặn theo role).

**Ba thứ KHÔNG nên đụng:**

1. **Quy ước biên `[from, to)` + lưới chịu lỗi `val == to`** ở `al_calculation_rule.py:88-94` và `al_dynamic_item_rule.py:94-100`. Dữ liệu seed đang khai kiểu đóng-hai-đầu có khe 0.1 (`setup/seed_demo_data.py:270-279`); bỏ lưới chịu lỗi là **giá trị đúng biên trượt hết, trả 0, sai giá âm thầm**.
2. **`AL Quantity Calc Method.calc_fn` + cơ chế cache/xoá cache** (`formula_handlers.py:248-261`, `al_quantity_calc_method.py:54-73`, nối qua `hooks.py:72-75`). Đây là chỗ duy nhất quyết định số lượng; `safe_eval` + AST whitelist là hàng rào bảo mật, không phải thủ tục.
3. **Đường B2 chọn mã Item** (`engine/bom_orchestrator.py:924-925`, `:1044-1048`, `:1155-1161`). Cache theo cặp `(rule_code, rule_input)` là bản vá cho lỗi thật: cache chỉ theo `rule_code` từng làm 2 dòng dùng chung rule nhưng khác độ dày kính ra cùng một mã (ghi chú tại `:1022-1034`).

---


##### Ba phát hiện khi đọc nhóm này

Ba điểm dưới đây không phải lỗi field, nhưng đổi cách hiểu cả nhóm — đọc trước khi lập kế hoạch.

##### 1. Cơ chế "ghim phiên bản rule" không tồn tại trong mã

`AL Dynamic Item Rule.current_version` (`al_dynamic_item_rule.json`, field Link read-only) và cả DocType
`AL Dynamic Item Rule Version` **không được engine đọc ở đâu**. Bằng chứng:

- `alumglass/engine/bom_orchestrator.py:1997` — `frappe.get_cached_doc("AL Dynamic Item Rule", rule_code)` → luôn đọc **rule sống**, không qua version.
- `alumglass/engine/bom_orchestrator.py:326-332` — dòng `current_version` mà input gốc gán cho rule này thực ra là `AL BOM.current_version` (**trùng tên**).
- `alumglass/setup/install_workflows.py:106-129` — chỉ cài workflow Draft→Approved→Published→Retired; State `Published` **không** làm engine đọc bản đóng băng.
- `rule_snapshot_json` (reqd) không có lệnh ghi lẫn đọc.

**Hệ quả cho người vận hành:** duyệt và "Xuất bản" một version rule **không** chốt gì cả — sửa rule là mọi báo giá tính lại theo bản mới. Tài liệu cho người dùng **không được** hứa "đã ghim phiên bản".

##### 2. `is_active` trên 3 DocType rule là công tắc giả

`AL Calculation Rule` (`al_calculation_rule.json`, mặc định 1), `AL Dynamic Item Rule`, `AL Alert Config`
đều có `is_active`, và **không lệnh nào kiểm nó**:

- `alumglass/al_formula_rules/doctype/al_calculation_rule/al_calculation_rule.py:59-68` — `resolve()` không nhánh `is_active`.
- `alumglass/engine/bom_orchestrator.py:76-83` — `_lookup_rule` gọi thẳng `rule.resolve(...)`.
- `alumglass/engine/bom_orchestrator.py:1997` — `_resolve_dynamic_item` gọi thẳng `doc.resolve(...)`.
- Các hit `is_active` trong input (`engine/bom_orchestrator.py:698,1227,1277`, `fb_handlers.py:115`) đều thuộc `AL Profile System` / `AL Variable Dimension Mapping` — **trùng tên**.

**Hệ quả:** bỏ tick "Is Active?" trên một rule **không** làm rule ngừng được dùng. Muốn ngừng phải xoá bản ghi hoặc sửa công thức đang gọi nó — và xoá thì `_lookup_rule` chỉ ghi cảnh báo rồi trả **0** (`engine/bom_orchestrator.py:86-95`), không chặn tính giá.

##### 3. `calc_formula` trông như công thức số lượng nhưng engine không đọc — chỉ `calc_fn` mới có tác dụng

Trên `AL Quantity Calc Method`, field `calc_formula` (nhãn "Display Formula") và `calc_fn` (nhãn "Python Lambda")
nằm cạnh nhau trong cùng section "Formula Definition" (`al_quantity_calc_method.json`). Engine chỉ đọc `calc_fn`:

- `alumglass/formula_handlers.py:248` — `frappe.db.get_value("AL Quantity Calc Method", code, "calc_fn")`, rồi `_compile_calc_fn` ở `:250`.
- Mọi chỗ `calc_formula` trong engine (`alumglass/engine/bom_orchestrator.py:2481,2508,2511,2515,2587`) là của **`AL Cost Template`** — trùng tên.
- `alumglass/setup/seed_demo_data.py:152` chỉ ghi `calc_formula` để làm chú thích.

Đồng thời `output_unit` thì **có** được đọc thật (`engine/bom_orchestrator.py:2264-2268`), còn nhóm field chỉ phục vụ
dropdown (`calc_pattern_name`, `sort_order`, `group`) nằm trong `get_available_patterns`
(`formula_handlers.py:303-356`) — hàm này **không có nơi nào gọi** trong repo.

**Hệ quả:** người sửa số lượng mà chỉnh `calc_formula` sẽ thấy số **không đổi**, và không có cảnh báo nào.
Tài liệu/usage phải nói rõ: sửa `calc_fn`, cần role `AL Technical Admin` hoặc `System Manager`
(`alumglass/al_formula_rules/doctype/al_quantity_calc_method/al_quantity_calc_method.py:44-52`).


---

## 9. Phân tích độ phức tạp & phương án bỏ bớt

### 9.1 Bốn loại phức tạp — và loại nào đáng cắt

| Loại | Đo bằng | Con số | Cắt được không |
|---|---|---|---|
| **Bề mặt** (người dùng thấy) | field khai báo − field `hidden` | 574 − 17 = **557** field hiển thị; **68** DocType khai trong app (chưa đếm thực tế trên site) | Cắt rẻ nhất, hoàn tác được: ẩn field/ẩn DocType |
| **Tính toán** | field có đường vào engine/API/handler (phép đo §6.1) | **288** field | Khó — cắt là đổi kết quả tính; chỉ nên **gộp** khi trùng nghĩa |
| **Chết** | field không xuất hiện ở đâu | **168** field (120 ở 17 DocType chưa có runtime) | Cắt được, nhưng phải qua §7.3 |
| **Cấu trúc** | DocType chưa có runtime · controller rỗng | **17/68** DocType · **43/68** controller rỗng | Ẩn khỏi menu trước, xoá sau |

Điểm quan trọng: **bốn loại này không cộng vào nhau**. Một field có thể "chết" về mã nhưng vẫn là
cột người dùng phải nhìn (bề mặt), và một field "có đường vào mã" vẫn có thể là **trùng tên** với
field của DocType khác.

### 9.2 DocType phức tạp nhất

Hai cột số dưới đây **đều theo phép đo §6.1** (đếm tên field xuất hiện trong mã), nên cộng lại đúng
bằng số field của DocType. Số "Tổng kết" trong từng khối §8 do người đọc tự xếp loại theo ý nghĩa
field — có thể lệch vài đơn vị, không phải mâu thuẫn.

| DocType | Field | 0 tham chiếu | Có tham chiếu (mã hoặc UI) | Vì sao đáng chú ý |
|---|---|---|---|---|
| AL Bom Item | 38 | 9 | 29 | Dòng vật tư trung tâm: 6 field là tàn dư mô hình giá cũ, 8 cờ tính năng chưa cài |
| AL Change Order | 15 | 4 | 11 | Chỉ `validate`; workflow duyệt chưa được cài |
| AL Bom Set | 14 | 0 | 14 | Toàn bộ field đều vào engine — không cắt được |
| AL AI Suggestion Log | 13 | 11 | 2 | Không có runtime; 11 field chỉ để form |
| AL BOM | 13 | 3 | 10 | Cấu hình gốc; phần lớn field thật sự dùng |
| AL Variable Profile Rule | 13 | 0 | 13 | Nhiều field nhưng **không field nào đổi số tiền** — chỉ lọc gợi ý |
| AL Cost Bucket | 12 | 1 | 11 | `source_type` khai 8 giá trị, engine chỉ hỗ trợ 1 |
| AL Cutting Plan Aluminum | 12 | 3 | 9 | Chưa có thuật toán cắt; bảng chỉ để chứa kết quả |
| AL Material Category | 12 | 0 | 12 | Công tắc quyết định engine đọc gì — nên giữ |
| AL Variable Library | 12 | 0 | 12 | Nguồn biến thật của B1 — nên giữ |

### 9.3 Mức cần thiết theo từng field (kết quả §8)

| Nhãn | Số field | Nghĩa | Việc làm ngay được |
|---|---|---|---|
| `GIỮ` | **326** | Có mã đọc hoặc là nhãn người dùng buộc thấy | Không đụng |
| `ẨN` | **98** | Không mã đọc; phần lớn là cờ của tính năng chưa cài | Ẩn khỏi form — hoàn tác 1 dòng |
| `BỎ` | **21** | Không mã đọc **và** đã có đường thay thế | Xoá khai báo, sau khi soát §7.3 |
| `CHỜ-DỮ-LIỆU` | **124** | Không mã đọc, chưa biết có dữ liệu thật | Đếm dữ liệu rồi mới quyết |
| `GỘP` | **5** | Trùng nghĩa với field khác trong cùng DocType | Gộp — xem §9.6 |

Tổng 574. **Nhóm "ẩn được ngay" + "bỏ được" = 98 + 21 = 119 field**, tức **21 % số field** có thể
rời khỏi màn hình mà không đổi một phép tính nào.

> **Vì sao 11 field từng xếp `BỎ` nay xếp `ẨN`:** chúng là cờ của tính năng **chưa từng được cài**
> (thay thế vật tư, sale đổi mã, đổi kính theo panel, gom lô, ghim phiên bản rule) — không có
> "đường thay thế" nào đang chạy, nên theo đúng định nghĩa ở §8.0 thì phải là `ẨN`, không phải `BỎ`.

### 9.4 Ba phương án

| Phương án | Làm gì | Kết quả | Công | Rủi ro | Khi nào chọn |
|---|---|---|---|---|---|
| **A — Tối thiểu (khuyến nghị trước)** | Ẩn 98 field `ẨN`; ẩn 17 DocType chưa có runtime khỏi menu/workspace | Bề mặt giảm 115 mục, **không đổi phép tính nào** | S | Gần 0 — đổi cấu hình hiển thị | Ngay, không cần chờ ai |
| **B — Vừa** | A + xoá khai báo 21 field `BỎ` + gộp 5 field `GỘP` | Field khai báo còn **548** | M | Thấp, nhưng **phải soát §7.3 trước**: xoá field mà còn công thức trỏ tới thì tính giá ném `NameError`; cột DB vẫn còn | Sau khi A chạy 1 chu kỳ **và Owner xác nhận** |
| **C — Triệt để** | B + xử lý 124 field `CHỜ-DỮ-LIỆU` (đo dữ liệu từng field) + quyết định 17 DocType | Có thể còn **≈ 424** field | L (nhiều tuần) | Trung bình — mất dữ liệu người dùng đã nhập | Khi Owner xác nhận phạm vi sản phẩm |

**Không khuyến nghị** một "phương án D" là gộp DocType: các cặp trùng vai (`AL BOM`/`AL Bom Set`/
`AL BOM Version`) khác nhau ở vòng đời, gộp là đổi khoá ngoại của dữ liệu đã submit (§7.4).

### 9.5 21 field đề xuất bỏ

Điều kiện để vào bảng này: **không lệnh nào đọc** và **đã có đường khác thay thế**. Trước khi xoá
vẫn phải soát 6 nơi ở §7.3 và đếm dữ liệu.

| DocType | Field | Nhãn | Lý do / đường thay thế |
|---|---|---|---|
| AL Color Standard | `is_default` | Mau mac dinh | `is_representative` đã thay |
| AL Glass Master | `item_code` | Item Code | engine tra theo `glass_code` |
| AL BOM | `pk_set` | Accessory Set (Optional) | phụ kiện đi qua DocType `AL Accessory Set` |
| AL BOM | `requires_approval_for_new_version` | Requires Approval for New Version? | duyệt nằm ở `workflow_state`, không đọc cờ |
| AL BOM Change Log | `field_name` | Field Name | bảng không có người ghi lẫn người đọc |
| AL BOM Change Log | `reason` | Reason | như trên |
| AL Bom Item | `price_rule` | Price Rule | giá đi qua `price_base_item`/Item Price |
| AL Bom Item | `price_list` | Price List | bảng giá do binding / Selling Settings quyết định |
| AL Bom Item | `fixed_price` | Fixed Price | thay bằng Item Price, hoặc `unit_price` của dòng phụ kiện |
| AL Bom Item | `cut_fee_pct` | Cut Fee (%) | thay bằng dòng công thức trong Cost Template |
| AL Bom Item | `ctx_inject_prefix` | CTX Inject Prefix | thay bằng tham chiếu `items.<slug>.<field>` đã có |
| AL Bom Item | `formula_set` | Formula Set | công thức đi qua `AL Cost Template` |
| AL BOM Version | `valid_to` | Valid To | thay bằng `workflow_state = Retired` |
| AL BOM Version | `items` | Change Log Items | bảng con không có người ghi |
| AL Cost Bucket | `parent_bucket` | Parent Bucket | B5 không dựng cây bucket |
| AL Cost Bucket | `default_expense_account` | Default Expense Account | hạch toán do ERPNext lo, engine không ghi GL |
| AL Cost Template Item | `show_on_quotation` | Show on Quotation? | báo giá lấy theo `is_final_price` / `is_pre_vat_price` |
| ConfigSnapshot | `snapshot_id` | Snapshot ID | trùng với `name` của bản ghi |
| AL Dynamic Item Rule | `current_version` | Current Version | engine đọc rule **sống** (`bom_orchestrator.py:1997`) |
| AL Dynamic Item Rule Version | `rule_snapshot_json` | Rule Snapshot (JSON) | không nơi nào ghi lẫn đọc |
| AL Alert Config | `recipients` | Recipients | `Table MultiSelect` trỏ `User` (không phải bảng con) nên không lưu được dòng; thêm nữa không có scheduler nào chạy |

### 9.6 5 field nên gộp

| DocType | Field | Nhãn | Lý do / đường thay thế |
|---|---|---|---|
| AL Variable Set Item | `var_label` | Label | vào `variable`, Library là nguồn |
| AL Variable Set Item | `var_type` | Type | vào `variable`, Library là nguồn |
| AL Variable Set Item | `link_doctype` | Link Doctype | vào `variable`, Library là nguồn |
| AL Variable Set Item | `select_options` | Select Options | vào `variable`, Library là nguồn |
| AL Bom Item | `price_type` | Price Type | gộp vào `price_base_item`: luôn hiện ô giá đại diện, bỏ 2 lựa chọn Rule/Fixed |

### 9.7 Chỗ hai lượt đo lệch nhau — và vì sao không phải mâu thuẫn

- **§6.3 liệt 11 field bỏ được; §8 liệt 21.** Lượt đọc từng field tìm thêm **10 field** có đường
  thay thế mà §6.3 chưa xếp: `AL Color Standard.is_default`, `AL Glass Master.item_code`,
  `AL BOM Change Log.field_name`/`reason`, `AL BOM Version.valid_to`/`items`,
  `AL Cost Bucket.parent_bucket`, `AL Dynamic Item Rule.current_version`,
  `AL Alert Config.recipients`, `AL Bom Item.ctx_inject_prefix`.
- **`price_type`** nằm trong §6.3 (nhóm bỏ) nhưng §8 xếp `GỘP` — vì cách xử lý đúng là gộp vào
  `price_base_item`, không phải xoá trắng.
- **11 field từng xếp `BỎ` nay xếp `ẨN`** (§9.3): cờ của tính năng chưa cài, không có đường thay thế.
- **`AL BOM Version.valid_to`** nằm ở §6.4 (nhóm chờ dữ liệu) nhưng §8 đề xuất `BỎ` vì đã có
  `workflow_state = Retired`. Hai câu không đụng nhau: §6.4 nói *chưa đủ căn cứ để xoá hôm nay*.
- **"Có tham chiếu" không đồng nghĩa "đúng là field này".** Ví dụ `AL Glass Master.item_code` bị
  máy đếm là "có dùng" vì trùng tên với `item_code` của dòng BOM; mở đúng dòng thì engine tra giá
  kính theo `glass_code`.

### 9.8 Ba phát hiện ngoài phạm vi field nhưng đổi cách hiểu hệ thống

1. **Profile/Profile Rule/Cross Row không đổi số tiền.** Validate công thức cố ý bỏ qua profile
   (`al_bom_engine/formula_validate.py:66-70`). Gán profile chỉ đổi danh sách gợi ý.
2. **`cost_template_snapshot` rỗng ⇒ giá bán = 0, không báo lỗi.** Snapshot chỉ được ghi khi
   `AL BOM.default_cost_template` có giá trị (`al_bom_version.py:140-159`); B6 gặp rỗng thì `return`
   im lặng (`bom_orchestrator.py:2484-2490`).
3. **Workflow duyệt chưa từng được cài.** `install_workflows()` bị comment ở `hooks.py:191` và
   `:235`, nên `workflow_state` là Select trơ; cờ `requires_approval_for_new_version` cũng không
   được đọc ở đâu.

### 9.9 Thứ tự làm

1. **A** — ẩn 98 field + ẩn 17 DocType khỏi menu (không xoá gì).
2. **Đo dữ liệu** — chạy đếm giá trị khác rỗng cho 21 field `BỎ` và 124 field `CHỜ-DỮ-LIỆU`.
3. **B** — xoá khai báo 21 field đã đo là rỗng + gộp 5 field.
4. **C** — chốt phần còn lại theo dữ liệu và theo quyết định phạm vi sản phẩm.

Điều kiện không được làm hỏng sau mỗi bước: **B0–B7 chạy đúng với BOM mẫu** và **submit Quotation
vẫn tạo ConfigSnapshot**.


---

## 10. Đọc tiếp

| Bạn cần | Đọc | Đừng nhầm với |
|---|---|---|
| Quyết định bỏ/giữ field, ẩn DocType | §6.7 rồi §7.2 (P1–P5) | — |
| Sửa code theo kế hoạch | `docs/BAN-FULL-A-Z.md` | **Không phải** catalog DocType |
| Tra lịch sử kiến trúc | `CAU_TRUC_MODULE_VA_DOCTYPE.md` (repo root) | Bản cũ: 61 DocType, v28.8 |
| Hiểu biến / công thức / gợi ý | `docs/variable-catalog/README.md` | — |
| Số liệu field mới nhất | chạy lại script ở §6.1 | Đừng chép số trong tài liệu này |


