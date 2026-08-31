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
                                          # + tự cài Workflow (hooks._after_migrate)
3. bench --site <site> clear-cache
4. Restart bench (để nạp lại api/__init__.py, bom_orchestrator.py mới)
5. Chạy checklist test ở cuối tài liệu này (gồm cả mục "Phần D" bổ sung)
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

⚠ **Patch đã đăng ký sẵn:** gói này (bản bổ sung lượt 2) đã kèm theo file
`alumglass/patches.txt` đầy đủ (copy từ bản gốc + thêm dòng
`alumglass.patches.v28_10.rebackfill_snapshot_category_final_price` vào
`[post_model_sync]`) — copy đè trực tiếp, không cần tự thêm tay nữa. Nếu app
thật của bạn đã có patch riêng khác trong `patches.txt`, hãy MERGE tay thay
vì copy đè (so sánh 2 file trước khi ghi đè).

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
[ ] Xóa alumglass/public/js/bom_set_context.js khỏi repo thật, xác nhận
    không có lỗi console nào liên quan
```

---

## Đề xuất bổ sung (chưa triển khai code — cân nhắc theo mức độ ưu tiên)

Những điểm dưới đây **không phải hardcode gây sai lệch số liệu** như Phần C,
nhưng vẫn là nơi có thể data-driven hoá thêm nếu bạn muốn triệt để 100%
nguyên tắc "mọi thứ setting trong DB":

### D6. Row Literals / Common BOM Variables vẫn là list cố định trong code
`api/__init__.py::get_formula_context()` — mục "5. Row Literals" (`weight_per_unit`, `unit_price`, `glass_thick`...) và "6. Common BOM Variables" (`W_mm`, `H_mm`, `n_panel`...) là 2 list Python cố định, không đọc từ DB.

**Đánh giá:** đây là **schema kỹ thuật của chính engine** (engine LUÔN inject đúng các tên này ở B2/B4, không phải business config người dùng chỉnh sửa được) — khác bản chất với Cost Bucket/Variable Library (business data). Đề xuất: **giữ nguyên dạng code**, vì biến thành DB-driven ở đây tạo rủi ro mismatch giữa "tên biến DB khai báo" và "tên biến engine thực sự inject" — một dạng hardcode-ngầm mới còn nguy hiểm hơn. Chỉ nên data-driven hoá nếu có nhu cầu thực tế thêm Row Literal mới thường xuyên.

### D7. `GIA_BAN` (giá trước VAT) vẫn hardcode tương tự `GIA_VAT` cũ
`bom_orchestrator.py` dòng cuối `b7_save_results`: `"al_gia_ban": self.cost_result.get("GIA_BAN", 0)`. Cùng bản chất hardcode với C3 nhưng **không nằm trong phạm vi yêu cầu ban đầu** nên chưa sửa. Nếu muốn triệt để, có thể thêm field thứ 2 kiểu `Select` (`none/is_pre_vat_price/is_final_price`) thay vì 2 Check riêng, hoặc đơn giản thêm field `is_pre_vat_price` (Check) tương tự C3.

### D8. `AL Variable Dimension Mapping.material_category` là Link đơn — 1 biến chỉ gắn được 1 category
Hiện tại 1 mapping record chỉ áp dụng cho đúng 1 `material_category`. Nếu sau này có dimension dùng chung cho NHIỀU category (vd "độ dày" áp dụng cho cả kính lẫn nhôm tấm), phải tạo N record trùng variable_name khác category — không sai nhưng hơi dư thừa dữ liệu. Có thể cân nhắc đổi `material_category` thành child table multi-select nếu nhu cầu này phát sinh thực tế — **chưa cần thiết ở quy mô hiện tại**, chỉ ghi nhận.

### D9. `_ALLOWED_ATTRS` của `FormulaValidator` (`get/keys/values/items/to_dict`) nằm trong repo Formula-Builder, ngoài phạm vi AlumGlass
Đây là whitelist cứng trong thư viện lõi (không phải AlumGlass), việc mở rộng (nếu cần cho phép thêm `.attr` nào đó) phải sửa ở repo `Formula-Builder`, không sửa được từ phía AlumGlass. Ghi nhận để bạn biết ranh giới sửa được/không sửa được giữa 2 repo.

### D10. Cân nhắc gộp cache `alumglass.CostTemplate._contextCache` với `alumglass.FormulaContext._cache`
Đã nêu trong hướng dẫn cũ (mục 5.1) nhưng chưa triển khai ở bản vá này (rủi ro cao hơn lợi ích ở quy mô hiện tại — 2 cache phục vụ 2 mục đích hơi khác nhau: 1 cho autocomplete Monaco, 1 cho known_names validate + Preview). Để dành cho đợt dọn nợ kỹ thuật riêng nếu cần.

---

## PHẦN D — Workflow thật + generalize `_resolve_doc_values` (bổ sung lượt 2)

Đọc trực tiếp code thật trong chính gói patch này (không suy đoán) trước khi sửa — 2 mục dưới đây độc lập với Phần A/B/C ở trên (không đụng file nào Phần A/B/C đã sửa, trừ 2 hàm được nêu rõ).

### D11. Workflow thật thay `workflow_state` Select tự chế

**Vấn đề xác nhận bằng grep trực tiếp:** 4 doctype (`AL BOM Version`, `AL Change Order`, `AL Dynamic Item Rule Version`, `AL Design Revision`) dùng field `workflow_state` kiểu `Select` thường — không có bất kỳ role/permission gating nào ở tầng transition (ai có quyền write doctype đều sửa trực tiếp field này sang giá trị bất kỳ, kể cả nhảy cóc bỏ qua bước duyệt). Enforcement cũ chỉ có ở  vài `if self.workflow_state == "...": frappe.throw(...)` — đây là RÀNG BUỘC DỮ LIỆU (business rule), không phải ai-được-phép-chuyển-trạng-thái.

**File mới:** `alumglass/setup/install_workflows.py` — khai báo `WORKFLOWS` (list dict thuần data, không if/else) cho cả 4 doctype, dùng đúng 5 role có sẵn trong `install_roles.py` (`AL BOM Manager`, `AL Technical Admin`, `AL Site Engineer`, `AL Sales User`). Mỗi doctype có States (`allow_edit` theo role) + Transitions (`allowed` theo role, có `condition` khi cần).

**Điểm quan trọng — KHÔNG đổi business logic hiện có:**
- `al_bom_version.py` (`_guard_published_immutability`, sync `current_version`, snapshot side-effect) — **giữ nguyên 100%**, vì Workflow transition chỉ set field + gọi `doc.save()` như thao tác save bình thường → `validate()`/`on_update()` vẫn chạy y hệt.
- `al_design_revision.py` (`_create_new_bom_version` khi Approved→Implemented) — **giữ nguyên**, cùng lý do.
- `al_change_order.py::validate()` (check `customer_approval`/`internal_approval`) — **giữ nguyên làm lưới an toàn backend**. Bổ sung thêm `condition: "doc.customer_approval and doc.internal_approval"` ở transition Pending→Approved trong `install_workflows.py` — đây là lớp UX (ẩn hẳn nút "Approve" tới khi đủ điều kiện, thay vì cho bấm rồi mới throw lỗi), 2 lớp bổ trợ nhau chứ không trùng lặp thật (1 lớp là declarative UI gate, 1 lớp là data-integrity check độc lập UI).

**Wiring:** `hooks.py::_after_install` + `hooks.py::_after_migrate` gọi `install_workflows()` (idempotent — xóa & tạo lại Workflow record mỗi lần, an toàn vì Workflow chỉ lưu CẤU HÌNH transition, không đụng `workflow_state` hiện tại của document nào cả).

**Bạn cần xác nhận/điều chỉnh:** role gán cho từng transition trong `WORKFLOWS` là suy luận hợp lý từ tên role có sẵn (vd "AL Technical Admin" duyệt AL BOM Version vì role này đã độc quyền sửa `calc_fn` — cùng mức độ nhạy cảm). Nếu quy trình duyệt thực tế của bạn khác, sửa trực tiếp trong `install_workflows.py::WORKFLOWS` (thuần data, không cần hiểu code) hoặc sau khi `bench migrate` xong, vào UI `Workflow` doctype chỉnh tay — cả 2 cách đều được, đây chính là lợi ích của "workflow thật".

### D12. Generalize `_resolve_doc_values` — phát hiện thêm 1 bug thật khi sửa

**Phát hiện giữa chừng thay đổi hướng sửa:** Dự định ban đầu là tạo 1 doctype mapping mới (giống style `AL Variable Dimension Mapping`), nhưng đọc kỹ `bom_orchestrator.py::_resolve_system_variables()` phát hiện **cơ chế này đã tồn tại sẵn** — `AL Variable Library` đã có field `source_doctype`/`source_field`, cộng thêm override qua child table `AL Profile System.system_variables` (đã có patch backfill `v28_9/backfill_profile_system_variables.py` chạy trước đó). Tạo doctype mới sẽ là **trùng lặp cơ chế** — đúng thứ bạn yêu cầu tránh. Đã đổi hướng: dùng lại đúng cơ chế có sẵn, chỉ tách phần dùng chung.

**Bug thật tìm được khi đối chiếu 2 nơi:** `_resolve_doc_values()` (cũ) hardcode
```python
for f in ["offset_frame", "offset_glass", "offset_fixed", "offset_crossbar"]:
    vals[f.upper()] = ps.get(f)
```
`"offset_crossbar".upper()` = `"OFFSET_CROSSBAR"`. Nhưng đối chiếu seed data (`seed_demo_data.py` dòng 231) và chính công thức đang seed (`do_ngang`: `"W_mm - 2*OFFSET_DO_NGANG"`), tên biến THẬT là `OFFSET_DO_NGANG` (khai báo trong `AL Variable Library`, `source_field="offset_crossbar"` nhưng `var_name="OFFSET_DO_NGANG"` — 2 tên khác hẳn nhau, không chỉ viết hoa). Autocomplete cũ từng hiện 1 biến `OFFSET_CROSSBAR` có giá trị nhưng **không dùng được trong công thức thật** (công thức dùng `OFFSET_DO_NGANG`) — gây nhầm lẫn khi người dùng gõ công thức dựa theo gợi ý autocomplete.

**File mới:** `alumglass/al_bom_engine/system_variable_resolver.py` — 2 hàm thuần (`resolve_source_record_names`, `resolve_system_variable_values`), KHÔNG hardcode tên doctype nào (tự dò field Link qua `frappe.get_meta()`, giống hệt cách `_resolve_variable_set_name` đã làm cho Variable Set).

**File sửa:**
- `api/__init__.py::_resolve_doc_values()` — xóa toàn bộ hardcode cũ, gọi lại module trên. Giờ tên biến autocomplete hiện ra LUÔN khớp tên biến dùng được trong công thức thật (cùng 1 nguồn).
- `engine/bom_orchestrator.py::_resolve_system_variables()` — thay `source_records = {"AL Profile System": ..., "AL Product Type": ...}` (hardcode 2 key cứng) bằng gọi `resolve_source_record_names("AL Bom Set", bom_set.name, system_vars)` (tự dò), giữ nguyên override `self.profile_system_override` (V6 P4) + 2 lớp fallback runtime cũ (`default_value`, `AL Calculation Rule CONSTANT`) — 2 fallback này KHÔNG chuyển vào module dùng chung vì đặc thù runtime tính BOM, không phù hợp cho hàm preview 1-shot.

**Kết quả:** thêm 1 System Variable mới trỏ `source_doctype` khác (vd `AL Color Standard`) = chỉ cần thêm field Link tương ứng trên `AL Bom Set` (hoặc bất kỳ doctype nào khác muốn dùng) + 1 record `AL Variable Library` — không sửa code ở cả 2 nơi (autocomplete lẫn tính toán thật) nữa.

### Checklist test bổ sung (Phần D)

```
--- Test tay: Workflow thật ---
[ ] bench migrate xong → mở AL BOM Version bất kỳ (Draft) → xác nhận CHỈ
    thấy nút "Submit for Approval" (không sửa trực tiếp field workflow_state
    trong 1 Select dropdown như trước)
[ ] Đăng nhập user KHÔNG có role AL Technical Admin → mở 1 AL BOM Version ở
    trạng thái "Pending Approval" → xác nhận KHÔNG thấy nút "Approve"
[ ] AL Change Order: tạo mới, để trống customer_approval → chuyển Pending →
    xác nhận nút "Approve" KHÔNG hiện (do condition) → tick đủ 2 approval →
    nút "Approve" xuất hiện
[ ] AL Design Revision: Approve → Implemented → xác nhận vẫn tự tạo BOM
    Version mới như hành vi cũ (business logic không đổi)
[ ] Vào Workflow List (System Manager) → xác nhận thấy đúng 4 Workflow mới,
    tự chỉnh sửa role 1 transition bất kỳ qua UI → xác nhận áp dụng ngay
    không cần deploy code

--- Test tay: _resolve_doc_values ---
[ ] Mở AL Bom Set có profile_system đã gán → F12 Console → gõ 1 ký tự vào
    field width → xác nhận autocomplete hiện đúng OFFSET_DO_NGANG (KHÔNG
    còn OFFSET_CROSSBAR) với giá trị đúng bằng offset_crossbar của Profile
    System đó
[ ] Xác nhận NC_SX_PCT/NC_LD_PCT/PROFIT_MARGIN vẫn hiện đúng giá trị như
    trước (không regression)
[ ] Nếu AL Profile System có override trong system_variables (child table)
    cho OFFSET_DO_NGANG → xác nhận autocomplete hiện ĐÚNG giá trị override
    (không phải giá trị field offset_crossbar gốc)
[ ] Chạy lại golden CDMQ-2C/4C — xác nhận KHÔNG lệch số (bom_orchestrator
    vẫn tính đúng như cũ, chỉ đổi cách lấy source_records)
```


---

## PHẦN E — Sửa "bước 5" theo nguyên tắc "tận dụng tối đa formula_builder" (lượt 3)

### E1. Bối cảnh

Đề xuất 5.4 ban đầu ("Xử lý rủi ro exact_match vs partial-match") chỉ dừng ở mức thống nhất THUẬT TOÁN giữa 2 nhánh tra giá composite (FB-max và Python fallback) — phần đó đã đúng (`engine/composite_pricing.py::best_partial_match` dùng chung, đã có trong zip trước). Nhưng soát lại theo đúng yêu cầu **"nguyên tắc là tận dụng tối đa formula_builder"** phát hiện 2 vấn đề sâu hơn thuật toán.

### E2. Vấn đề 1 — FB-max không bao giờ thực sự chạy trong vận hành thật

`bom_orchestrator.py::_get_pricing_bindings()` query `Formula Variable Binding` theo `source_type ∈ {composite_key_lookup, aluminum_price_composite}`. Grep xác nhận `composite_key_lookup` không có handler nào đăng ký (dead placeholder). `aluminum_price_composite` có handler đầy đủ trong `fb_handlers.py`, nhưng **không có gì tự tạo binding record này** — phải ai đó tự tay tạo qua UI. Nếu chưa ai làm (thực tế hiện tại) → `_fetch_composite_prices_via_fb()` luôn trả `None` → hệ thống **LUÔN chạy nhánh Python fallback**, dù code FB-max đã viết đầy đủ, đúng, sẵn sàng dùng.

**Fix — file mới `alumglass/setup/install_fb_bindings.py`:**
```python
COMPOSITE_PRICING_BINDING = {
    "variable_name": "COMPOSITE_MATERIAL_PRICE",
    "source_type": "aluminum_price_composite",
    "source_config": {"price_list": "Standard Selling", "pricing_mode": "exact_match"},
    "applies_to_doctype": "",   # global — gọi trực tiếp qua resolve_all_bindings_batch
    "is_global": 1, "is_active": 1, ...
}

def install_composite_pricing_binding():
    # idempotent: update nếu đã tồn tại, insert nếu chưa
    ...
```
Gọi từ `hooks.py::_after_install` VÀ `_after_migrate` — `bench migrate` xong là FB-max chạy thật, không cần thao tác tay D3 nữa.

### E3. Vấn đề 2 — dù bật FB-max, vẫn thiếu context `category` → tái phát bug đã sửa

`_fetch_composite_prices_via_fb()` build `row_ctx` cho từng `item_code` nhưng **không set `row_ctx["category"]`** — trong khi handler `aluminum_price_composite` đọc `resolved_so_far.get("category")` để lọc `AL Variable Dimension Mapping` theo `material_category` (chính fix V6 P10 đã áp cho nhánh fallback ở lượt trước). Nghĩa là nếu bật FB-max (sau khi seed binding ở E2), nó tái phát ĐÚNG bug material_category đã sửa — 2 nhánh cho **kết quả khác nhau tùy nhánh nào đang chạy**, chứ không chỉ khác thuật toán.

**Fix — `alumglass/engine/bom_orchestrator.py`:** tách `_category_by_code()` thành 1 hàm dùng chung (trước chỉ có inline trong `_fetch_composite_prices`), gọi ở CẢ 2 nhánh. `_fetch_composite_prices_via_fb()` giờ set đúng `row_ctx["category"]` + `row_ctx["row"]["category"]`.

### E4. Kết quả

FB-max và fallback giờ **luôn cho cùng 1 kết quả**, không phụ thuộc nhánh nào đang thực thi — đúng tinh thần "formula_builder là nguồn chính, Python fallback chỉ là lưới an toàn dự phòng", không phải 2 con đường độc lập cần bảo trì song song vĩnh viễn. `_fetch_composite_prices()` (fallback) giờ có docstring ghi rõ: về lý thuyết không còn được gọi trong vận hành bình thường sau khi seed xong.

**File mới:** `alumglass/setup/install_fb_bindings.py`
**File sửa:** `alumglass/engine/bom_orchestrator.py` (`_category_by_code` mới, `_fetch_composite_prices_via_fb`, `_fetch_composite_prices`), `alumglass/hooks.py` (nối `install_composite_pricing_binding()`)
**Không đụng:** `AL Variable Dimension Mapping`, `AL Pricing Dimension`, nội dung bên trong `fb_handlers.py::aluminum_price_composite` (logic đã đúng từ trước, chỉ thiếu bên GỌI truyền đủ context).

### Checklist test (Phần E)

```
[ ] bench migrate → Formula Variable Binding list → xác nhận thấy đúng 1
    record "COMPOSITE_MATERIAL_PRICE" (source_type=aluminum_price_composite,
    is_active=1)
[ ] Chạy lại golden CDMQ-2C (22,717,289) / CDMQ-4C (47,430,808) → xác nhận
    KHÔNG lệch số dù giờ chạy qua FB-max thay vì fallback (nếu lệch — tạm
    set is_active=0 cho binding vừa seed để quay về fallback, báo lại)
[ ] Set log tạm trong _fetch_composite_prices_via_fb → xác nhận nó KHÔNG
    còn trả None (đang thực sự được dùng, không rơi về fallback nữa)
[ ] Test 1 BOM có dòng kính (category=KINH) + dòng nhôm (category=NHOM)
    cùng lúc, chạy qua FB-max → xác nhận giá 2 loại KHÔNG bị lẫn dimension
    của nhau (đúng material_category filter, khớp kết quả với fallback cũ)
```
