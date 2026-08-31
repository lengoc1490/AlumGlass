# AlumGlass — Bản vá tổng hợp V6 P10

Tổng hợp toàn bộ thay đổi đã thảo luận: (1) kính/vật tư mã đại diện tra giá
động theo Pricing Dimension, (2) validate công thức cho các doctype còn thiếu
(giống AL Cost Template), (3) rà soát & sửa hardcode để mọi thứ setting qua
DB — đúng nguyên tắc "Zero hardcode" của dự án.

Repo gốc đối chiếu: `github.com/lengoc1490/AlumGlass`,
`github.com/lengoc1490/Formula-Builder` (đọc trực tiếp code thật, không suy
đoán — mọi dòng/hàm trích dẫn trong tài liệu này đều tồn tại thật trong repo
tại thời điểm rà soát).

## Cách dùng gói này

Copy từng file trong thư mục `alumglass/` của package này **đè lên đúng path
tương ứng** trong app `alumglass` thật của bạn (cấu trúc thư mục đã giữ y hệt
repo gốc — copy nguyên `alumglass/` đè lên app root là đủ, trừ phần JSON cần
kiểm tra kỹ vì Frappe có thể tự thêm field `idx`/`docstatus` mặc định lúc
migrate — xem mục "Lưu ý JSON" bên dưới).

```
1. cp -r alumglass/* <app_path>/alumglass/
2. bench --site <site> migrate          # áp field JSON mới + chạy patch v28_10
3. bench --site <site> clear-cache
4. Restart bench (để nạp lại api/__init__.py, bom_orchestrator.py mới)
5. Chạy checklist test ở cuối tài liệu này
```

---

## PHẦN A — Kính/vật tư mã đại diện, tra giá động theo Pricing Dimension

### File: `alumglass/engine/bom_orchestrator.py`

| Thay đổi | Vị trí (hàm) | Vì sao |
|---|---|---|
| `self.glass_master_map = {}` — đọc từ `al_bom_vars["glass_master_map"]` | `__init__`, `b1_gather_inputs` | Dialog Quotation đã lưu key này ("Kính theo vị trí") từ trước nhưng **engine chưa từng đọc** — đổi kính đa vị trí không có tác dụng thật |
| `_resolve_glass_override(rep_code)` (hàm mới) | ngay trước `_resolve_rule_input_for_code` | Resolve mã kính thật: ưu tiên `glass_master_map[rep]` → `glass_master_override` (global cũ) → giữ nguyên |
| Batch query weight/price/Glass Master gộp cả `glass_master_map.values()` | `b1_gather_inputs` | Đảm bảo giá + spec kính mới được fetch, không chỉ mã override global |
| `glass_data[slug]` build qua `_resolve_glass_override` | `b1_gather_inputs` | **Đây là chỗ quyết định nẹp kính tra đúng độ dày** — `rule_input_expr` kiểu `items.kinh_tren.glass_thick` đọc từ `glass_data`, nay resolve đúng theo từng vị trí đã đổi |
| `row_literals` (giá kính) dùng `_resolve_glass_override` | `b1_gather_inputs` | Giá kính tra theo đúng mã đã đổi ở từng vị trí, có composite key nếu cấu hình Pricing Dimension cho category kính |

→ **Kết quả:** dialog đổi mã kính theo từng vị trí → engine tra đúng giá + nẹp kính tự tra đúng độ dày kính mới, đúng yêu cầu ban đầu.

### File mới: `alumglass/engine/composite_pricing.py`

Thuật toán `best_partial_match()` — DÙNG CHUNG giữa `bom_orchestrator._match_composite_price` (nhánh fallback, luôn chạy) và `fb_handlers.aluminum_price_composite` mode `exact_match` (nhánh FB-max, chạy khi FVB seed D3). Trước đây 2 nhánh có **2 thuật toán khác nhau** (fallback = best-partial-match; FB-max = AND cứng qua DB filter) → hành vi tra giá đổi khác khi chuyển nhánh, có thể vỡ golden test CDMQ-2C/4C khi D3 chạy. Giờ gộp về 1 chỗ.

### `bom_orchestrator.py` — lọc Pricing Dimension theo `material_category`

Hàm mới `_get_dim_mappings_raw()` + `_dim_fieldnames_for_category(category)` (giữ nguyên `_get_dim_fieldnames()` cũ để không phá test hiện có). `_fetch_composite_prices()` giờ lọc dimension theo **material_category của đúng dòng BOM sở hữu item_code/price_base_item đó** — trước đây nhánh fallback áp TẤT CẢ mapping cho MỌI item_code bất kể category (nhôm/kính lẫn lộn); nhánh FB-max đã lọc đúng từ trước. Giờ 2 nhánh nhất quán, và cơ chế này **tự động áp dụng cho cả kính lẫn nhôm hay category thêm sau** — không hardcode tên category nào.

### File: `alumglass/al_bom_engine/doctype/al_bom_version/al_bom_version.py`

Snapshot Pricing Dimension (`_snapshot_pricing_dimensions`) và snapshot Cost Template (trong `on_workflow_transition`/hàm publish) bổ sung field `material_category` và `is_final_price` — trước đây thiếu nên dù sửa code, BOM Version publish mới vẫn không lọc được category (snapshot rỗng field này).

### Patch mới: `alumglass/patches/v28_10/rebackfill_snapshot_category_final_price.py`

Patch `v28_9` cũ **chỉ backfill snapshot RỖNG** (idempotent theo thiết kế) — không tự lan field mới tới BOM Version **đã Published từ trước**. Patch `v28_10` này ghi đè lại toàn bộ snapshot (dùng config hiện tại) cho mọi version Published, đảm bảo lọc category + `is_final_price` hoạt động ngay cả với báo giá cũ.

⚠ **Cần đăng ký patch trong `patches.txt`** (file này không có trong package vì không rõ nội dung đầy đủ của bạn — tự thêm dòng sau vào cuối `alumglass/patches.txt`):
```
alumglass.patches.v28_10.rebackfill_snapshot_category_final_price
```

### File: `alumglass/fb_handlers.py`

`aluminum_price_composite` mode `exact_match`: thay AND-filter cứng bằng `composite_pricing.best_partial_match()` — cùng thuật toán với nhánh fallback (xem trên).

---

## PHẦN B — Validate công thức cho các doctype còn thiếu (giống AL Cost Template)

### Hiện trạng đã rà soát (bằng chứng từ code thật)

| Doctype.field | Autocomplete trước patch | Validate server trước patch |
|---|---|---|
| `AL Cost Template.items.calc_formula` | ✅ | ✅ (viết tay riêng trong `al_cost_template.py`) |
| `AL Bom Set.items.{width,height,qty,show_condition,item_condition_formula,rule_input_expr}` | ✅ | ❌ KHÔNG có |
| `AL Accessory Set.items.qty_formula` | ❌ KHÔNG có luôn | ❌ KHÔNG có |
| `AL Alert Config.trigger_condition` | ✅ | ❌ `.py` chỉ `pass` |

⚠ **Đính chính quan trọng:** hướng dẫn cũ (`HUONG_DAN_INJECT_VALIDATE.md`) giả định `FormulaValidator` chỉ kiểm tra node gốc của `items.slug.field`. Đọc trực tiếp `formula_builder/formula_utils/security.py` cho thấy **giả định này SAI** — mọi truy cập `.attr` không nằm trong whitelist `{get,keys,values,items,to_dict}` bị từ chối thẳng. Engine thật (`bom_orchestrator._normalize_items_ref`) luôn **normalize `items.slug.field` → `slug__field`** (namespace FLAT) trước khi compile — module validate mới bắt buộc làm y hệt.

### File mới: `alumglass/al_bom_engine/formula_validate.py`

Module dùng chung (mà hướng dẫn cũ có nhắc tới nhưng **chưa từng tồn tại thật** trong repo — giờ tạo thật, đúng theo hành vi engine thật):
- `ALUMGLASS_CUSTOM_FUNCS` / `VALIDATOR_ALLOWED_FUNCS` — whitelist hàm custom
- `normalize_cross_row(expr)` — dùng đúng `formula_builder.table_formula_builder.normalize_global` (không tự viết lại regex riêng, tránh lệch pha với engine thật)
- `build_known_names(doctype, docname, cross_row_slugs, cross_row_fields)` — universe biến hợp lệ, tự động bổ sung `{slug}__{field}` khi có cross-row
- `check_formula()` / `check_formula_fields()` — validate, trả list lỗi (không tự throw — caller quyết định throw/msgprint)

### Wiring theo doctype

- **`al_bom_item.py`**: thêm `FORMULA_FIELDS = ("width","height","qty","show_condition")`, `CONDITION_FORMULA_FIELDS`; thêm regex check format `rule_input_expr` (field này KHÔNG qua FormulaValidator vì không phải cú pháp biểu thức — chỉ được `bom_orchestrator` parse bằng regex).
- **`al_bom_set.py`**: `_validate_child_formulas()` — build `known_names` **1 lần** (không trong loop, tránh N+1 query), validate toàn bộ dòng, `frappe.throw()` cứng vì doctype này **chưa có lớp chặn client nào** trước đây.
- **`al_accessory_set.py`** (trước đây `pass` trơn): validate `qty_formula` từng dòng.
- **`al_alert_config.py`** (trước đây `pass` trơn): validate `trigger_condition`.
- **`formula_setup.js`**: thêm block `frappe.ui.form.on("AL Accessory Set", ...)` — autocomplete cho `qty_formula` (trước đây hoàn toàn không có, kể cả client).

---

## PHẦN C — Rà soát & sửa hardcode (Zero hardcode, data-driven qua DB)

| # | Hardcode phát hiện | File / dòng gốc | Sửa thành |
|---|---|---|---|
| C1 | `"Standard Selling"` cứng 2 chỗ trong `bom_orchestrator.py`, nhưng **configurable** ở `fb_handlers.py` (`cfg.get("price_list", ...)`) | `bom_orchestrator.py` (2 vị trí Item Price query) | Hàm mới `_default_price_list()` đọc `Selling Settings.selling_price_list` (chuẩn Frappe/ERPNext có sẵn), fallback "Standard Selling" |
| C2 | `"calc_pattern": "COUNT"`, `"cost_bucket": "VL_PK"` ép **mọi** dòng phụ kiện | `bom_orchestrator.py::_load_accessories()` | Đọc `acc.get("calc_pattern")`/`acc.get("cost_bucket")` — field mới trên `AL Accessory Item`, bỏ trống = giữ hành vi cũ (backward-compat) |
| C3 | `self.cost_result.get("GIA_VAT", 0)` — giả định CHẾT tên `line_code` cuối cùng | `bom_orchestrator.py` (cuối `b6_calculate_cost_template`) | Field mới `is_final_price` (Check) trên `AL Cost Template Item`; `_resolve_final_price()` đọc dòng đánh dấu, fallback `"GIA_VAT"` nếu chưa gắn cờ |
| C4 | Doctype allowlist `("AL Bom Set","AL BOM","AL Bom Engine")` lặp 2 nơi trong `api/__init__.py`, hướng dẫn cũ dạy sửa tay mỗi khi thêm doctype mới | `api/__init__.py::get_formula_context` + `_inject_variable_set_vars` | Hàm mới `_resolve_variable_set_name()` tự dò field `Link → AL Variable Set` (hoặc `Link → AL Bom Set` làm trung gian) qua `frappe.get_meta()` — thêm doctype mới = thêm đúng 1 field Link, **không sửa code** |
| C5 | `OPTIONAL_DIMENSIONS = ["aluminum_color", ...]` hardcode 4 tên biến nhôm trong dialog | `quotation.js::_var_to_field` | Server trả cờ `is_pricing_dimension` (từ chính bảng `AL Variable Dimension Mapping` đã tồn tại) — áp dụng tự động cho dimension kính hay bất kỳ vật tư nào thêm sau |
| C6 | `ALUMGLASS_CUSTOM_FUNCS`/`customFns` lặp tay 3 nơi (`al_cost_template.py` cũ, `cost_template.js`, và nay `formula_validate.py`) | rải rác | API mới `alumglass.api.get_allowed_formula_functions()` — nguồn DUY NHẤT là `formula_validate.ALUMGLASS_CUSTOM_FUNCS`; `cost_template.js::validateViaFB` fetch động (cache 1 lần/session) thay vì hardcode `Set([...])` |
| C7 | AL Cost Template có 3 handler `refresh` chồng chéo, 2 nút "Preview"/"Preview Calculation" trùng | `cost_template.js` + `al_cost_template.js` + `formula_setup.js` | Gộp về `al_cost_template.js` là nơi DUY NHẤT gọi `injectContext` + nút `"Preview"`; xóa hẳn block `refresh` trùng trong `cost_template.js` (giữ nguyên object `alumglass.CostTemplate` làm thư viện) |
| C8 | File chết `bom_set_context.js` — không có trong `app_include_js`, không ai reference | `public/js/bom_set_context.js` | **Xóa file này** (không có trong package — tự `git rm alumglass/public/js/bom_set_context.js` ở app thật) |
| C9 | 6 doctype có field công thức (`AL Bom Set`, `AL Accessory Set`, `AL Cost Template`, `AL Alert Config`, `AL Quantity Calc Method`, `Formula Global Variable`) mỗi doctype viết 1 block `frappe.ui.form.on(doctype, {refresh...})` RIÊNG trong `formula_setup.js`, lặp lại y hệt boilerplate `fetch()` + `initGridField`/`patchField` | `formula_setup.js` (toàn bộ phần "DOCTYPE SETUP") | Gộp về **1 mảng cấu hình** `FORMULA_DOCTYPE_REGISTRY` + **1 vòng lặp `forEach` đăng ký duy nhất**. Thêm doctype/field công thức mới = thêm 1 object vào mảng, KHÔNG viết `frappe.ui.form.on()` nào nữa. Riêng `AL Bom Item`'s `_repatchDependsOnFormulaFields` (xử lý event `item_selection_mode`, không phải `refresh`) vẫn giữ block riêng — vì nó làm việc KHÁC (re-patch Monaco khi field ẩn/hiện), không phải trùng lặp cùng 1 việc |

> **Lưu ý về C7 vs C9 — 2 tầng khác nhau, không mâu thuẫn:** C7 xử lý phần **known_names cache riêng cho validate + nút Preview** của AL Cost Template (`al_cost_template.js`/`cost_template.js`) — việc này đặc thù cho đúng 1 doctype, không tổng quát hoá được (mỗi doctype cần logic validate khác nhau). C9 xử lý phần **bật autocomplete Monaco editor** (`formula_setup.js`) — việc này giống hệt nhau ở mọi doctype nên gộp được về 1 registry dùng chung. AL Cost Template sau khi áp cả 2 bản vá có: 1 entry trong `FORMULA_DOCTYPE_REGISTRY` (autocomplete) + 1 block riêng trong `al_cost_template.js` (known_names cache + nút Preview) — đây là 2 CONCERN khác nhau, không phải trùng lặp còn sót.

---

## Lưu ý JSON

2 file JSON trong package (`al_accessory_item.json`, `al_cost_template_item.json`) chỉ thêm field mới vào `field_order` + `fields` — **không đổi field cũ nào**. Đã kiểm tra JSON hợp lệ (`json.load` pass). Sau khi copy đè, chạy `bench migrate` để Frappe tạo cột DB mới cho field vừa thêm.

Nếu app thật của bạn đã chỉnh sửa 2 file JSON này khác với bản gốc đã rà soát (vd thêm field khác), **đừng copy đè trực tiếp** — mở Doctype Builder và thêm thủ công các field sau:

**AL Accessory Item** (child table): `calc_pattern` (Link → AL Quantity Calc Method), `cost_bucket` (Link → AL Cost Bucket) — cả 2 optional, đặt sau `qty_formula`.

**AL Cost Template Item** (child table): `is_final_price` (Check, default 0) — đặt sau `is_subtotal`.

---

## Checklist test sau khi áp patch

```
[ ] bench --site <site> migrate
[ ] bench --site <site> run-tests --app alumglass --module alumglass.tests.test_bom_orchestrator
[ ] bench --site <site> run-tests --app alumglass --module alumglass.tests.test_composite_pricing
[ ] bench --site <site> run-tests --app alumglass --module alumglass.tests.test_pricing_dimension_snapshot
[ ] python -m pytest standalone_tests/test_phase_b_fbmax.py -k composite_match
[ ] Golden case CDMQ-2C/4C — chạy lại, xác nhận KHÔNG lệch số

--- Test tay: Kính đa vị trí (Phần A) ---
[ ] Dialog Quotation: đổi kính vị trí "Kính trên" khác kính vị trí "Kính dưới"
    → mở BOM preview → xác nhận CẢ 2 vị trí tra ĐÚNG giá riêng
[ ] Xác nhận nẹp kính mỗi vị trí tra ĐÚNG độ dày kính riêng (không bị 1 mã
    global đè lên cả 2 — đây chính là lỗi đã sửa)

--- Test tay: Validate công thức (Phần B) ---
[ ] AL Bom Set: gõ "witdh" (typo) vào field width 1 dòng → save → throw
    "Biến không khai báo: witdh" NGAY khi save
[ ] AL Bom Set: field width dùng "items.kinh_tren.width" (cross-row hợp lệ,
    kinh_tren là slug có thật) → save → PHẢI qua được (không bị từ chối vì
    .attr — điểm hay vỡ nếu làm sai theo hướng dẫn cũ)
[ ] AL Accessory Set: gõ qty_formula sai biến → save → throw
[ ] AL Alert Config: gõ trigger_condition sai biến → save → throw
[ ] AL Cost Template: sửa 1 công thức có lỗi hàm lạ → xác nhận
    validateViaFB vẫn hoạt động đúng (đã đổi sang fetch customFns động)

--- Test tay: Hardcode (Phần C) ---
[ ] Đổi Selling Settings > Selling Price List sang bảng giá khác → xác nhận
    bom_orchestrator dùng đúng bảng giá mới
[ ] Thêm 1 AL Accessory Item có cost_bucket khác VL_PK → xác nhận vào đúng
    bucket đã chọn
[ ] Tạo 1 Cost Template KHÔNG có dòng line_code="GIA_VAT" nhưng có 1 dòng
    is_final_price=1 tên khác → xác nhận al_gia_vat lấy đúng dòng đó
[ ] AL Cost Template: xác nhận CHỈ còn đúng 1 nút "Preview" (không còn
    "Preview Calculation" trùng)
[ ] Mở F12 Console trên form AL Quantity Calc Method hoặc Formula Global
    Variable → gõ 1 ký tự trong field công thức → autocomplete vẫn xuất
    hiện đúng như trước (xác nhận registry gộp không làm mất tính năng ở
    các doctype không phải AL Cost Template)

--- Test tay: Workflow thật (Phần E) ---
[ ] bench --site <site> migrate → kiểm tra 4 Role mới xuất hiện (Role List)
    và 4 Workflow mới xuất hiện (Workflow List), is_active=1
[ ] Gán role "AL BOM Manager" cho 1 user test → mở AL BOM Version Draft →
    xác nhận thấy nút "Gửi duyệt", KHÔNG thấy nút "Duyệt"/"Phát hành"
[ ] Gán thêm role "AL BOM Approver" → mở lại record đang Pending Approval →
    xác nhận thấy nút "Duyệt"/"Từ chối"
[ ] AL Change Order: để trống customer_approval → chuyển Pending → xác nhận
    nút "Duyệt" KHÔNG hiện (do condition chưa thỏa) → tick đủ 2 approval →
    nút "Duyệt" hiện lại
[ ] AL Design Revision: user có role "AL Design Reviewer" bấm "Duyệt" (với
    requires_new_bom_version=1) → xác nhận AL BOM Version mới được tạo
    THÀNH CÔNG (không bị PermissionError dù role này không có quyền create
    trực tiếp trên AL BOM Version)

--- Test tay: FVB single-source (Phần F) ---
[ ] Mở AL Bom Set đã chọn Profile System + Product Type → F12 Console →
    gõ 1 ký tự trong field công thức → xác nhận autocomplete hiện ĐÚNG giá
    trị hiện tại của OFFSET_FRAME/NC_SX_PCT/... (khớp với giá trị thật trên
    Profile System/Product Type đã chọn)
[ ] Đổi giá trị `nc_pct` trên 1 AL Product Type → mở lại AL Bom Set dùng
    Product Type đó → xác nhận preview autocomplete cập nhật theo giá trị
    mới NGAY (không cần sửa code, không cần chạy patch lại — vì giờ đọc
    thẳng field DB qua FVB, không còn cache hardcode nào)
[ ] Xóa alumglass/public/js/bom_set_context.js khỏi repo thật, xác nhận
    không có lỗi console nào liên quan
```

---

## Đề xuất bổ sung (chưa triển khai code — cân nhắc theo mức độ ưu tiên)

Những điểm dưới đây **không phải hardcode gây sai lệch số liệu** như Phần C,
nhưng vẫn là nơi có thể data-driven hoá thêm nếu bạn muốn triệt để 100%
nguyên tắc "mọi thứ setting trong DB":

### D1. Row Literals / Common BOM Variables vẫn là list cố định trong code
`api/__init__.py::get_formula_context()` — mục "5. Row Literals" (`weight_per_unit`, `unit_price`, `glass_thick`...) và "6. Common BOM Variables" (`W_mm`, `H_mm`, `n_panel`...) là 2 list Python cố định, không đọc từ DB.

**Đánh giá:** đây là **schema kỹ thuật của chính engine** (engine LUÔN inject đúng các tên này ở B2/B4, không phải business config người dùng chỉnh sửa được) — khác bản chất với Cost Bucket/Variable Library (business data). Đề xuất: **giữ nguyên dạng code**, vì biến thành DB-driven ở đây tạo rủi ro mismatch giữa "tên biến DB khai báo" và "tên biến engine thực sự inject" — một dạng hardcode-ngầm mới còn nguy hiểm hơn. Chỉ nên data-driven hoá nếu có nhu cầu thực tế thêm Row Literal mới thường xuyên.

### D2. `GIA_BAN` (giá trước VAT) vẫn hardcode tương tự `GIA_VAT` cũ
`bom_orchestrator.py` dòng cuối `b7_save_results`: `"al_gia_ban": self.cost_result.get("GIA_BAN", 0)`. Cùng bản chất hardcode với C3 nhưng **không nằm trong phạm vi yêu cầu ban đầu** nên chưa sửa. Nếu muốn triệt để, có thể thêm field thứ 2 kiểu `Select` (`none/is_pre_vat_price/is_final_price`) thay vì 2 Check riêng, hoặc đơn giản thêm field `is_pre_vat_price` (Check) tương tự C3.

### D3. `AL Variable Dimension Mapping.material_category` là Link đơn — 1 biến chỉ gắn được 1 category
Hiện tại 1 mapping record chỉ áp dụng cho đúng 1 `material_category`. Nếu sau này có dimension dùng chung cho NHIỀU category (vd "độ dày" áp dụng cho cả kính lẫn nhôm tấm), phải tạo N record trùng variable_name khác category — không sai nhưng hơi dư thừa dữ liệu. Có thể cân nhắc đổi `material_category` thành child table multi-select nếu nhu cầu này phát sinh thực tế — **chưa cần thiết ở quy mô hiện tại**, chỉ ghi nhận.

### D4. `_ALLOWED_ATTRS` của `FormulaValidator` (`get/keys/values/items/to_dict`) nằm trong repo Formula-Builder, ngoài phạm vi AlumGlass
Đây là whitelist cứng trong thư viện lõi (không phải AlumGlass), việc mở rộng (nếu cần cho phép thêm `.attr` nào đó) phải sửa ở repo `Formula-Builder`, không sửa được từ phía AlumGlass. Ghi nhận để bạn biết ranh giới sửa được/không sửa được giữa 2 repo.

### D5. Cân nhắc gộp cache `alumglass.CostTemplate._contextCache` với `alumglass.FormulaContext._cache`
Đã nêu trong hướng dẫn cũ (mục 5.1) nhưng chưa triển khai ở bản vá này (rủi ro cao hơn lợi ích ở quy mô hiện tại — 2 cache phục vụ 2 mục đích hơi khác nhau: 1 cho autocomplete Monaco, 1 cho known_names validate + Preview). Để dành cho đợt dọn nợ kỹ thuật riêng nếu cần.

---

## PHẦN E — Workflow thật thay "workflow_state" tự chế (V6 P11)

### File mới: `alumglass/setup/setup_workflows.py`

4 doctype trước đây tự chế state machine bằng Select field + `if self.workflow_state == "X"` rải rác trong code (`AL BOM Version`, `AL Change Order`, `AL Dynamic Item Rule Version`, `AL Design Revision`) — giờ chuyển sang dùng đúng doctype `Workflow` của Frappe (data-driven 100%, sửa luật qua UI Workflow Builder, không cần sửa code).

**Thiết kế maker-checker** (người tạo ≠ người duyệt) — 4 role duyệt MỚI, tách biệt role editor đã có sẵn (`AL BOM Manager`, `AL Site Engineer` — cấp qua `install_roles.py` theo module, không đụng):

| Doctype | Role editor (đã có) | Role duyệt (mới) | States |
|---|---|---|---|
| AL BOM Version | AL BOM Manager | **AL BOM Approver** | Draft → Pending Approval → Approved → Published → Retired |
| AL Change Order | AL Site Engineer | **AL Construction Manager** | Draft → Pending → Approved/Rejected → Implemented |
| AL Dynamic Item Rule Version | AL BOM Manager | **AL Formula Rule Approver** | Draft → Approved → Published → Retired |
| AL Design Revision | AL BOM Manager | **AL Design Reviewer** | Draft → Under Review → Approved → Implemented |

Change Order transition Pending→Approved có `condition: "doc.customer_approval and doc.internal_approval"` — khớp đúng logic đã có trong `validate()`, giờ ẨN LUÔN nút nếu chưa đủ 2 chữ ký (UX tốt hơn để user bấm rồi mới bị throw). `validate()` vẫn giữ nguyên làm lớp chặn thứ 2.

⚠ **Lưu ý kỹ thuật quan trọng**: `Workflow Document State.allow_edit` là Link ĐƠN tới 1 Role (không multi-value) — state "Draft" để `allow_edit` RỖNG, dựa vào DocPerm gốc (đã đúng role editor từ trước) thay vì khoá thêm ở tầng Workflow.

⚠ **Rủi ro đã rà và vá kèm**: `AL Design Revision._create_new_bom_version()` tự động tạo `AL BOM Version` mới khi Duyệt — nhưng role duyệt (`AL Design Reviewer`) KHÔNG có quyền `create` trên `AL BOM Version` (đúng chủ ý). Đã thêm `ignore_permissions=True` vào đúng chỗ insert tự động này (`al_design_revision.py`) để không bị chặn — đây là hệ quả tự động của hành động Duyệt, không phải user chủ động tạo. `create_bom_version_doc()` (al_bom.py) và luồng seed data đã có `ignore_permissions=True` từ trước, không cần sửa.

**Hook vào**: `hooks.py::_after_install` và `_after_migrate` (đúng pattern `install_roles_and_permissions()` đã có) — gọi `install_workflows()`, idempotent (bỏ qua Workflow đã tồn tại, không ghi đè tuỳ chỉnh của bạn qua Workflow Builder UI sau khi cài).

---

## PHẦN F — Tổng quát hoá `_resolve_doc_values` bằng Formula Variable Binding (V6 P11)

### Phát hiện quan trọng khi kiểm tra kiến trúc `formula_builder` ↔ `alumglass`

`formula_builder` **đã là engine tổng quát đúng nghĩa** — không hề hardcode business logic của alumglass (đã grep xác nhận: 0 chữ "alumglass"/"AL Bom" trong code thực thi của formula_builder, chỉ có trong docstring ví dụ). Cơ chế `Formula Variable Binding` (FVB, `source_type="linked_doctype_field"`) đã tồn tại sẵn trong formula_builder, và **đã được alumglass seed dữ liệu** qua `patches/v28_9/seed_fvb_from_variable_library.py` — bao gồm ĐÚNG mapping mà `_resolve_doc_values()` đang hardcode lại (`OFFSET_FRAME` từ `AL Profile System.offset_frame`, `NC_SX_PCT` từ `AL Product Type.nc_pct`...).

**Kết luận kiến trúc: KHÔNG cần chuyển thêm gì vào formula_builder — ranh giới hiện tại đã đúng** (formula_builder = cơ chế tổng quát + registry mở rộng qua `fb_source_types`; alumglass = dữ liệu binding + handler nghiệp vụ riêng như `aluminum_price_composite`). Vấn đề thật chỉ là: `_resolve_doc_values()` (phục vụ preview giá trị trong autocomplete) bị bỏ sót trong đợt migrate sang FVB, vẫn giữ 1 bản hardcode riêng — **2 nguồn dữ liệu cho cùng 1 sự thật**, trong khi `bom_orchestrator.py` (engine tính giá THẬT) đã đúng chuẩn đọc FVB qua `_resolve_fb_context()` từ trước.

### Sửa

`alumglass/api/__init__.py::_resolve_doc_values()` — bỏ hoàn toàn hardcode `doctype == "AL Bom Set"` + hardcode mapping field→biến, thay bằng đọc trực tiếp bản ghi FVB (`source_type="linked_doctype_field"`, lọc theo `applies_to_doctype`) — tự động áp dụng cho MỌI doctype/biến đã có FVB, không cần sửa code khi thêm mapping mới (chỉ cần thêm 1 FVB record).

`get_bom_meta()` mục 2b (dòng ~694) — cùng 1 lỗi trùng lặp, cùng file — đã gộp về gọi `_resolve_doc_values()` thay vì tự lặp lại mapping offset_* riêng; vẫn giữ nguyên lớp 1 (child table `system_variables`, linh động theo TỪNG record Profile System — đây là dữ liệu khác, không trùng với FVB) làm ưu tiên cao hơn.

**Chưa động tới** (cân nhắc thêm nếu bạn muốn triệt để hơn): `bom_orchestrator.py::_resolve_system_variables()` (đọc `AL Profile System Variable` child table trực tiếp làm fallback khi FVB chưa phủ hết) — đây LÀ fallback có chủ đích, đã đúng thứ tự ưu tiên (FVB trước qua `_resolve_fb_context()`, fallback này chỉ chạy khi FVB thiếu), không phải duplication cần dọn ngay.
