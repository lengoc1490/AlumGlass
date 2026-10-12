# HƯỚNG DẪN TÍNH GIÁ FULL FLOW — ALUMGLASS × FORMULA BUILDER

> **Mốc code tài liệu này mô tả**
>
> | | |
> |---|---|
> | App | `alumglass` — nhánh `main`, HEAD `ad79edb` (2026-10-10) |
> | Nền tảng | `formula_builder` — nhánh `develop`, HEAD `0ed8e1b` |
> | Đích phiên bản | Frappe/ERPNext **v16** ⚠️ (bench cục bộ có thể là v14 — cây Frappe cài trên máy ⛔ **không phải** nguồn sự thật cho đích phiên bản của app) |
> | Ngày soạn | 2026-10-12 |
> | Phạm vi | Luồng **tính giá 1 dòng báo giá**: từ cú bấm → `BomOrchestrator` B0–B7 → ghi giá vào Quotation |
> | ⛔ Ngoài phạm vi | Duyệt/submit báo giá · in báo giá · MRP · mua hàng · sản xuất |
>
> **Nguồn dẫn chứng:** mọi khẳng định trong tài liệu này đọc trực tiếp từ mã tại 2 mốc trên.
> Dẫn chứng ghi dạng `file:dòng`. Ký hiệu ✅[V] = đã đọc tận dòng code, không suy luận.
>
> ⚠️ **Về số liệu ở §7 / §8:** đây là số của **golden case có thật** (`alumglass/run_test.py`),
> nhưng **chưa chạy lại** trên máy soạn tài liệu — máy này ⛔ không có site nào cài
> `alumglass` + `formula_builder`. Số được lấy từ chính `run_test.py` + lần chạy đã ghi vết ở
> `docs/quotation-pricing-flow.md` §9/§10. Muốn khẳng định lại ⇒ chạy theo §12.2.

---

## Quy ước đọc tài liệu

| Ký hiệu | Nghĩa |
|---|---|
| `tên_hàm()` | hàm trong code |
| `DocType.field` | field của một DocType |
| ⚠️ **Hành vi hiện tại** | điều dễ gây bất ngờ — đọc kỹ trước khi kết luận "hệ thống sai" |
| ✅[V] | đã kiểm trực tiếp trong mã tại mốc nêu trên |
| ⛔ | điều bị cấm / điều KHÔNG xảy ra |

---

## MỤC LỤC

- [§1. Bức tranh một trang](#1-bức-tranh-một-trang)
- [§2. Kiến trúc: 3 tầng và 7 phase](#2-kiến-trúc-3-tầng-và-7-phase)
- [§3. Bản đồ DocType — cái gì nuôi bước nào](#3-bản-đồ-doctype--cái-gì-nuôi-bước-nào)
- [§4. Điểm vào — từ cú bấm tới engine](#4-điểm-vào--từ-cú-bấm-tới-engine)
- [§5. B0 → B7 chi tiết từng bước](#5-b0--b7-chi-tiết-từng-bước)
- [§6. Formula Builder tham gia ở đâu](#6-formula-builder-tham-gia-ở-đâu)
- [§7. Ví dụ 1 — CDMQ-2C, tính từng bước](#7-ví-dụ-1--cdmq-2c-tính-từng-bước)
- [§8. Ví dụ 2 — CDMQ-4C, tính từng bước](#8-ví-dụ-2--cdmq-4c-tính-từng-bước)
- [§9. Checklist cấu hình để một sản phẩm tính được giá](#9-checklist-cấu-hình-để-một-sản-phẩm-tính-được-giá)
- [§10. Xử lý sự cố — triệu chứng → nguyên nhân → cách sửa](#10-xử-lý-sự-cố)
- [§11. Hành vi hiện tại cần biết](#11-hành-vi-hiện-tại-cần-biết)
- [§12. Phụ lục](#12-phụ-lục)

---

## §1. Bức tranh một trang

Tính giá AlumGlass **không** phải một hàm tính tiền. Nó là **7 bước** chạy trên một
`BomOrchestrator`, và **toàn bộ nghiệp vụ nằm trong DB** — engine không biết "cửa đi 2 cánh" là gì.

```
Người dùng bấm "Tính giá" trên 1 dòng Quotation Item
        │
        ▼
alumglass.api.calculate_bom(quotation_item_name)        ← api/__init__.py:7
        │  · kiểm quyền `read` trên Quotation cha
        │  · chốt docstatus (báo giá đã gửi/đã huỷ ⇒ dừng)
        │  · BOM ≤ ngưỡng ⇒ chạy đồng bộ; BOM lớn ⇒ đẩy job nền
        ▼
BomOrchestrator(quotation_item_name).run()              ← engine/bom_orchestrator.py:266
        │
        ├─ B0  Chốt phiên bản BOM (version pinning)
        ├─ B1  Gom biến đầu vào (7 tiểu bước, FB-first)
        ├─ B2  Nạp master data (6 batch query + literal từng dòng)
        ├─ B3  Sinh danh sách công thức          ──┐
        ├─ B4  Tính dòng vật tư  ─────────────────┤ đều giao cho FORMULA BUILDER
        ├─ B5  Gom cost bucket                    │
        ├─ B6  Chạy Cost Template ────────────────┘
        └─ B7  Ghi kết quả (1 commit duy nhất)
        │
        ▼
{alumglass.api.calculate_bom trả} {buckets, cost_template, lines, errors}
        │
        ▼
Quotation Item:  al_gia_vat · al_gia_ban · al_bom_result · rate
Quotation (cha): 13 trường tổng tiền
```

**Ba câu chốt cần nhớ:**

1. **Engine không tính gì bằng Python thuần.** `unit_qty`, `total_qty`, `line_total`, và toàn bộ
   cost template đều do `FormulaEngine` / `FlexibleFormulaEngine` của Formula Builder tính.
   Engine chỉ **dựng chuỗi công thức** rồi **giao cho FB**.
2. **Giá vật tư không nằm trong công thức.** Giá được tra ở B2 theo **composite key**
   (màu × xuất xứ × độ dày × bề mặt) rồi **nhét vào context dưới dạng literal** `{slug}__unit_price`.
3. **Bất biến giá đến từ B0.** Mọi con số lấy từ **snapshot** của `AL BOM Version` đang ghim,
   ⛔ không phải từ cấu hình sống. Đổi Bom Set hôm nay ⛔ không làm đổi giá báo giá đã tính.

---

## §2. Kiến trúc: 3 tầng và 7 phase

### 2.1 Ba tầng

```
┌─ TẦNG 3 — CẤU HÌNH (dữ liệu, không phải code) ───────────────────────────┐
│  AL Bom Set / AL Bom Item        ← hình học & thành phần sản phẩm        │
│  AL Cost Template (Item)         ← công thức giá thành → giá bán         │
│  AL Cost Bucket                  ← nhóm chi phí                          │
│  Item Price (+ custom_pd_*)      ← giá vật tư theo composite key         │
│  AL Variable Library / Profile System / Product Type  ← biến hệ thống    │
│  Formula Global Variable         ← hằng số (VAT, %, ngưỡng async)        │
│  Formula Variable Binding        ← "lấy giá trị thế nào"                 │
│  AL Quantity Calc Method / AL Calculation Rule / AL Dynamic Item Rule    │
└──────────────────────────────┬───────────────────────────────────────────┘
┌─ TẦNG 2 — PLATFORM formula_builder (resolve & tính) ────────────────────┐
│  FormulaEngine                  ← DAG + sắp xếp topo, không gian PHẲNG   │
│  FlexibleFormulaEngine          ← công thức tuần tự, không gian TOÀN CỤC │
│  get_live_context · binding_scope · resolve_all_bindings_batch           │
│  source_type_registry · safe_eval (compile_expression)                   │
└──────────────────────────────┬───────────────────────────────────────────┘
┌─ TẦNG 1 — ENGINE alumglass (điều phối) ─────────────────────────────────┐
│  BomOrchestrator B0→B7 — CHỈ: đọc config → resolve biến → build công    │
│  thức → gọi FB → gom bucket → ghi kết quả. Không chứa nghiệp vụ.        │
└─────────────────────────────────────────────────────────────────────────┘
```

Đọc `engine/bom_orchestrator.py:1-21` — docstring đầu tệp tự khai đúng nguyên tắc này:
*"AlumGlass chỉ config, không hardcode nghiệp vụ."*

### 2.2 Bảy phase

| Phase | Hàm | Việc | Giao cho FB? |
|---|---|---|---|
| **B0** | `b0_version_pinning()` `:280` | Chốt `AL BOM Version` cho dòng báo giá | — |
| **B1** | `b1_gather_inputs()` `:337` | Gom & chuẩn hoá mọi biến đầu vào | ✅ `get_live_context` (1.4) |
| **B2** | `b2_prefetch_master_data()` `:826` | Nạp giá/khối lượng/độ dày/hao hụt, giải rule | ✅ `resolve_all_bindings_batch` (giá composite) |
| **B3** | `b3_build_formulas()` `:1936` | Sinh danh sách công thức `{slug}__{field}` | — (chỉ dựng chuỗi) |
| **B4** | `b4_calculate_bom_items()` `:2150` | Tính từng dòng vật tư | ✅ `FormulaEngine` |
| **B5** | `b5_aggregate_cost_buckets()` `:2278` | Cộng `line_total` theo `cost_bucket` | ✅ nếu bucket khai `aggregate_from_items` |
| **B6** | `b6_calculate_cost_template()` `:2395` | Chạy Cost Template → giá thành → giá bán | ✅ `FlexibleFormulaEngine` |
| **B7** | `b7_save_results()` `:2537` | Ghi DB, 1 commit | — |

`run()` `:266` gọi đúng 8 hàm này theo thứ tự và trả `_build_response()` `:2683`.

---

## §3. Bản đồ DocType — cái gì nuôi bước nào

### 3.1 Bảng lớn

| DocType | Vai trò trong tính giá | Engine đọc ở bước |
|---|---|---|
| **Quotation Item** | Đầu vào thô (biến người dùng nhập) + đầu ra (giá) | B0, B1 (đọc) · B7 (ghi) |
| **AL BOM** | Cầu nối: BOM ↔ Bom Set, và `current_version` | B0, `_get_bom_set` |
| **AL BOM Version** | **Snapshot bất biến** — nguồn duy nhất của hình học & công thức | B0 (chốt), B2 (đọc snapshot) |
| **AL Bom Set** | Khai báo sản phẩm: profile system, product type, variable set, bộ phụ kiện, có bật hao hụt không | B1 (scope FB), B2 (phụ kiện) |
| **AL Bom Item** | **Từng dòng vật tư**: công thức `width/height/qty`, category, calc pattern, cost bucket, rule | B2, B3, B4 |
| **AL Accessory Set / AL Accessory Item** | Bộ phụ kiện (tay nắm, khoá, bản lề) | B2 `_load_accessories()` |
| **AL Cost Template / AL Cost Template Item** | Công thức từ TONG_VL → GIA_VAT | B6 |
| **AL Cost Bucket** | Nhóm chi phí (VL_NHOM, VL_KINH, VL_VTP, VL_PK…) | B5 |
| **Item Price** + custom field `custom_pd_*` | **Giá vật tư** theo composite key | B2 (2 nhánh) |
| **AL Pricing Dimension / AL Variable Dimension Mapping** | Định nghĩa **chiều** của composite key (màu, xuất xứ, độ dày, bề mặt) | B2 |
| **AL Variable Library** | Khai báo biến: hệ thống hay người dùng, nguồn, mặc định | B1 (1.3, 1.6, 1.7) |
| **AL Profile System (+ child `system_variables`)** | Nguồn `OFFSET_*` | B1 (1.3 / 1.4b) |
| **AL Product Type** | Nguồn `NC_SX_PCT`, `NC_LD_PCT`, `PROFIT_MARGIN` | B1 (1.3) |
| **Formula Global Variable** | Hằng số: `VAT_RATE`, `OH_VC_PCT`, `OH_QLY_PCT`, `ASYNC_BOM_THRESHOLD` | B1 (1.2), `_get_async_threshold()` |
| **Formula Variable Binding** | "Lấy giá trị thế nào" — binding cho biến hệ thống và cho giá composite | B1 (1.4), B2, B5 |
| **AL Quantity Calc Method** | Cách tính số lượng: `COUNT`, `AREA_M2`, `LENGTH_TO_WEIGHT`… | B3/B4 (`lookup_calc_pattern`) |
| **AL Calculation Rule** | Bảng tra ngưỡng/hằng số (`RULE-BANLE-QTY`, `RULE-HEIGHT-MULT`…) | B4/B6 (`lookup_rule`) |
| **AL Dynamic Item Rule** | Chọn mã vật tư **theo thuộc tính** (độ dày kính → mã nẹp) | B2 (batch #5) |
| **AL Glass Master** | `total_thick_mm`, `glass_type`, `max_area_m2` của kính | B2 (batch #3) |
| **AL Material Category** | `default_scrap_pct`, `has_weight`, `requires_glass_master` | B2 (batch #4) |
| **AL Color Standard** | Mã màu để tra giá (chiều `MAU_SAC`) + `price_multiplier` (⚠️ **chỉ** dùng ở chế độ `multiplier_chain` — xem §5 B2) | B2 |

### 3.2 `Quotation Item` — đầu vào & đầu ra

**Engine ĐỌC:**

| Field | Ý nghĩa |
|---|---|
| `al_bom` | Link → AL BOM |
| `al_bom_version` | Link → AL BOM Version (nếu đã chốt) |
| `al_bom_vars` | **JSON** — toàn bộ biến người dùng nhập + override config |

**Engine GHI** (`b7_save_results` `:2574`):

| Field | Giá trị ghi |
|---|---|
| `al_gia_vat` | Giá bán **có VAT** (dòng có cờ `is_final_price=1`, fallback `GIA_VAT`) |
| `al_gia_ban` | Giá **trước VAT** (dòng có cờ `is_pre_vat_price=1`, fallback `GIA_BAN`) |
| `al_bom_result` | JSON đầy đủ: `buckets`, `cost_template`, `cost_template_trace`, `lines`, `gia_vat`, `gia_ban`, `errors` |
| `rate` | = `al_gia_ban` ⚠️ **Hành vi hiện tại:** máy chủ ghi luôn `rate` (trước đây chỉ trình duyệt ghi) |

### 3.3 Cấu trúc `al_bom_vars` — JSON trung tâm

Đây là **hợp đồng** giữa dialog và engine (`b1_gather_inputs` `:337-453`):

```jsonc
{
  // (a) biến người dùng nhập — phẳng, mỗi key là 1 biến
  "W_mm": 2400, "H_mm": 2600, "n_panel": 2, "TransomHeight_mm": 600,
  "aluminum_color": "WHITE", "aluminum_origin": "IMPORT",
  "aluminum_thickness": 20, "aluminum_surface": "POWDER_COATED",
  "installation_height_m": 3,

  // (b) biến mở rộng
  "extra_vars": { "ten_bien": 123 },

  // (c) override CONFIG — CHỈ có khi người dùng đổi khác default của BOM
  "_accessory_set":   "ACC-01",         // fallback convention cũ: "accessory_set"
  "_profile_system":  "XINGFA_55",
  "_cost_template":   "CT-01-STANDARD",
  "glass_master":     "KINH-LOWE-24",   // 1 kính cho TOÀN BOM (global, cũ)
  "glass_master_map": { "<rep>": "KINH-8MM" },   // kính theo TỪNG VỊ TRÍ
  "aluminum_color":   "WHITE",
  "color_master_map": { "<rep>": "DARK" }        // màu theo TỪNG VỊ TRÍ
}
```

### 3.4 `AL Bom Item` — các field engine thật sự đọc

Nguồn: `b2_prefetch_master_data` `:826+`, `b3_build_formulas` `:1936+`, `b4` `:2202+`.

| Field | Kiểu | Engine dùng để |
|---|---|---|
| `slug` | Data | **Khoá định danh dòng** — mọi công thức dùng `{slug}__{field}` |
| `item_code` | Link → Item | Mã vật tư mặc định |
| `price_base_item` | Link → Item | ⭐ Mã dùng để **tra giá** (khác `item_code` khi cần) |
| `category` | Link → AL Material Category | Lọc dimension + tra hao hụt + lọc nhóm kính |
| `color_group_category` | Data | Nhóm cho dialog "Màu sắc" (phụ kiện = tag riêng) |
| `default_color` | Link → AL Color Standard | Đại diện nhóm màu của dòng |
| `default_glass_master` | Link → AL Glass Master | Đại diện nhóm kính của dòng |
| `calc_pattern` | Link → AL Quantity Calc Method | Chọn cách tính `unit_qty` |
| `cost_bucket` | Link → AL Cost Bucket | Nhóm chi phí |
| `item_selection_mode` | Select | `Rule` ⇒ chọn mã động |
| `item_rule` | Link → AL Dynamic Item Rule | Rule chọn mã (chỉ khi mode = Rule) |
| `rule_input_expr` | Small Text | Biểu thức tính **đầu vào** cho rule, vd `items.kinh_tren.glass_thick` |
| `width` `height` `qty` | Small Text | **Công thức** (mm / số lượng) — không phải số cứng |
| `show_condition` | Small Text | Công thức điều kiện hiện dòng |
| `item_condition_formula` | Small Text | Công thức điều kiện chọn mã |
| `qty_formula` (accessory) | Small Text | Công thức số lượng cho dòng phụ kiện |
| `input_vars` | JSON | Biến riêng của dòng → `{slug}__{tên}` |
| `supplier_location` `install_position` `cut_angle` `note` | Data | Chỉ để hiển thị (đi thẳng vào `lines[]`) |

⚠️ **Hành vi hiện tại:** danh sách field-nào-là-công-thức lấy từ `AL Bom Set.formula_fieldnames`;
nếu Bom Set không khai, engine dùng mặc định tại `bom_orchestrator.py:208`:

```python
DEFAULT_FORMULA_FIELDS = ["width", "height", "qty", "show_condition",
                          "item_condition_formula", "rule_input_expr"]
```

---

## §4. Điểm vào — từ cú bấm tới engine

### 4.1 Chuỗi gọi

```
[Form Quotation]  nút 📐 "Tham số BOM"  → dialog nhập biến → Lưu vào al_bom_vars
[Form Quotation]  nút 🖥️ "Preview tính giá"  → frappe.call("alumglass.api.calculate_bom", ...)
[Form Quotation]  nút form-level "Tính giá" → quét mọi dòng rồi gọi cùng endpoint
        │
        ▼
alumglass.api.calculate_bom(quotation_item_name)      ← api/__init__.py:7
```

### 4.2 `calculate_bom` làm gì — theo đúng thứ tự

Trích `api/__init__.py:31-51`:

```python
    _require_quotation_item_permission(quotation_item_name, ptype="read")

    from alumglass.engine.bom_orchestrator import assert_quotation_item_editable
    assert_quotation_item_editable(quotation_item_name)

    qi = frappe.get_doc("Quotation Item", quotation_item_name)

    line_count = _estimate_bom_line_count(qi)
    threshold = _get_async_threshold()

    if line_count <= threshold:
        from alumglass.engine.bom_orchestrator import BomOrchestrator
        result = BomOrchestrator(quotation_item_name).run()
        return _normalize_bom_response(result)

    return _enqueue_bom_calculation(qi)
```

| Bước | Việc | Ở đâu |
|---|---|---|
| 1 | Cổng quyền `read` trên **Quotation cha** (Quotation Item là bảng con ⇒ kiểm quyền trên nó vô nghĩa) | `_require_quotation_item_permission()` `:74` |
| 2 | Chốt `docstatus` — báo giá đã gửi/đã huỷ ⇒ **dừng ngay**, chưa tính gì | `assert_quotation_item_editable()` `bom_orchestrator.py:29` |
| 3 | Đếm số dòng BOM từ snapshot (⛔ không dựng engine chỉ để đếm) | `_estimate_bom_line_count()` `:136` |
| 4a | ≤ ngưỡng ⇒ chạy **đồng bộ**, trả `{buckets, cost_template, lines, errors}` | `:44-48` |
| 4b | > ngưỡng ⇒ `frappe.enqueue(queue="long", timeout=600)`, trả `{async, job_id, status}` | `_enqueue_bom_calculation()` `:171` |

Ngưỡng đọc từ `Formula Global Variable.ASYNC_BOM_THRESHOLD` (field `constant_value`),
**mặc định 150** (`:160-168`).

### 4.2b Chạy nền (async) — chi tiết từng bước

Chỉ dùng khi BOM vượt ngưỡng. Chuỗi trạng thái ghi vào `Quotation Item.al_calc_status`:

```
Queued ──► Running ──► Success
                    └─► Failed   (kèm al_calc_error = 1 câu tiếng Việt)
```

| Bước | Việc | Dòng |
|---|---|---|
| 1 | Sinh `job_id = "albom-<tên dòng>-<8 ký tự hash>"` | `:173` |
| 2 | Ghi `Queued` + `al_calc_job_id` + **xoá** `al_calc_error`, rồi **commit NGAY** | `:175-184` |
| 3 | `frappe.enqueue(queue="long", timeout=600, job_name=job_id, user=<người bấm>)` | `:190-198` |
| 4 | Trả `{async: true, job_id, status: "Queued", message: "BOM có {n} dòng — đang tính trong nền, kết quả sẽ hiện tự động khi xong."}` | `:217-224` |
| 5 | *(worker)* `frappe.set_user(user)` → `Running` → commit → `BomOrchestrator(...).run()` → `Success` → commit | `:236-252` |
| 6 | *(worker)* `frappe.publish_realtime("alumglass_bom_calc_done", …, user=user)` — kèm **kết quả đã chuẩn hoá** | `:280-289` |

**Ba chi tiết đã được xử lý kỹ, ⛔ đừng vô tình làm hỏng:**

1. **`frappe.enqueue` nằm TRONG `try`** (`:186-215`, ghi chú `D3`). Nếu Redis/worker chết mà để
   ngoài `try`, dòng báo giá **kẹt `Queued` vĩnh viễn**, `al_calc_error` rỗng, người dùng ⛔ không
   có đường xử lý. Nay: chuyển `Failed` + câu *"Không xếp được việc tính giá vào hàng đợi — vui
   lòng thử lại, nếu vẫn lỗi hãy báo quản trị."* + `log_error` + `throw`.
2. **`frappe.set_user(user)` nằm TRONG `try`** (`:233-237`). Worker mặc định chạy quyền
   **Administrator** — không set_user thì job **bỏ qua toàn bộ role-based access**. Nhưng nếu
   `set_user` ném lỗi (user không hợp lệ) mà lại để ngoài `try` ⇒ dòng kẹt `Queued` mãi.
3. **Ghi trạng thái + commit TRƯỚC khi publish realtime** (`:232`) — để lúc client nhận event thì
   DB đã nhất quán.

**Ai nhận được event:** `user=user` — chỉ phiên của **người đã bấm tính**. ⛔ Không phải broadcast
cho mọi người đang mở báo giá đó.

⚠️ **Mọi lần ghi trạng thái đều dùng `update_modified=False`** (`:182`, `:241`, `:251`, `:260`) —
cố ý: tránh đụng `modified` và gây `TimestampMismatchError` cho người đang mở form.

### 4.3 Gọi engine bằng tay (không qua UI)

```python
# bench --site <site> console
from alumglass.engine.bom_orchestrator import BomOrchestrator
result = BomOrchestrator("<tên Quotation Item>").run()
# → {'buckets': {...}, 'cost_template': {...}, 'lines': [...], 'errors': {...}}
```

Hoặc dựng dữ liệu test rồi gọi API — xem `alumglass/run_test.py:12-32` (tự `INSERT` Quotation +
Quotation Item rồi gọi `calculate_bom`).

⚠️ **Hành vi hiện tại:** chạy `BomOrchestrator.run()` trực tiếp **vẫn ghi DB** — B7 nằm trong
chuỗi `run()`. Muốn xem thử mà không ghi, phải gọi lần lượt `b0`→`b6` thủ công.

### 4.4 Các endpoint whitelist liên quan

| Endpoint | Dòng | Việc |
|---|---|---|
| `calculate_bom(quotation_item_name)` | `:7` | **Điểm vào chính** |
| `preview_cost_template(template_code, inputs_json)` | `:293` | Preview công thức cost template (không ghi DB) |
| `get_result_display(quotation_item_name)` | `:1242` | Đọc lại `al_bom_result` đã lưu để render dialog |
| `get_variable_set_for_bom(bom_code)` | `:737` | Trả biến + nhóm kính/màu cho dialog "Tham số BOM" |
| `get_formula_context(doctype, docname)` | `:437` | Ngữ cảnh biến để autocomplete công thức |
| `get_allowed_formula_functions()` | `:660` | Danh sách hàm được phép dùng trong công thức (JS fetch động) |
| `get_bom_structure(bom_code)` | `:324` | Cấu trúc BOM |
| `get_cost_template_context(template_code)` | `:333` | Ngữ cảnh biến cho cost template |
| `resolve_item_rule(rule_code, input_value)` | `:313` | Tra thử 1 Dynamic Item Rule |
| `get_slug_info(slug)` | `:303` | Thông tin 1 slug |
| `product_item_query(...)` | `:1088` | Query chọn item (link field) |

---

### 4.5 `quotation.js` — lớp UI (2.351 dòng)

**Nạp ở đâu** — `hooks.py:33-36`:

```python
doctype_js = {
    "Quotation": "alumglass/doctype/overrides/quotation.js",
    "Sales Order": "alumglass/doctype/overrides/sales_order.js",
}
```

⛔ Cố ý **không** load toàn trang qua `app_include_js`: chỉ nạp khi mở form Quotation (ghi rõ ở
`quotation.js:1-17`).

**Một tệp gánh 5 nhóm việc:**

| Nhóm | Dòng | Nội dung |
|---|---|---|
| Helper dùng chung | `35-485` | Renderer kết quả + 10 hàm xử lý lỗi/cảnh báo |
| Đồng bộ dòng | `486-550` | `_persist_row()`, `_sync_row_to_db()` |
| `ItemParamDialog` | `551-1682` | Dialog **📐 Tham số BOM** → chi tiết ở §4.8.A |
| `BOMDialog` | `1687-1891` | Dialog kết quả tính giá (🖥️) → chi tiết ở §4.8.B |
| Form event + nút | `1896-2351` | Nút form-level, nút trên dòng, 2 luồng tính hàng loạt |

⚠️ **Ba đường tính/xem giá ⛔ đừng lẫn nhau:**

| Đường | Mở từ đâu | Có GHI giá không |
|---|---|---|
| `ItemParamDialog` | Nút **📐 Tham số BOM** (form con của dòng), icon 📐 ở góc phải cột `item_code`, hoặc **nháy đúp** vào dòng | **Có** — preview **tự động** cũng chạy `calculate_bom` |
| `BOMDialog` | Nút **🖥️ Preview tính giá** trên dòng | **Có** — nhưng chỉ khi dòng **chưa** có kết quả (`al_calc_status ≠ "Success"`) |
| `Preview giá` (form-level) | Nút nhóm **AlumGlass** trên form | ⛔ **Không** — chỉ đọc `get_result_display` |

⚠️ **Không có chế độ "tính thử mà không ghi".** Cả 3 nơi gọi `calculate_bom` (§4.8.C) đều dẫn tới **B7 ghi
giá**; muốn xem **mà không ghi** thì chỉ có `get_result_display` — tức đọc **kết quả đã lưu từ trước**.

---

### 4.6 Renderer dùng chung — `render_bom_result_display(display, opts)`

`quotation.js:35-200`. **Cả 3 đường trên đều đổ về hàm này** (`:1495`, `:1859`, `:2322`) ⇒ ⛔ không
có chuyện 2 dialog hiển thị lệch nhau.

**Nguồn dữ liệu:** *display model* do máy chủ dựng sẵn ở `alumglass.api.get_result_display` —
server đã resolve **nhãn + công thức + trace**, trình duyệt chỉ vẽ. Hàm `raw_to_display()`
(`:417`) là đường biến `al_bom_result` thô (JSON đã lưu) thành display model khi cần xem lại kết
quả cũ.

**4 khối, theo thứ tự:**

| Khối | Điều kiện hiện | Nội dung |
|---|---|---|
| **Thanh tổng** | `summary.calculated` | `Giá bán` (đậm, màu `#b45309`) · `VAT` · `Số dòng vật tư` = `summary.line_count` |
| **Chi tiết vật tư** | `lines.length > 0` | 11 cột cơ bản + **5 cột tuỳ chọn** (xem dưới) |
| **Tổng theo nhóm chi phí** | `buckets.length > 0` | `Nhóm chi phí` (tên + mã nhỏ bên dưới) / `Thành tiền` |
| **Chi phí chế tạo** | `cost_template.length > 0` | `Khoản mục` / `Công thức` / `Diễn giải` / `Giá trị` / `ĐVT` |
| *Rỗng* | cả 3 khối trên đều rỗng | *"Chưa có kết quả tính giá cho sản phẩm này."* |

**11 cột cơ bản của bảng vật tư:**
`Mã vật tư` · `Tên vật tư` · `Rộng (mm)` · `Cao (mm)` · `Số lượng` · `Trọng lượng` · `Khối lượng` ·
`ĐVT` · `Đơn giá` · `Thành tiền` · `Nhóm CP`.

⚠️ **5 cột `Màu sắc` · `Nơi cấp vật tư` · `Vị trí lắp đặt` · `Góc cắt` · `Ghi chú` chỉ hiện khi có
ÍT NHẤT 1 dòng thật sự dùng** (`:81-83`) — để BOM cũ/đơn giản không bị đội bảng. Đây là lý do cùng
một BOM mà lúc thấy 11 cột, lúc thấy 16 cột: ⛔ **không phải lỗi**.

**Vài quy tắc hiển thị đáng biết:**

| Chỗ | Luật |
|---|---|
| `Trọng lượng` | Chỉ hiện `kg/m` khi `has_weight` **và** `weight_per_unit > 0`; còn lại `—` |
| `Số lượng` | `qty`, kèm `(unit_qty/đv)` màu xám khi có `unit_qty` |
| `Tên vật tư` | Lấy `label` **hoặc** `slug`; có `trace` thì hiện mục *"Xem trace"* gập được (khi `opts.show_trace`) |
| `Diễn giải` (cost template) | `format_trace(c.trace)` + `= giá trị`; dòng có `is_subtotal` **in đậm + nền vàng** |
| Mọi chuỗi từ dữ liệu | Đi qua `alumglass.esc()` (`:204`) trước khi nhét vào HTML |

**`opts`:**

| Option | Mặc định | Tác dụng |
|---|---|---|
| `collapsible` | `true` | Bọc mỗi khối trong `<details>`; `false` ⇒ khối `<div>` trơn |
| `show_trace` | `false` | Hiện trace **từng dòng vật tư** |
| `compact` | `false` | Cỡ chữ `11px` thay vì `12px` |
| `title` | — | Tiêu đề đậm in trên cùng |

---

### 4.7 Nút cấp form + 2 luồng tính hàng loạt

#### `_add_form_actions(frm)` — `:2116`

Đăng ký 2 nút trong nhóm **AlumGlass**:

| Nút | Điều kiện hiện | Gọi |
|---|---|---|
| **Tính giá** | Chỉ khi `frm.doc.docstatus === 0` (báo giá còn Draft) | `_calc_all_items(frm)` |
| **Preview giá** | **Mọi trạng thái** | `_preview_all_items(frm)` |

✅[V] Ghi chú ngay trong code (`:2119-2122`): *"Chỉ mời bấm 'Tính giá' khi báo giá còn Draft. Chốt
THẬT nằm ở SERVER … docstatus ở đây chỉ để đỡ mời người dùng bấm nút sẽ hỏng, **KHÔNG phải lớp bảo
vệ**."* — đúng tinh thần: ẩn nút không phải phân quyền.

#### `_calc_all_items(frm)` — nút **Tính giá** `:2132`

Luồng **tuần tự**, từng dòng một (⛔ không song song) — để tránh dội tải và để tiến trình dễ hiểu:

```
1. Lọc dòng thật:  items.filter(r => !r.is_new)
   rỗng ⇒ msgprint "Chưa có dòng sản phẩm nào." rồi dừng

2. Kiểm tra từng dòng, gom hết lỗi rồi báo MỘT LẦN:
     · chưa chọn BOM
     · chưa chọn BOM Version
     · chưa nhập tham số (mở Tham số BOM và bấm Lưu)
   thiếu ⇒ msgprint (cam) "Chưa thể tính giá — thiếu thông tin"
           + danh sách "Dòng {n} (mã): <thiếu gì>" — ⛔ KHÔNG tính dòng nào

3. show_alert "Đang tính giá {n} dòng..."
4. Với TỪNG dòng, nối tiếp:
     a. _sync_row_to_db(frm, "Quotation Item", <tên dòng>)   ← đẩy al_bom_vars xuống DB trước
     b. frappe.call("alumglass.api.calculate_bom", {quotation_item_name})
     c. rồi sang dòng kế
5. finish(): refresh_field("items") + show_alert tổng kết
```

⚠️ **Vì sao phải có bước (a):** `calculate_bom` đọc dữ liệu **từ DB**, ⛔ không đọc bộ nhớ trình
duyệt — người dùng vừa đổi tham số trong dialog mà chưa `Ctrl+S` thì server vẫn thấy bản cũ
(ghi rõ ở `:2185-2187`).

**Xử lý kết quả từng dòng:**

| Kết quả server | Việc client làm |
|---|---|
| `async = true` | `al_calc_status = "Queued"`, lưu `al_calc_job_id`, tăng biến đếm `queued` |
| Đồng bộ OK | `al_calc_status = "Success"`, `al_bom_result = JSON`, `al_gia_ban = ct.GIA_BAN`, `al_gia_vat = ct.GIA_VAT`, **`rate = ct.GIA_BAN`** |
| Lỗi mạng/server | `al_calc_status = "Failed"`, `al_calc_error = sanitize_calc_error(...)` |
| `_sync_row_to_db` thất bại | Như trên, ghi vào `al_calc_error` |

⚠️ **Hai điểm đáng lưu ý trong bảng này:**

1. **Client đọc `GIA_BAN` / `GIA_VAT` theo TÊN** (`ct.GIA_BAN`, `ct.GIA_VAT`) — trong khi engine
   chọn dòng giá cuối **theo CỜ** `is_final_price` / `is_pre_vat_price` (§5 B6). Hai cơ chế này
   ⛔ không ràng buộc nhau: nếu Cost Template đổi tên `line_code` mà vẫn giữ cờ, engine vẫn đúng
   nhưng **ô `al_gia_ban`/`al_gia_vat` trên lưới sẽ hiện 0** cho tới khi tải lại form. Đây là chỗ
   hay gây "server tính đúng mà lưới hiện sai".
2. **`rate` = giá TRƯỚC VAT** (ghi chú `A8`, `:2220`) — khớp với B7 ở server (`rate = al_gia_ban`).

**Tổng kết cuối:** `frappe.show_alert` *"Đã tính {x}/{y} dòng"* + hậu tố `· {n} dòng chờ nền` và
`· {n} dòng lỗi`; màu xanh / cam / đỏ theo kết quả.

**Cảnh báo của engine:** gom hết vào `calc_issues` rồi **chỉ hiện MỘT popup** ở cuối — lý do ghi rõ
ở `:2160-2161`: *"tính 20 dòng mà popup 20 lần thì không dùng được"*. Tiêu đề popup:

| Có lỗi? | Tiêu đề |
|---|---|
| Có ≥1 mục `severity = "error"` | *"Tính giá có lỗi — cần xử lý trước khi chốt báo giá"* (đỏ) |
| Chỉ cảnh báo | *"Cảnh báo tính giá — cần xác nhận lại trước khi chốt báo giá"* (cam) |

Mỗi mục in `⚠️` (warning) hoặc `⛔` (error) + `"<mã vật tư>: <câu cảnh báo>"`.

#### `_preview_all_items(frm)` — nút **Preview giá** `:2251`

Thuần **đọc** — ⛔ không gọi `calculate_bom`, ⛔ không ghi gì:

```
1. Lọc dòng thật; rỗng ⇒ "Chưa có dòng sản phẩm nào."
2. Mở Dialog "Preview giá toàn bộ sản phẩm", size large, ép rộng 90vw (:2264)
3. Vẽ NGAY 2 phần:
     · bảng tổng hợp: # · Mã sp · Tên sp · Số lượng · Đơn giá · Thành tiền (qty × rate)
     · mỗi sản phẩm 1 <details> gập được, trạng thái "Đang tải..."
4. Rồi frappe.call("alumglass.api.get_result_display") cho TỪNG dòng, KHÔNG chặn UI
5. Mỗi dòng trả về ⇒ đổ vào <details> của nó
```

**Trạng thái hiện trên từng `<details>`:**

| Tình huống | Chữ hiện ra |
|---|---|
| Có kết quả, không cảnh báo | *"Đã tính"* |
| Có cảnh báo | *"Đã tính — có cảnh báo"* (cam) |
| Có lỗi | *"Đã tính — có lỗi"* (đỏ) |
| Chưa tính (Draft) | *"Chưa tính giá cho sản phẩm này — bấm nút Tính giá hoặc mở Tham số BOM để tính."* |
| Chưa tính, `docstatus = 1` | *"…Báo giá đã gửi khách nên không tính giá lại được."* |
| Chưa tính, `docstatus = 2` | *"…Báo giá đã huỷ nên không tính giá được."* |
| Lỗi tải | *"Lỗi"* + *"Không tải được chi tiết."* |

✅[V] Điểm đáng khen ở `:2330-2337`: câu "chưa tính giá" **đổi theo trạng thái chứng từ** — vì ở
báo giá đã gửi/đã huỷ thì 2 nút đã bị ẩn, ⛔ không chỉ vào nút không còn tồn tại.

⚠️ **Hai comment trong tệp đã CŨ so với mã hiện tại** (đừng tin khi đọc code):

| Chỗ | Comment nói | Thực tế tại `ad79edb` |
|---|---|---|
| `quotation.js:2206-2208` | *"response đồng bộ hiện CHƯA có `errors`…"* | Engine **đã** trả `errors` — `_build_response()` `:2686-2698` |
| `api/__init__.py:65-67` | *"…`_build_response()` chưa trả key này ⇒ đường sync sẽ là `{}`…"* | Như trên — comment này ngược với chính hàm `_build_response()` đã sửa |

⇒ **Kết luận đúng:** đường **đồng bộ CÓ** mang túi `errors`; client đã đọc nó qua
`collect_calc_errors(r.message.errors)` (`:2209`). ⛔ Không cần "chờ API bổ sung" như comment viết.

---

### 4.8 Hai dialog — chi tiết từng hàm

`quotation.js` có **2 class dialog**, ⛔ không phải 1. Cả hai đều là **đường GHI giá**:

| Class | Dòng | Vai trò | Gọi API | Có ghi giá không? |
|---|---|---|---|---|
| `ItemParamDialog` | `:551–1682` | Nhập/sửa tham số + preview **tự động** | `get_variable_set_for_bom`, `calculate_bom`, `get_result_display` | **CÓ** — auto-preview tự chạy `calculate_bom` |
| `BOMDialog` | `:1687–1891` | Xem kết quả | `calculate_bom` (**chỉ khi dòng chưa có kết quả**), `get_result_display` | **CÓ, có điều kiện** |

⚠️ **Điểm dễ hiểu nhầm nhất:** `BOMDialog` mang tên "dialog kết quả" nhưng `_load_existing_state()`
**vẫn gọi `calculate_bom`** khi dòng chưa có `al_calc_status = "Success"` (`:1742`). Mở 🖥️ trên dòng
chưa tính = **tính giá thật**. ⛔ Đừng coi nó là thao tác đọc thuần.

Cả hai đều mở **sau** `_sync_row_to_db()` (§4.5) và đều render qua `render_bom_result_display` (§4.6).

#### A. `ItemParamDialog` — dialog nhập tham số (`:551`)

**Mở từ 3 chỗ** (⛔ không có nút toolbar nào):

| Chỗ | Dòng | Dạng |
|---|---|---|
| Nút 📐 ở góc phải ô `item_code` mỗi dòng | `:2049` | Icon nhỏ, luôn hiện |
| Nút *"📐 Tham số BOM"* trong form mở rộng của dòng | `:1945` | Nút đầy đủ |
| **Nháy đúp** vào dòng | `:2088` | Không có nút |

⛔ Cả 3 đều bị chặn khi `frm.doc.docstatus !== 0` (`:2029` cho nút dòng, `:1931` cho form mở rộng) —
chốt thật ở server.

**`constructor(frm, child_doc)`** `:552` — nhận thẳng **doc của dòng** `Quotation Item`, ⛔ không nhận
tên. Khởi tạo các ô nhớ nội bộ; 6 ô quan trọng:

| Ô | Ý nghĩa | Vì sao cần |
|---|---|---|
| `_var_controls` | `[{var_name, ctrl}]` | Để `_save()` đọc giá trị biến |
| `_glass_controls` | `[{rep, ctrl}]` | Chọn **kính theo từng vị trí** |
| `_color_controls` | `[{rep, ctrl}]` | Chọn **màu theo từng vị trí** (Q2) |
| `_preview_seq` | Số tăng mỗi lần preview | **Chống race**: preview cũ về sau preview mới ⇒ bỏ |
| `_dialog_ready` | Chỉ `true` **sau** khi nạp xong lần đầu | ⛔ Chặn preview thừa lúc vừa mở (set giá trị mặc định cũng bắn `onchange`) |
| `_dialog_open` | Dialog đang hiện | ⛔ Chặn debounce còn treo ghi DB **sau khi dialog đóng** → tránh `TimestampMismatchError` |

✅[V] Hai cờ `_dialog_ready` / `_dialog_open` đều có comment nêu **hậu quả thật** ở `:563–571` —
đọc trước khi sửa.

**`show()`** `:574` — gọi thẳng `_render_dialog()`. ⛔ Không tải dữ liệu trước: dialog hiện ngay rồi
mới nạp.

**`_render_dialog()`** `:692` — trái tim của dialog:

- **Tiêu đề**: `"Tham số BOM — " + (item_name || item_code || "Dòng mới")` `:694`
- **`size: "large"`** + ép `max-width: 80vw` `:710`
- **Nút chính** `"💾 Lưu"` → `_save()` rồi `dialog.hide()` `:697–701`
- **Nút phụ** `"🖥️ Preview tính giá"` → `_save()` **trước**, rồi `_run_preview(true)` `:702–706`
  — `true` = thủ công ⇒ **được phép cuộn** tới kết quả
- `hidden.bs.modal` ⇒ `_dialog_open = false` + `_cleanup_realtime()` `:714–717`
- `_populate_extra_vars()` + `_setup_extra_vars_autofill()` `:720–721`
- `_load_variable_set()` → `_render_vars_container(vars)` → `_render_bom_info(true)` → **`setTimeout(…, 50)`
  mới bật `_dialog_ready = true`** `:725–732`
- `alumglass.excel_io.attach(...)` cho vùng `upload_section` — Export/Import **bảng Biến mở rộng**
  `:735–742`
- `setTimeout(() => this._render_preview_panel(), 300)` `:744` — vẽ lại **kết quả đã lưu**, ⛔ **không
  gọi lại API**

⚠️ **`preserveExisting`** (`:753`): `true` khi **mở dialog** ⇒ giữ override đã lưu trong `al_bom_vars`;
`false` khi **đổi BOM** ⇒ bỏ override, reset về mặc định của BOM mới.

**`_build_dialog_fields()`** `:606` — 6 nhóm field, theo đúng thứ tự hiển thị:

| # | Nhóm | Field | Ghi chú |
|---|---|---|---|
| 1 | **Sản phẩm** | `product_header` (HTML) | Vẽ bởi `_render_product_header()` `:782` — ảnh `item_image` + tên + mã sản phẩm |
| 2 | **Chọn BOM** | `al_bom`, `al_bom_name`, `al_bom_version`, `al_brand` | `al_bom` đổi ⇒ `_on_bom_change()`; 3 field còn lại ⇒ auto-preview |
| 3 | **Cấu hình BOM** | `al_bom_set`, `al_accessory_set`, `al_profile_system`, `al_cost_template` | **Editable** (A2/A3) — đổi khác mặc định ⇒ lưu override `_bom_set`… |
| 4 | **Tham số sản phẩm** | `vars_container` (HTML) | **Vùng biến động** — re-render tại chỗ, ⛔ không tạo lại dialog |
| 5 | **Biến mở rộng (tùy chọn)** | `extra_vars` (Table) | 3 cột con: `var_name` (Link → `AL Variable Library`, lọc `is_system = 0`), `var_type`, `var_value` |
| 6 | **Kết quả Preview** | `preview_html` (HTML) | |

✅[V] `al_bom_version` có `get_query` lọc `{bom: <al_bom đang chọn>}` `:627–631` — đổi BOM là danh sách
version đổi theo.

**`_load_variable_set()`** `:579` — `al_bom` rỗng ⇒ trả `[]`, `_bom_meta = null`. Ngược lại gọi
`get_variable_set_for_bom(bom_code)`; **lỗi mạng cũng trả `[]`** (⛔ không ném) để dialog không chết
`:595`. Kết quả gán vào `this._bom_meta` — dùng lại ở `_render_vars_container`, `_render_bom_info`,
`_save`.

**`_render_vars_container(vars)`** `:894` — dựng toàn bộ vùng biến động bằng
`frappe.ui.form.make_control`, **3 cột**, mỗi mục là 1 `<details open>` gập được:

| Mục | Nguồn | Ghi chú |
|---|---|---|
| **Kính theo vị trí** | `_bom_meta.glass_groups` | Mỗi vị trí 1 Link → `AL Glass Master`; `rep` = mã đại diện |
| **Màu sắc** | `_bom_meta.color_groups` | Nhóm theo `category_label` (Nhôm/Kính/Phụ kiện…); mỗi vị trí 1 Link → `AL Color Standard`, lọc `is_representative = 1` |
| **Biến đầu vào** | `vars` lọc `!is_system` | ⛔ Ẩn `glass_master` nếu có `glass_groups`; ⛔ Ẩn `aluminum_color` nếu có `color_groups`; ⛔ Ẩn `accessory_set`/`_accessory_set` (đã có field riêng) `:931–943` |
| **Biến hệ thống (tự động)** | `vars` lọc `is_system` | Kèm nút `"↺ Khôi phục mặc định biến hệ thống"` `:1085` |

⚠️ **Mã đại diện ≠ kính đã chọn** (`:974–1009`) — chi tiết quan trọng nhất của mục này: ô kính có thể
đang hiện **mã giữ chỗ** (`g.default` khai trên BOM Set), ⛔ **không phải** kính người dùng đã chọn cho
báo giá này. Khi đó engine **vẫn tra giá theo mã giữ chỗ** ⇒ mã này thường ⛔ không có dòng `Item Price`
nào ⇒ **giá tạm tính 0 + cảnh báo "thiếu giá"**. Client in ngay hint vàng *"Mã đại diện của BOM — chưa
chọn kính cho báo giá này"* `:1005–1009`. ✅[V] Đúng rule 8: trạng thái tự giải thích + lối xử lý tại
chỗ, ⛔ không để người dùng gặp lỗi "thiếu giá" mới hiểu.

**`_var_to_field(v, current_val)`** `:859` — ánh xạ 1 biến của Variable Set → 1 field Frappe:

| `var_type` | `fieldtype` | Ghi chú |
|---|---|---|
| `Float` | `Float` | `precision: "1"` — **1 số lẻ** |
| `Int` · `Data` · `Check` · `Currency` | Tương ứng | |
| `Select` | `Select` | ⛔ Không bắt buộc ⇒ **chèn thêm option rỗng** để bỏ trống được `:880` |
| `Link` | `Link` | `options = v.link_doctype` |
| Khác | `Data` | |

⚠️ **Quy tắc Q1b** `:860`: biến là **pricing dimension** (`is_pricing_dimension`) ⇒ **luôn `reqd: 0`**,
bỏ trống được — engine chỉ **bỏ qua dimension đó** khi khớp giá composite. ⛔ Không hardcode tên biến:
client đọc cờ từ server, nên **thêm dimension mới ⛔ không phải sửa file này**.

**Auto-preview — 3 hàm, đây là chỗ hay gây khó chịu nhất khi dùng**

| Hàm | Dòng | Việc |
|---|---|---|
| `_schedule_auto_preview()` | `:1207` | Thoát ngay nếu ⛔ `!_dialog_ready` hoặc ⛔ `!_dialog_open`; gọi `_mark_preview_stale()`; **debounce 700ms** rồi `_run_preview()` |
| `_mark_preview_stale()` | `:1220` | Dán badge vàng *"⏳ Tham số vừa đổi — đang tự động tính lại giá..."* — ⛔ **không xoá** kết quả cũ (tránh cảm giác dialog "đứng") |
| `_bind_auto_preview_listeners()` | `:1232` | Gắn `change` + `awesomplete-selectcomplete` cho **mọi** control biến/kính/màu |

`_bind_auto_preview_listeners()` được gọi lại **mỗi lần** `_render_vars_container` chạy (`:1100`) — vì
khi đổi BOM, các control cũ bị huỷ và tạo lại hoàn toàn.

✅[V] **Debounce 700ms** và **`_preview_seq`** là 2 lớp chống dội khác nhau: 700ms gộp thao tác gõ số;
`_preview_seq` (`:1389`, `:1397`, `:1426`) loại kết quả **cũ về muộn**. Đổi kính liên tục ⇒ chỉ kết quả
**mới nhất** được vẽ.

**`_run_preview(manual)`** `:1362` — luồng preview (dùng chung cho cả bấm tay lẫn tự động):

```
1. Hiện spinner "Đang tính toán..."
     · manual = true  ⇒ scrollIntoView (cuộn tới kết quả)
     · manual = false ⇒ ⛔ KHÔNG cuộn — để con trỏ người dùng đứng nguyên lúc đang gõ
2. self._save()                    ← lưu tham số vào MODEL TRÌNH DUYỆT
3. Không có BOM ⇒ "Vui lòng chọn BOM trước khi Preview" rồi dừng
4. seq = ++this._preview_seq       ← mốc chống race
5. _sync_row_to_db(cdt, cdn)       ← đẩy xuống DB (server đọc DB, ⛔ không đọc browser)
     · thành công ⇒ _exec_calculate_bom($container, seq, manual)
     · thất bại   ⇒ "Không lưu được dữ liệu dòng trước khi tính giá: <lỗi>"
6. Dòng mới vừa lưu lần đầu ⇒ TÊN DÒNG ĐỔI ⇒ cập nhật lại self.child_doc (:1398–1402)
```

**`_exec_calculate_bom($container, seq, manual)`** `:1418` — gọi `calculate_bom`, 4 nhánh:

| Nhánh | Việc client làm |
|---|---|
| `r.message.async` | Tiến trình nền; `al_calc_status = "Queued"` + `al_calc_job_id` vào model **và** `child_doc`; `_listen_realtime(job_id)` |
| Đồng bộ | `al_calc_status = "Success"`, `al_bom_result = JSON.stringify(r.message)`; `_apply_rate(ct.GIA_BAN)`; `_render_display_model(...)` |
| `!r.message` | *"Không có kết quả. Kiểm tra lại tham số đầu vào."* |
| `error` | `_preview_error_html(err)` — đưa **nguyên object** lỗi (⛔ không `String()` trước) để `sanitize_calc_error` rút được câu người-đọc-được `:1468–1470` |

⚠️ `seq !== self._preview_seq` xuất hiện ở **cả 3** callback (`callback` `:1426`, `error` `:1466`,
`.then` của sync `:1397`) — chỗ nào cũng **thoát sớm**. Đây là lớp chống race **thật**, ⛔ đừng bỏ khi
refactor.

**`_render_display_model($container, qi_name, force_notify)`** `:1480` — lấy **display model** từ server
rồi vẽ:

- Gọi `get_result_display(quotation_item_name)` — server trả **nhãn + công thức + `errors` đã resolve**
- Có `summary.calculated` ⇒ dán `calc_errors_banner(errors)` **trên** bảng +
  `notify_calc_errors(..., {dedupe_key: qi_name, force: !!force_notify})`
- Server trả rỗng ⇒ **fallback** đọc `child_doc.al_bom_result` (JSON trong tay) → `raw_to_display(raw)`
  → **vẫn dán banner** `errors` lấy từ raw
- `force_notify` = người dùng **vừa chủ động** bấm tính, hoặc **vừa có kết quả async về** ⇒ **luôn
  popup**; mở lại panel xem kết quả **cũ** ⇒ chỉ banner (⛔ không popup lặp)

✅[V] **Vì sao phải đi vòng qua `get_result_display`** thay vì dùng `r.message` vừa nhận (`:1457–1458`):
đây là **nguồn duy nhất có `errors` cho CẢ 2 đường** sync/async, **và** nhãn/công thức đã được server
resolve sẵn — client ⛔ không phải tự đoán.

⚠️ **`raw_to_display(raw)` ⛔ KHÔNG mang `errors`** (`:447–457` chỉ trả `summary`/`lines`/`buckets`/
`cost_template`). Nên ở nhánh fallback, banner phải lấy `errors` **từ raw** — cả `ItemParamDialog`
`:1509` lẫn `BOMDialog` `:1872` đều đã làm đúng. Thêm chỗ gọi mới thì **phải nhớ điều này**.

**`_save()`** `:1540` — gom 5 nguồn rồi ghi vào dòng:

| Nguồn | Ghi vào `al_bom_vars` |
|---|---|
| `_var_controls` | `<var_name>: <giá trị>` (bỏ qua ô rỗng) |
| `_glass_controls` | `glass_master_map: {rep: mã kính}` — chỉ ghi khi **có ≥ 1 ô** |
| `_color_controls` | `color_master_map: {rep: mã màu}` — như trên |
| Bảng `extra_vars` | `extra_vars: {tên: giá trị}` — `Float`/`Int` ⇒ `parseFloat` (NaN ⇒ 0); `Check` ⇒ boolean |
| `_collect_overrides()` | `_bom_set` · `_accessory_set` · `_profile_system` · `_cost_template` · `_bom_name` · `_brand` |

Rồi ghi xuống dòng: `al_bom_vars` (JSON), `al_bom`, `al_bom_version`; **và tự set `item_code` /
`item_name`** từ `_bom_meta` (representative item của BOM) — ⛔ **chỉ ghi khi KHÁC** giá trị hiện có, để
không đè mã người dùng tự nhập `:1620–1629`.

⚠️ **`_collect_overrides()`** `:1656` chỉ ghi override khi giá trị **khác mặc định của BOM** — cố ý, để
`al_bom_vars` không bị nhiễu. **Hệ quả:** `al_bom_vars` ⛔ **không phải** bản sao đầy đủ cấu hình, nó chỉ
chứa **phần bị đổi**. Đọc `al_bom_vars` để suy ra cấu hình đang dùng là **sai** — phải đọc `_bom_meta`
+ phần override.

**`_apply_rate(giaban)`** `:1643` — đặt `rate = GIA_BAN` (⛔ **chưa VAT**), chỉ ghi khi `rate > 0`. Gọi
từ 3 nơi: preview đồng bộ `:1456`, realtime async `:1301`, và nút **Tính giá** form-level (§4.7).

**`_render_preview_panel()`** `:1247` — mở lại dialog: đọc `child_doc.al_calc_status` rồi:

| `al_calc_status` | Hiện gì |
|---|---|
| `Success` + có `al_bom_result` | `_render_display_model(...)` — ⛔ **không gọi lại API** |
| `Queued` / `Running` | Thanh tiến trình + câu *"…Nếu chờ lâu mà chưa thấy kết quả, bấm nút 'Preview tính giá' để tính lại."* + `_listen_realtime(job_id)` |
| `Failed` | `_preview_error_html(al_calc_error)` |
| Khác (chưa tính) | *"🖥️ Nhấn nút 'Preview tính giá' để xem kết quả"* |

⚠️ Câu ở nhánh `Queued` **là lối xử lý cho ca worker đã chết** (`:1261–1263`) — dòng còn "Queued" từ
lần mở form trước ⛔ **sẽ không bao giờ** có kết quả. ⛔ Đừng "dọn" câu này thành *"đang chờ…"* chung
chung.

**`_listen_realtime(job_id, $container)`** `:1282` — nghe `alumglass_bom_calc_done`, **lọc theo
`job_id`** (`:1286`); nhận đúng job ⇒ `_cleanup_realtime()` **ngay** rồi:

- `Success`: `set_value` `al_calc_status = "Success"` + `al_bom_result`;
  `_apply_rate(result.cost_template.GIA_BAN)`; `_render_display_model(..., true)` (**force** để cảnh báo
  hiện ngay, ⛔ không bị dedupe chặn); `show_alert "Tính giá xong"` (xanh)
- Lỗi: `al_calc_status = "Failed"`, `al_calc_error = data.error`, vẽ `_preview_error_html`

**Hiển thị lỗi — quy tắc D2:** `_preview_error_html(error)` `:1342` **⛔ không render thẳng** chuỗi lỗi.
Đi qua `sanitize_calc_error(error)`:

| Phần | Hiện ở đâu |
|---|---|
| `info.message` | Câu tiếng Việt ngắn, đã escape — hiện thẳng |
| `info.trace` | **Chỉ** nằm trong `<details>` ẩn, nhãn *"Chi tiết kỹ thuật (gửi cho quản trị khi cần)"* |
| Lối xử lý | Luôn kèm: *"Bấm nút 'Preview tính giá' để thử lại. Nếu vẫn lỗi, báo quản trị."* |

✅[V] Lý do (`:1339–1341`): `al_calc_error` trong DB có thể là **stack trace do bản cũ ghi** — render
thẳng là phơi mã kỹ thuật ra người dùng.

#### B. `BOMDialog` — dialog kết quả (`:1687`)

**Mở từ 2 chỗ**, cả hai đều **sau** `_sync_row_to_db()` và có `frappe.dom.freeze("Đang đồng bộ dữ
liệu...")`: nút 🖥️ trong form mở rộng của dòng `:1961`, nút 🖥️ nhỏ ở dòng `:2067`.

⚠️ Cả hai **chặn trước**: chưa có `al_bom` ⇒ *"Chưa chọn BOM. Vui lòng mở 📐 Tham số BOM trước."*
`:1949` / `:2057` — ⛔ không mở dialog rỗng.

**`constructor(quotation_item_name)`** `:1688` — ⚠️ **khác `ItemParamDialog`**: nhận **tên dòng** (chuỗi),
⛔ **không** nhận `frm`. Nên `BOMDialog` chỉ đọc DB, ⛔ **không cập nhật lưới** — muốn thấy giá trên lưới
phải bấm **Tính giá** hoặc tải lại form.

**`show()`** `:1694` — dialog **1 field** `result_html`, tiêu đề *"BOM Calculation Result"*,
`size: large`, nút **"Close"**; đóng ⇒ `_cleanup_realtime()`; rồi `_load_existing_state()`.

**`_load_existing_state()`** `:1715` — đọc `al_calc_status`, `al_calc_job_id`, `al_bom_result`,
`al_calc_error` bằng `frappe.db.get_value`:

| Trạng thái trên dòng | Việc làm |
|---|---|
| `Success` + có `al_bom_result` | `JSON.parse` → `render_results(data)` — ⛔ **không gọi lại API** |
| `Queued` / `Running` | `_show_async_progress(...)` + `_listen_realtime(job_id)` |
| `Failed` | `_render_error(al_calc_error)` |
| Chưa có / khác | **`this.calculate()`** ← ⚠️ **đây là đường GHI** |

**`calculate()`** `:1746` — `_show_loading("Đang tính giá...")` → `calculate_bom` → `async` ⇒
`_show_async_progress` + `_listen_realtime`; đồng bộ ⇒ `render_results(r.message)`; lỗi ⇒
`_render_error(String(err))`.

**`render_results(data)`** `:1850` — ⚠️ **có tham số `data` nhưng ⛔ không dùng cho nhánh chính**: nó gọi
`get_result_display` để lấy **display model** (giống `ItemParamDialog`), chỉ dùng `data` làm **fallback**
khi server không có display. Tùy chọn render khác preview:

| Option | `ItemParamDialog` (preview) | `BOMDialog` (kết quả) |
|---|---|---|
| `collapsible` | `true` | `true` |
| `show_trace` | **`false`** | **`true`** — hiện trace từng dòng vật tư |
| `compact` | `true` (chữ 11px) | ⛔ không đặt |
| `title` | — | *"BOM Calculation Results"* |
| `notify_calc_errors` | `force: !!force_notify` | **`force: true`** — luôn popup |

⚠️ **Nhánh `error` của `render_results`** `:1880–1888` **không báo lỗi** mà cố render bằng `data` trong
tay (fallback có chủ ý). Nhưng khi mất mạng và `data` rỗng, `raw_to_display({})` vẫn trả display hợp lệ
(`summary.calculated = false`) ⇒ dialog hiện **bảng rỗng** thay vì nói *"không tải được"*. Đây là hành vi
**đang sống** — gặp "dialog trắng" thì kiểm tra mạng trước, ⛔ đừng kết luận dữ liệu mất.

**`_show_async_progress(job_id, message)`** `:1811` — ⚠️ kèm **lối xử lý** cho ca **worker đã chết**:
*"Nếu chờ lâu mà chưa thấy kết quả, đóng cửa sổ này rồi bấm lại nút tính giá để chạy lại."* ⛔ Đừng bỏ
câu này — job nền không tự hồi sinh.

**`_render_error(error)`** `:1824` — cùng quy tắc D2 như `ItemParamDialog._preview_error_html`: câu tiếng
Việt ngắn + lối xử lý, trace chỉ trong `<details>` ẩn. Khác một chỗ: câu dự phòng khi ⛔ không rút được
message người-đọc-được là *"Xem chi tiết trong Error Log hoặc trường AL Calc Error trên Quotation
Item."*

**`_set_html(html)`** `:1839` — `dialog.set_value("result_html", html)` rồi **`dialog.show()` lại**. ✅[V]
Đây là lý do dialog **không cần** hiện trước khi có dữ liệu: mỗi lần đổi nội dung là mỗi lần show lại.

#### C. Toàn bộ `frappe.call` trong `quotation.js` — bảng tra

| Dòng | Method | Gọi từ | Loại |
|---|---|---|---|
| `:585` | `get_variable_set_for_bom` | `ItemParamDialog._load_variable_set()` | Đọc |
| `:1423` | `calculate_bom` | `ItemParamDialog._exec_calculate_bom()` | ⚠️ **GHI** |
| `:1487` | `get_result_display` | `ItemParamDialog._render_display_model()` | Đọc |
| `:1751` | `calculate_bom` | `BOMDialog.calculate()` | ⚠️ **GHI** |
| `:1853` | `get_result_display` | `BOMDialog.render_results()` | Đọc |
| `:2191` | `calculate_bom` | `_calc_all_items(frm)` — nút **Tính giá** | ⚠️ **GHI** |
| `:2308` | `get_result_display` | `_preview_all_items(frm)` — nút **Preview giá** | Đọc |

✅[V] **3 nơi gọi `calculate_bom`** — tất cả đều dẫn tới **B7 ghi giá**. ⛔ Không có đường "chỉ tính thử
mà không ghi": muốn xem **mà không ghi** thì chỉ có `get_result_display` (đọc kết quả **đã lưu**), ⛔
không có chế độ dry-run.

---

## §5. B0 → B7 chi tiết từng bước

### B0 — Chốt phiên bản BOM

**Mục đích:** mọi con số phải đến từ **một bản snapshot bất biến**, không phải cấu hình sống.

**Đọc:**

| Thứ tự | Nguồn | Field |
|---|---|---|
| 1 | `Quotation Item` | `al_bom_version` — nếu có, dùng luôn |
| 2 | `AL BOM` | `current_version` |
| 3 | `AL BOM Version` (query) | `order_by = "creation DESC"`, `limit 1` |

**Ghi:** `self.bom_version`, `self.bom_version_name`, `self.bom_code`.

⚠️ **Hành vi hiện tại — engine ⛔ KHÔNG tự tạo phiên bản.** Nếu BOM chưa có phiên bản nào:

```
frappe.throw(
    "BOM '%s' chưa có phiên bản nào nên chưa tính giá được. "
    "Mở BOM này → bấm \"Tạo BOM Version mới\" → duyệt và Xuất bản phiên bản, "
    "rồi bấm \"Tính giá\" lại." % self.bom_code)
```
`bom_orchestrator.py:311-316` ✅[V]

Lý do (ghi ngay trong code `:296-306`): đường tính giá **cố ý** không tạo version — tránh sinh dữ
liệu ngầm và tránh vòng qua quy trình duyệt. Đây là **thay đổi so với các bản tài liệu cũ** mô tả
"Tính giá tự tạo & xuất bản BOM Version".

---

### B1 — Gom biến đầu vào

Đây là bước phức tạp nhất. Thứ tự **có ý nghĩa** — cái nào chạy sau thì thắng.

#### Bảng thứ tự 7 tiểu bước

| # | Tiểu bước | Nguồn | Ghi đè lên |
|---|---|---|---|
| 1.1 | `extra_vars` | `Quotation Item.al_bom_vars` → `extra_vars` | — |
| 1.2 | Global variables | `Formula Global Variable` (cache Redis TTL 60s) | 1.1 |
| **1.4** | **FB `get_live_context`** ⭐ chạy TRƯỚC 1.3 (FB-first) | `Formula Variable Binding` scope **AL Bom Set** | 1.1–1.2 |
| 1.3 | Resolver hệ thống cũ (`fill_missing_only=True`) | `AL Variable Library` → `source_doctype.source_field` | **chỉ biến CHƯA có** |
| 1.4b | Child table profile | `AL Profile System.system_variables` | 1.4 |
| 1.5 | Biến người dùng nhập | `al_bom_vars` (phẳng) | tất cả |
| 1.5b | *capture* override (không ghi vào inputs) | `_accessory_set`, `glass_master_map`, `color_master_map`… | — |
| 1.5c | Resolve LẠI toàn bộ nếu có `_profile_system` | như 1.3 nhưng `fill_missing_only=False` | 1.3 + 1.4 |
| 1.6 | Mặc định biến người dùng | `AL Variable Library.default_value` | — |
| **1.7** | **Chuẩn hoá phần trăm** — chạy SAU CÙNG | — | mọi nguồn trên |

#### Vì sao 1.4 chạy trước 1.3

Ghi chú trong code `:367-373`: để biến đã có FVB seed **không phải resolve 2 lần** (legacy chạy
rồi FB ghi đè cùng giá trị). Biến **chưa** seed vẫn rơi về resolver 1.3 như cũ.

#### 1.4 — FB resolve thế nào

`_resolve_fb_context()` `:672` gọi:

```python
get_live_context(json.dumps({
    "current_doctype": scope_doctype,     # ưu tiên "AL Bom Set", fallback "Quotation Item"
    "current_docname": scope_docname,
}))
```

**Vì sao scope là `AL Bom Set`?** Chuỗi `Quotation Item → AL BOM → AL BOM Version → AL BOM →
AL Bom Set`. `AL Bom Set` là doc **duy nhất** có link trực tiếp tới `profile_system` và
`product_type` — đúng 2 nguồn của biến hệ thống. `Quotation Item` ⛔ không có link đó.

Sau khi FB trả về, engine **chỉ nhận scalar**:

| Loại giá trị FB trả | Engine làm gì |
|---|---|
| `None`, dict, list, chuỗi rỗng | **Bỏ** |
| Số (từ binding) | Ép `float` |
| Field của doc (`source == "field"`) | Giữ nguyên kiểu |

#### 1.7 — Chuẩn hoá phần trăm (rất dễ vấp)

`_normalize_percent_inputs()` `:483` + `_PERCENT_VAR_SUFFIXES` `:178`:

```python
_PERCENT_VAR_SUFFIXES = ("_PCT", "_MARGIN", "_RATE")
```

Luật: biến có tên kết thúc bằng `_PCT` / `_MARGIN` / `_RATE`, **hoặc** được khai
`AL Variable Library.var_type == "Percent"`, mà `abs(giá trị) > 1` ⇒ **chia 100**.

| Giá trị lưu trong DB | Sau chuẩn hoá | Ý nghĩa |
|---|---|---|
| `8` (`NC_SX_PCT`) | `0.08` | 8% |
| `10` (`VAT_RATE`) | `0.10` | 10% |
| `0.08` (đã là thập phân) | `0.08` | giữ nguyên — an toàn với data chưa migrate |
| `1` | ⚠️ **Cảnh báo** | nhập nhằng: 1% hay 100%? |

⚠️ **Hành vi hiện tại:** giá trị **đúng bằng 1** sinh cảnh báo `phan_tram_mo_ho_bang_1__warn:<key>`
— hệ thống không đoán, mà nói ra.

---

### B2 — Nạp master data

**Tiền đề:** `bom_version.bom_set_snapshot` phải có, nếu không ⇒
`frappe.throw("BOM Version không có snapshot")` `:828`.

**B2.0 — Nạp phụ kiện** (`_load_accessories()` `:768`)

| Thứ tự nguồn bộ phụ kiện | Nguồn |
|---|---|
| 1 | `al_bom_vars._accessory_set` (hoặc `accessory_set`) |
| 2 | `AL Bom Set.default_accessory_set` |

Mỗi dòng `AL Accessory Item` được **append vào `self.bom_items`** như một dòng BOM bình thường,
với mặc định khi bỏ trống: `calc_pattern = "COUNT"`, `cost_bucket = "VL_PK"`,
`color_group_category = <hằng số DEFAULT_ACCESSORY_CATEGORY>` (lấy từ `Formula Variable Binding`
qua `fb_config.get_named_constant()` — ⛔ không hardcode chuỗi trong code).

#### Sáu batch query

| # | Đọc từ | Field lấy | Dùng để |
|---|---|---|---|
| 1 | `Item` | `weight_per_unit` | `LENGTH_TO_WEIGHT` |
| 2 | `Item Price` | `price_list_rate` + mọi field `custom_pd_*` | **Giá vật tư** |
| 3 | `AL Glass Master` | `total_thick_mm`, `glass_type`, `max_area_m2` | Rule theo độ dày + cảnh báo quá khổ |
| 4 | `AL Material Category` | `default_scrap_pct`, `has_weight` | Hao hụt + cột trọng lượng |
| 5 | `AL Dynamic Item Rule` | theo rule + input | **Chọn mã vật tư động** |
| 6 | `Item` + `Item Price` | của mã vừa resolve từ batch #5 | Giá/khối lượng mã động |

#### Nhánh tra giá — 2 đường, ⛔ không được lệch số

```
prices = self._fetch_composite_prices_via_fb(all_price_items)     # :886
if prices is None:                                                # chưa có binding
    prices = self._fetch_composite_prices(all_price_items)        # :888 — lưới an toàn Python
```

**Nhánh FB** (`_fetch_composite_prices_via_fb` `:1530`) đọc `Formula Variable Binding` có
`source_type` ∈ `("composite_key_lookup", "aluminum_price_composite")` (`:1256`), scope 2 doctype
`("Quotation Item", "AL Bom Item")` (`:1259`), sắp theo `resolve_priority asc`.

Seed sẵn có: binding `COMPOSITE_MATERIAL_PRICE`, `source_type = aluminum_price_composite`,
`source_config = {pricing_mode: "exact_match", price_list: <động>}` — do
`setup/install_fb_bindings.py` tự seed **mỗi lần migrate**. `price_list` điền **động** từ
`_default_price_list()` = `Selling Settings.selling_price_list` (fallback `"Standard Selling"`) —
cùng nguồn với nhánh Python, nên 2 đường ⛔ không thể lệch số khi đổi bảng giá.

**Chế độ `multiplier_chain`** (`_fetch_composite_prices_multiplier_chain` `:1618`):

```
giá = giá_gốc × ∏(effective_mult của từng dimension có mặt trong inputs)

effective_mult = price_multiplier của bản ghi ĐƯỢC LINK   (khi dimension kiểu Link và bản ghi
                                                           có field price_multiplier)
                 nếu không có → price_multiplier khai trên AL Variable Dimension Mapping
```

`fb_handlers.py:222-259` · `bom_orchestrator.py:1694-1722` — ✅[V] **hai đường dùng CÙNG logic**
(cùng công thức `effective_mult`, cùng cách lọc mapping theo `material_category`), nên bật chế độ
này ⛔ không sinh lệch số giữa đường FB-max và đường dự phòng.

#### Hệ số màu `price_multiplier` — hiện trạng & cách bật

| Sự thật | Dẫn chứng |
|---|---|
| Binding seed sẵn chạy `pricing_mode = "exact_match"` | `setup/install_fb_bindings.py:45` |
| Ở `exact_match`, màu **không** nhân hệ số — màu chỉ **chọn dòng giá** (xem `best_partial_match` ở trên) | `engine/composite_pricing.py:25-71` |
| `AL Pricing Dimension` mã `MAU_SAC` kiểu **Link** → `AL Color Standard` | `seed_demo_data.py:302` |
| `AL Color Standard`: WHITE `1.0` · DARK **`1.08`** · GRAY `1.05` · GO `1.20` | `seed_demo_data.py:83` |
| `AL Variable Dimension Mapping`: cả 4 chiều `price_multiplier = 1.0` | `seed_demo_data.py:307` |
| ⛔ Dữ liệu giá seed **không gắn dimension nào** (`custom_pd_*` đều trống) | `seed_demo_data.py:288-289` |

⇒ **Trên dữ liệu hiện tại, DARK và WHITE ra cùng một giá.** Muốn DARK đắt hơn 8% phải **bật
`multiplier_chain`**.

⚠️ **Hành vi hiện tại — ⛔ KHÔNG bật được qua UI.** `install_composite_pricing_binding()` chạy
**mỗi lần migrate** và **ghi đè `source_config`** cho khớp khai báo trong code
(`install_fb_bindings.py:97-112` — vòng `for k, v in payload.items(): if doc.get(k) != v: doc.set(k, v)`).
Ai vào form `Formula Variable Binding` sửa `pricing_mode` thành `multiplier_chain` sẽ thấy nó
**quay về `exact_match` ở lần migrate kế tiếp** mà không có cảnh báo. Muốn bật thật phải sửa hằng số
`COMPOSITE_PRICING_BINDING["source_config"]["pricing_mode"]` tại `setup/install_fb_bindings.py:45`
⇒ **có sửa code**, ⛔ không phải thuần cấu hình như tài liệu cũ mô tả.

⚠️ **Bật `multiplier_chain` sẽ ĐỔI SỐ GOLDEN.** Trong `run_test.py`, CDMQ-2C dùng
`aluminum_color = WHITE` (`×1.0` ⇒ không đổi), nhưng **CDMQ-4C dùng `DARK`** ⇒ mọi dòng nhôm
(`material_category = NHOM`) `×1.08` ⇒ `GIA_VAT` **không còn bằng `47.430.808`**. Bật xong **phải
chạy lại §12.2 rồi cập nhật cả `expected` trong `run_test.py`** — ⛔ đừng để bộ test cũ báo đỏ rồi
kết luận engine sai.

⚠️ **Hai giới hạn đã biết của `multiplier_chain`:**

1. **Màu theo VỊ TRÍ ⛔ không tham gia.** `_fetch_composite_prices_multiplier_chain()` đọc thẳng
   `self.inputs` (`:1698`) và ⛔ **không** gọi `_compute_color_price_overrides()`, trong khi nhánh
   `exact_match` **có** gọi (`:1742` và `:1584`). Nghĩa là: ở chế độ này, chọn màu theo từng vị trí
   trong dialog **không đổi giá** — chỉ biến `aluminum_color` toàn cục mới có tác dụng.
2. **Giá gốc phải là dòng "trần".** `pick_base_price()` lấy dòng **không gắn dimension nào** làm
   giá gốc. Nếu item chỉ có dòng giá đã gắn dimension (tức giá đã gồm phụ phí màu/độ dày) ⇒ engine
   lấy dòng đầu rồi **nhân thêm** ⇒ **tính trùng phụ phí**. Có cảnh báo
   `gia_goc_thieu_dong_tran:<code>` nhưng ⛔ **không chặn** — phải đọc túi `errors` mới thấy.

#### Thuật toán khớp giá — `best_partial_match`

`engine/composite_pricing.py`, dùng **chung** cho cả 2 nhánh và cho `fb_handlers`:

1. Lọc dòng còn hiệu lực: `valid_from` / `valid_upto` (chấp nhận NULL) + đúng `currency`.
2. Với mỗi dòng, đối chiếu các **field dimension** của category (`custom_pd_*`) với biến đầu vào
   hiện tại (màu / xuất xứ / độ dày / bề mặt).
3. Chọn dòng khớp **nhiều chiều nhất** (khớp một phần vẫn được — dòng không gắn dimension nào là
   phương án dự phòng).
4. Không có dòng nào khớp:
   - nhánh chặt (`allow_missing=False`) ⇒ `frappe.throw("Không tìm được Item Price khớp cho '%s' …")` `:1801`
   - nhánh `allow_missing=True` ⇒ trả `0` **kèm cảnh báo** `thieu_gia_item:<code>` (⛔ không im lặng)

#### `row_literals[slug]` — cầu nối giữa B2 và B4

Mỗi dòng BOM được chốt sẵn một dict literal, B3 sẽ nhét vào context dưới dạng `{slug}__{key}`:

| Key | Nguồn |
|---|---|
| `weight_per_unit` | `Item.weight_per_unit` |
| `unit_price` | `best_partial_match` (ưu tiên `price_base_item`) |
| `calc_pattern` | `AL Bom Item.calc_pattern` |
| `glass_thick` / `glass_type` | `AL Glass Master` của kính **đã resolve theo vị trí** |
| `scrap_pct` | `AL Material Category.default_scrap_pct` |
| `has_weight` | `AL Material Category.has_weight` |
| `color` | `default_color` đã resolve theo vị trí |
| `supplier_location` `install_position` `cut_angle` `note` | Khai báo tĩnh trên dòng |

Quy tắc ghi đè: giá khai **tay** trên `AL Accessory Item.unit_price > 0` **thắng** giá tra tự động.

#### Giải kính & màu theo vị trí

```
glass_master_map[rep]  →  glass_master_override  →  rep (chỉ khi rep là mã kính THẬT)
color_master_map[rep]  →  color_master_override  →  rep
```
`_resolve_glass_override()` `:1807` · `_resolve_color_override()` `:1847`

`rep` = mã đại diện của nhóm, tính bởi `glass_group_rep()` / `color_group_rep()`
(`al_bom_engine/`). Với kính, `glass_group_rep` trả `(rep, is_real_master)`; khi BOM chưa cấu
hình `default_glass_master`, `rep` là khoá tổng hợp `"__slug__<slug>"` và `is_real_master=False`
⇒ engine trả `None` (an toàn) ⛔ thay vì coi khoá đó là một mã item.

---

### B3 — Sinh danh sách công thức

Sinh ra 3 nhóm công thức cho mỗi dòng:

**(a) Công thức khai trên dòng** — mọi field trong `formula_fieldnames`. Biểu thức cross-row dạng
`items.<slug>.<field>` được chuẩn hoá:

```python
normalized = self._normalize_items_ref(str(expr))   # items.kinh_tren.width → kinh_tren__width
```

`_normalize_items_ref()` `:2114` dùng `formula_builder.table_formula_builder.normalize_global`.
⚠️ **Hành vi hiện tại — cố ý ⛔ KHÔNG dùng `DotToSubscriptTransformer`** (ghi rõ ở `:2123-2128`):
`items.X.Y` ở đây trỏ tới **kết quả công thức** (biến phẳng `X__Y`), không phải truy cập dict lồng
đã resolve. Đổi sang subscript sẽ khiến nẹp/keo/gioăng ra `0` và lệch golden.

**(b) Ba công thức tổng hợp — luôn được sinh:**

```python
# số lượng đơn vị (linh kiện) — tham số thứ 4 là dict biến phụ của dòng
"{slug}__unit_qty"  = "lookup_calc_pattern({slug}__calc_pattern, {slug}__width,
                        {slug}__height, {slug}__weight_per_unit, {'glass_thick': {slug}__glass_thick, ...})"

# tổng số lượng
"{slug}__total_qty" = "{slug}__unit_qty * {slug}__qty"
# ⚠️ khi AL Bom Set bật apply_scrap_pct:
"{slug}__total_qty" = "({slug}__unit_qty * {slug}__qty) * (1 + {slug}__scrap_pct/100)"

# thành tiền
"{slug}__line_total" = "{slug}__total_qty * {slug}__unit_price"
```
`bom_orchestrator.py:2057-2084` ✅[V]

**(c) Dict lồng `items`** — mirror toàn bộ `{slug}__{field}` vào `inputs["items"][slug][field]`
để công thức cross-row đọc được (`:2086-2095`).

---

### B4 — Tính dòng vật tư bằng `FormulaEngine`

```python
from formula_builder.formula_utils.engine_public import FormulaEngine

engine = FormulaEngine(
    formulas=self.bom_formulas,
    safe_funcs={
        "lookup_calc_pattern": lookup_calc_pattern,
        "lookup_rule": _lookup_rule,
        "roundup": _roundup,
    },
    on_error="default",
    default_value=0,
    deterministic=True,
)
result = engine.calculate(dict(self.inputs))
```
`bom_orchestrator.py:2154-2166` ✅[V]

| Tham số | Ý nghĩa |
|---|---|
| `on_error="default"`, `default_value=0` | **Một dòng lỗi ⛔ không giết cả BOM** — dòng đó nhận 0 |
| `deterministic=True` | Cho phép cache kết quả theo đầu vào |
| `safe_funcs` | 3 hàm được phép gọi trong công thức |

⚠️ **Ngoại lệ:** **chia cho 0 vẫn là lỗi chết** (`FormulaZeroDivisionError`) — cố ý, vì nó là dấu
hiệu dữ liệu sai (kích thước = 0), không phải lỗi công thức lẻ.

Sau khi tính:

| Việc | Hàm |
|---|---|
| Gộp lỗi engine vào túi `bom_engine_errors` (**merge**, ⛔ không gán đè — giữ cảnh báo từ B2) | `:2171` |
| Hút cảnh báo phát sinh trong lúc tính (`lookup_rule` thiếu mã…) | `_drain_engine_warnings()` `:2174` |
| **Cảnh báo diện tích kính vượt khổ** `max_area_m2` (chỉ WARN, ⛔ không throw) | `_validate_glass_max_area()` `:2243` |
| Batch-fetch `output_unit` theo `calc_pattern` để hiện cột ĐVT | `:2186-2195` |

**Dòng kết quả** (`:2216-2241`) — đây chính là `lines[]` mà dialog hiển thị:

```jsonc
{ "slug", "item_code", "width", "height", "qty", "unit_qty", "total_qty",
  "unit_price", "line_total", "cost_bucket",
  "unit", "weight_per_unit", "has_weight", "trace",
  "color", "supplier_location", "install_position", "cut_angle", "note" }
```

---

### B5 — Gom cost bucket

```
fb_buckets = self._resolve_cost_buckets_via_fb()      # :2290
```

| Trường hợp | Cách gom |
|---|---|
| `AL Cost Bucket.source_type == "aggregate_from_items"` **và** có `source_config` hợp lệ | Giao cho FB `aggregate_from_items` (`rows_source="resolved"`, `rows_var="bom_result"`) |
| Còn lại | **Cộng `line_total` bằng Python** theo `cost_bucket` |

Chỉ tiêu `rows` truyền cho FB gồm đúng 2 field: `cost_bucket`, `line_total` (`:2373-2376`).

⚠️ **Hành vi hiện tại:** bucket khai `source_type` khác `aggregate_from_items` ⇒ engine ghi cảnh
báo `bucket_source_type_chua_ho_tro:<code>` rồi vẫn cộng như cũ — ⛔ không còn bỏ qua im lặng.

---

### B6 — Chạy Cost Template → ra giá bán

**Nguồn công thức (theo thứ tự ưu tiên):**

| # | Nguồn | Khi nào |
|---|---|---|
| 1 | `al_bom_vars._cost_template` → đọc **doc sống** `AL Cost Template` | khi người dùng đổi template |
| 2 | `AL BOM Version.cost_template_snapshot` | mặc định |

**Cấu hình engine:**

```python
config = EngineConfig(
    global_formulas=global_formulas,      # [{"name": line_code, "formula": calc_formula}, ...]
    extra_context=extra_context,          # inputs + buckets
    on_error="default", default_value=0, deterministic=True,
    custom_functions={"lookup_calc_pattern": ..., "lookup_rule": _lookup_rule, "roundup": _roundup},
)
engine = FlexibleFormulaEngine(config)
result = engine.calculate(dict(self.inputs))
```
`bom_orchestrator.py:2463-2476` ✅[V]

**Khác biệt với B4:**

| | B4 `FormulaEngine` | B6 `FlexibleFormulaEngine` |
|---|---|---|
| Không gian tên | **PHẲNG** (`{slug}__{field}`) | **TOÀN CỤC** (`line_code` là biến) |
| Thứ tự | Sắp xếp topo (DAG) | **Tuần tự** theo khai báo |
| Nguồn công thức | `bom_formulas` (sinh động) | `global_formulas` (từ Cost Template) |

⚠️ **Hai điểm rất dễ vấp ở B6:**

1. **Thứ tự dòng trong Cost Template là thứ tự tính.** Đặt `GIA_BAN` trước `GIA_THANH` ⇒
   `GIA_BAN` lấy giá trị cũ/0.
2. **`custom_functions` là bắt buộc.** Thiếu nó, `lookup_rule('RULE-HEIGHT-MULT', …)` báo
   `[ENGINE.UNKNOWN_FUNCTION]` (ghi rõ ở `:2457-2460`).

**Bucket nào chưa có giá trị thì mặc định `0`** — nhưng **chỉ** cho những mã thật sự được công
thức tham chiếu (quét bằng regex `\b([A-Z][A-Z0-9_]{1,30})\b`, loại các tiền tố `TONG_`, `GIA_`,
`PROFIT`, `VAT`, `DON_GIA` — `:2441-2454`), ⛔ không nạp cả bảng `AL Cost Bucket`.

**Chọn dòng giá cuối — theo CỜ, ⛔ không theo tên:**

| Cờ trên `AL Cost Template Item` | Trở thành |
|---|---|
| `is_final_price = 1` | `al_gia_vat` (`_resolve_final_price()` `:2514`) |
| `is_pre_vat_price = 1` | `al_gia_ban` (`_resolve_pre_vat_price()` `:2524`) |
| Không dòng nào có cờ | Fallback `GIA_VAT` / `GIA_BAN` (an toàn với config cũ) |

**Trace diễn giải:** mỗi `line_code` được lưu kèm chuỗi công thức **đã thay số** —
`_build_trace()` `:138` → `"0.08 × TONG_VL(14062817) = ..."` — để dialog giải thích được con số.

---

### B7 — Ghi kết quả

```python
assert_quotation_item_editable(self.quotation_item_name)          # chốt SÁT lệnh ghi

frappe.db.set_value("Quotation Item", self.quotation_item_name, {
    "al_gia_vat": self.gia_vat,
    "al_gia_ban": pre_vat_price,
    "al_bom_result": result_json,
    "rate": pre_vat_price,                                        # ⚠️ server ghi luôn rate
})

self._recalculate_quotation_totals(pre_vat_price)
frappe.db.commit()                                                # 1 commit duy nhất
```
`bom_orchestrator.py:2564-2588` ✅[V]

**`_recalculate_quotation_totals()` `:2590` — vì sao phải có:**

1. Nạp Quotation cha vào bộ nhớ, gán `rate` cho **đúng dòng đang tính**.
2. **Vô hiệu hoá trong bộ nhớ** 5 field ERPNext dùng để tự tính lại `rate`
   (`price_list_rate`, `discount_percentage`, `discount_amount`, `margin_type`,
   `margin_rate_or_amount` = 0/None) — nếu không, ca `price_list_rate > 0` sẽ **âm thầm thay giá hệ
   thống bằng giá bảng giá**.
3. `parent.calculate_taxes_and_totals()` → `set_total_in_words()`.
4. **Lưới an toàn:** nếu sau khi tính, `rate` bị đổi khác giá hệ thống (vd Pricing Rule ở v16
   can thiệp) ⇒ **`frappe.throw`** kèm hướng dẫn *"Gỡ Pricing Rule / giảm giá trên dòng rồi tính
   lại"* — ⛔ thà dừng còn hơn ghi tổng tiền sai.
5. Ghi lại **13 trường tổng tiền** (`_QUOTATION_TOTAL_FIELDS` `:190`) bằng
   `frappe.db.set_value(..., update_modified=False)` — ⛔ **không** `save()` cha, vì `save()` cập
   nhật `modified` của cha và gây `TimestampMismatchError` ở lần Save sau.

⚠️ **Hành vi hiện tại:** B7 ⛔ **không** tạo `ConfigSnapshot`. Snapshot cấu hình chỉ được tạo khi
**submit Quotation** (doc event `on_submit`).

---

## §6. Formula Builder tham gia ở đâu

### 6.1 Bảng tổng hợp

| Bước | Đối tượng FB | Hàm alumglass gọi |
|---|---|---|
| B1.4 | `get_live_context(scope_json)` — scope `AL Bom Set` | `_resolve_fb_context()` `:672` |
| B2 (giá) | `resolve_all_bindings_batch` / handler `aluminum_price_composite` | `_fetch_composite_prices_via_fb()` `:1530` |
| B2 (hằng số) | `resolve_all_bindings_batch` + `source_type = constant` | `fb_config.get_named_constant()` |
| B3 | `table_formula_builder.normalize_global` | `_normalize_items_ref()` `:2114` |
| B4 | `FormulaEngine` + `safe_funcs` | `b4_calculate_bom_items()` `:2150` |
| B5 | `resolve_all_bindings_batch` + `aggregate_from_items` | `_resolve_cost_buckets_via_fb()` `:2304` |
| B6 | `FlexibleFormulaEngine` + `EngineConfig.custom_functions` | `b6_calculate_cost_template()` `:2395` |
| — | `compile_expression` (safe_eval) | `al_quantity_calc_method._compile_calc_fn` |

### 6.2 `source_type` của `Formula Variable Binding` dùng trong app này

| source_type | Nguồn gốc | Dùng cho |
|---|---|---|
| `constant` | FB built-in | `VAT_RATE`, `OH_VC_PCT`, `OH_QLY_PCT` |
| `linked_doctype_field` | FB built-in | Biến hệ thống (`OFFSET_*`, `NC_*_PCT`, `PROFIT_MARGIN`) — đọc field của doc liên kết |
| `composite_key_lookup` | FB built-in | Tra giá theo ma trận N chiều |
| `aggregate_from_items` | FB built-in | Gom cost bucket kiểu SUMIF |
| **`aluminum_price_composite`** | **alumglass đăng ký** (`fb_handlers.py`) | Tra giá nhôm/kính theo composite key; 2 chế độ `exact_match` / `multiplier_chain` |
| **`glass_master_data`** | **alumglass đăng ký** (`fb_handlers.py`) | Tra `total_thick_mm` / `glass_type` của kính |

### 6.3 Ba hàm alumglass tiêm vào FB

Đăng ký **module-level** trong `bom_orchestrator.py` để B4 và B6 dùng **chung một bản**:

| Hàm | Dòng | Việc | Khi lỗi |
|---|---|---|---|
| `lookup_calc_pattern(pattern, w, h, weight, extra?)` | `formula_handlers.py` | Tính `unit_qty` theo `AL Quantity Calc Method` | Trả 0 + cảnh báo |
| `lookup_rule(rule_code, input)` | `:70` | Tra `AL Calculation Rule` (CONSTANT / THRESHOLD / LOOKUP) | ⛔ **không im lặng**: ghi cảnh báo `lookup_rule_thieu_ma:<code>` rồi trả 0 |
| `roundup(x, y=None)` | `:97` | Làm tròn **LÊN** kiểu Excel | — |

⚠️ **`roundup` — ngữ nghĩa hiện tại:**

| Gọi | Kết quả |
|---|---|
| `roundup(2.5)` / `roundup(x, 0)` | `math.ceil(x)` — giữ nguyên hành vi cũ |
| `roundup(2.111, 2)` | `2.12` |
| `roundup(1234, -2)` | `1300` |
| `roundup(-2.5, 0)` | **`-3`** — Excel làm tròn **ra xa 0** |

⚠️ **Vì sao alumglass phải có hàm này riêng, ⛔ không dùng thẳng của FB:** `formula_builder` **đã có**
`roundup` (`formula_utils/funcs/math.py:182`), nhưng viết bằng `math.ceil(x * 10**d) / 10**d` ⇒ với số
**âm** nó làm tròn **về phía 0** (`roundup(-2.5, 0)` = `-2`), ⛔ **sai ngữ nghĩa Excel**. alumglass truyền
`_roundup` qua `safe_funcs`/`custom_functions`, mà `safe_funcs` **đè** `BASE_FUNCS`
(`engine_core.py:256-258`) ⇒ bản đúng đang thắng. ⇒ ⛔ **KHÔNG gỡ hàm này** cho tới khi FB sửa gốc —
chi tiết + đo đạc ở §6.5 và §6.6 mục 1.5.

### 6.4 Túi lỗi có cấu trúc — `al_bom_result["errors"]`

Kết quả tính mang theo **2 túi cảnh báo**, ⛔ không nuốt lỗi:

```jsonc
"errors": {
  "bom_items":     { "<key>": "<câu tiếng Việt>", ... },
  "cost_template": { "<key>": "<câu tiếng Việt>", ... }
}
```

Một số khoá thường gặp:

| Khoá | Khi nào |
|---|---|
| `thieu_gia_item:<item_code>` | Không tìm được Item Price khớp composite key |
| `gia_goc_thieu_dong_tran:<code>` | Chế độ `multiplier_chain` thiếu dòng gốc |
| `thieu_gia_goc:<code>` | Chế độ `multiplier_chain` thiếu giá gốc |
| `lookup_rule_thieu_ma:<rule_code>` | Công thức tham chiếu mã rule không tồn tại |
| `<slug>__max_area_exceeded` | Diện tích kính vượt `AL Glass Master.max_area_m2` |
| `bucket_source_type_chua_ho_tro:<code>` | Cost Bucket khai source_type chưa hỗ trợ |
| `phan_tram_mo_ho_bang_1__warn:<key>` | Biến % có giá trị đúng bằng 1 |

Chuỗi ghi nhận: `_record_engine_warning()` `:59` → `composite_pricing.add_engine_warning()` →
`_drain_engine_warnings()` `:1459` → 2 túi trong `al_bom_result["errors"]`.

---

### 6.5 Đánh giá mức độ tận dụng `formula_builder`

**Phép thử dùng để chấm** (lấy từ `BAN-FULL-A-Z.md` PHẦN A.1, giữ nguyên tinh thần):
*"ngành khác có cần y hệt cơ chế này không, chỉ khác data?"* — **có** ⇒ thuộc FB, alumglass
⛔ **không được tự viết**; **không** ⇒ thuộc alumglass, viết là đúng.

**Thang điểm dùng ở đây:**

| Mức | Nghĩa |
|---|---|
| 🟢 | Dùng đúng cơ chế FB, ⛔ không có code nhà trùng chức năng |
| 🟡 | Có code nhà, nhưng **chính đáng** (đặc thù ngành, hoặc FB chưa có) — đã cân nhắc và giữ có lý do |
| 🔴 | Tự viết thứ FB **đã có sẵn** ⇒ nợ kỹ thuật thật |

#### Bảng chấm theo lớp

| Lớp | Năng lực | alumglass làm gì | Mức |
|---|---|---|---|
| **Engine** | `FormulaEngine` (DAG + topo) cho B4 | Gọi thẳng `engine_public.FormulaEngine` `:2151` | 🟢 |
| **Engine** | `FlexibleFormulaEngine` + `EngineConfig.custom_functions` cho B6 | Gọi thẳng `:2393`, `:2462` | 🟢 |
| **Engine** | `normalize_global` (B3) | Gọi `table_formula_builder` | 🟢 |
| **Biểu thức** | `safe_eval.compile_expression` | Dùng ở B4/B6 **và** ở `AL Quantity Calc Method` (re-export `:17`) — ⛔ không `eval()` trần chỗ nào | 🟢 |
| **Data source** | `get_live_context` (B1.4) | Dùng, scope `AL Bom Set` | 🟢 |
| **Data source** | `resolve_all_bindings_batch` (B2, B5) | Dùng cho **cả** giá lẫn gom bucket | 🟢 |
| **Scope binding** | `binding_scope.get_scope_bindings_multi` | Dùng đúng `:1281–1317`, kèm log cảnh báo khi FB bản cũ thiếu | 🟢 ⭐ |
| **Đăng ký** | `@register_source` + `hooks.fb_source_types` | 2 source type (`hooks.py:79-82`), có `config_schema`, fingerprint, `default_cache_ttl` | 🟢 |
| **Gom bucket** | platform `aggregate_from_items` | ⭐ **Đã bỏ handler nhà** `cost_bucket_aggregate` (C2/v28_11) để dùng type của FB | 🟢 ⭐ |
| **Nhập liệu** | `fb_source_types` đăng ký qua `hooks.py` | 2 source type, `hooks.py:79-82` | 🟢 |
| **Bề mặt công khai** | FB có `integration.py` — *"Other apps should import from here rather than reaching into internals"* | Nhập thẳng từ `api.*`, `formula_utils.*`, `security.*` | 🟡 |
| **Tra giá** | `composite_key_lookup` — ⚠️ **FB đã có `multiplier_chain`** | Tự viết `aluminum_price_composite` + `composite_pricing.py` | 🟡 → cần đối chiếu |
| **Tra kính** | `linked_doctype_field` · `child_table_lookup` · `matrix_lookup` | Tự viết `glass_master_data` | 🟡 |
| **Tra bảng rule** | `range_lookup` · `child_table_lookup` · `fallback_chain` (đều **đã có mã**) | Tự viết `lookup_rule` + `lookup_calc_pattern`, tiêm qua `safe_funcs`/`custom_functions` | 🔴 |
| **Làm tròn** | FB có `roundup`/`rounddown` (`funcs/math.py:182-189`) **nhưng dùng `ceil`/`floor` ⇒ SAI với số âm** (Excel làm tròn *ra xa 0*) | Tự viết `_roundup` (`:97-111`) **xử lý đúng dấu**, tiêm đè qua `safe_funcs`/`custom_functions` | 🟡 **bản VÁ** ⛔ không phải bản trùng |
| **Cost Bucket** | Vocabulary `source_type` + `config_schema` từng type của FB | Chép tay **3 nơi**; engine **chỉ thực thi 1/8** giá trị khai | 🔴 |
| **Cache** | `supports_cache` / `default_cache_ttl` của FB | Tự viết `_DB_PATTERN_CACHE` + `_NEGATIVE_CACHE` (`formula_handlers.py:88-89`) | 🟡 |
| **Snapshot** | FB có `Snapshot`/`SnapshotManager` + DocType `Formula Snapshot` | Tự viết `ConfigSnapshot` (chỉ tạo khi submit) | ⚠️ **chưa kiểm** |

✅[V] **Ba dòng dưới đây đã ĐỔI so với bản nháp đầu** — sau khi đọc trực tiếp mã FB tại `0ed8e1b`.
*(Dòng 3 đổi **hai lần**: lần đầu chỉ thấy tên hàm trong `funcs/math.py` rồi kết luận "FB đã có ⇒ bản
nhà là code trùng"; lần hai đọc kỹ **thân hàm** mới thấy FB sai dấu. Ghi lại vì đây là kiểu sai rất dễ
mắc: **trùng tên hàm ⛔ không có nghĩa là trùng hành vi**.)*

1. **`composite_key_lookup` ĐÃ có `multiplier_chain`** (`data_source_registry.py:2599-2601`: `match_mode`
   enum gồm `multiplier_chain`, kèm config `multipliers` map `dim → {doctype, match_field, match_value,
   value_field}`). ⛔ Lý do cũ để giữ `aluminum_price_composite` — *"type generic chưa có 2 chế độ"*
   (`BAN-FULL-A-Z.md` PHẦN I) — **đã hết hiệu lực**. Xem §6.6 nhóm 2.
2. **`range_lookup` và `child_table_lookup` ĐÃ có mã** (`:2739`, `:2821`) ⇒ việc tự viết `lookup_rule`
   giờ là 🔴 thật, ⛔ không còn là "chờ FB".
3. **FB CÓ `roundup`/`rounddown`** (`funcs/math.py:182-189`) **nhưng ⛔ KHÔNG cùng ngữ nghĩa Excel.**
   FB viết `math.ceil(x * 10**d) / 10**d` — với `x` **âm** thì `ceil` làm tròn **về phía 0**, còn Excel
   ROUNDUP làm tròn **ra xa 0**. Đo được: `roundup(-2.5, 0)` → **alumglass `-3`** (đúng Excel) vs
   **FB `-2`** (sai). `rounddown` lệch tương tự ở đầu âm (`floor` → về `-∞`, Excel về 0).
   ⇒ `_roundup` của alumglass (`bom_orchestrator.py:97-111`, có nhánh
   `ceil if scaled >= 0 else floor`) là **BẢN VÁ ngữ nghĩa**, ⛔ **không phải code trùng**.
   Thứ tự ưu tiên ✅[V] đã kiểm: `engine_core.py:256-258` — `base = BASE_FUNCS.copy();
   base.update(safe_funcs)` ⇒ **`safe_funcs` ĐÈ** ⇒ **bản vá đang thắng**, hệ thống đang chạy ĐÚNG.
   ⚠️ **Bẫy:** thấy "FB đã có `roundup` rồi" rồi bỏ bản nhà là **gỡ mất bản vá, đưa lỗi số âm vào**.
   Xem §6.6 mục 1.5 (đã đảo chiều so với bản nháp).
   ⚠️ **Mức ảnh hưởng hiện tại: TIỀM ẨN.** Mọi chỗ gọi trong cấu hình hiện có đều là
   `roundup(H_mm/700, 0)` với `H_mm` **dương** ⇒ chưa có sai số nào đang xảy ra; lỗi chỉ thành thật khi
   có công thức cho ra số âm (vd `roundup((a-b)/700, 0)` với `a < b`).

**Bối cảnh quy mô — đo từ phía alumglass (✅[V]):**

| Đo gì | Số | Bằng chứng |
|---|---|---|
| `source_type` **riêng của alumglass** (đăng ký qua `hooks.fb_source_types`) | **2** | `hooks.py:79-82` → `aluminum_price_composite`, `glass_master_data` (`fb_handlers.py:14` dùng `@register_source`) |
| Tên trong vocabulary `AL Cost Bucket` **trùng tên type của FB** | **7 / 8** | `al_cost_bucket.json:83` — `aggregate_from_items`, `doctype_query`, `custom_function`, `constant`, `pipeline`, `conditional`, `fallback_chain` |
| Tên ⛔ **không** phải type của FB trong vocabulary đó | **1** | `formula` — nghĩa nội bộ của alumglass ("bucket tính bằng công thức"), ⛔ không phải nguồn dữ liệu |
| `source_type` **nhà đã GỠ** để dùng của FB | **1** | `cost_bucket_aggregate` → `aggregate_from_items` (patch `v28_11`) |
| Giá trị `source_type` mà **engine Cost Bucket THỰC THI** | **1 / 8** | `bom_orchestrator.py:2341` chỉ nhận `aggregate_from_items`; giá trị khác → cảnh báo `bucket_source_type_chua_ho_tro` (`:2346-2353`) rồi gom bằng tổng `line_total` |

⚠️ **Vocabulary `source_type` của Cost Bucket đang bị chép tay ở 3 nơi, ⛔ không nơi nào hỏi FB:**
(a) Select cứng trong `al_cost_bucket.json:83`; (b) list Python `ALCostBucket.VALID_SOURCE_TYPES`
(`al_cost_bucket.py:12-16`) — **đúng 8 tên đó, chép lại lần hai**; (c) câu cảnh báo trong engine
(`bom_orchestrator.py:2350`) chỉ nêu `aggregate_from_items`. ⇒ FB thêm/đổi type thì **cả 3 nơi ⛔ không
biết**, trong khi UI vẫn cho admin chọn **7 giá trị engine ⛔ không chạy** — chọn xong ⛔ không có gì báo
là sẽ ⛔ không có tác dụng (trừ khi bucket đó là LEAF và có mặt trong `bom_result`).

⚠️ **Số "9/19 đang dùng" của bản nháp đã BỎ** — con số đó suy từ grep mã nguồn và **tính nhầm**
(`composite_key_lookup` bị tính là "đang dùng" trong khi alumglass dùng type **nhà**
`aluminum_price_composite`). Bảng trên thay bằng số đo được. ⚠️ **Vẫn chưa đối chiếu DB**: binding thật
nằm ở DocType `Formula Variable Binding` — xem §6.7.

⚠️ **Bộ hàm công thức của FB rộng hơn nhiều so với những gì alumglass dùng**: có sẵn `vlookup`,
`xlookup`, `index`, `match`, `sumif/sumifs/countif/averageif`, `IF/IFS/SWITCH`, `safe_div`,
`number_to_words` (đọc số thành chữ **tiếng Việt**), `allocate`/`AllocationEngine` (7 phương pháp
phân bổ), `solve_linear_on_graph`… ⇒ **trước khi tự viết một hàm công thức mới, phải tra
`formula_utils` của FB trước** — rất dễ viết lại thứ đã có.

⚠️ **⚠️ Bẫy đọc tài liệu FB:** `docs/imported_reference_table.md` và `docs/optimizer_solver.md`
mô tả config schema **rất cụ thể** nhưng **⛔ không có mã** (cả hai tự ghi "DESIGN ONLY" ở dòng 3;
grep toàn app ⛔ không có handler). ✅[V] Tài liệu FB nói *"Built-in batchable handlers: 4 type"*
(`README.md:1174`) nhưng mã có **10** — **⛔ đừng tin README của FB**, đối chiếu mã
(`BAN-FULL-A-Z.md:5` đã cảnh báo đúng điều này).

**Hai điểm 🟢⭐ đáng nêu riêng vì hiếm app làm đúng:**

1. **`binding_scope` (A5/v28_11).** Chính tài liệu FB (`docs/fb_source_type_contract.md` §9.1) nêu
   **đích danh** `alumglass._get_pricing_bindings` và yêu cầu app **phải** import hàm scope của FB
   thay vì tự lọc theo `applies_to_doctype`. ✅[V] alumglass **đã làm đúng** — `bom_orchestrator.py:1281`
   import `get_scope_bindings_multi`, và giữ nhánh lọc tay **chỉ** làm fallback cho FB bản cũ, **có log
   cảnh báo** (D9, `:1286-1288`) chứ ⛔ không im lặng. Comment tại chỗ nói rõ lý do: *"KHÔNG tự fork luật
   lọc … → có thể lệch với preview/get_live_context"*.
2. **Bỏ code nhà để dùng type platform.** `cost_bucket_aggregate` của alumglass đã được **gỡ** và
   migrate sang `aggregate_from_items` của FB qua patch `v28_11` (`hooks.py:75-78` ghi rõ). Đây là ví
   dụ mẫu của việc **xoá** code nhà thay vì giữ song song.

#### Kết luận mức độ tận dụng

**Tận dụng TỐT ở lớp engine và lớp binding** — đúng những chỗ khó và dễ sai nhất: ⛔ không tự viết
engine công thức, ⛔ không tự parse biểu thức, ⛔ không tự lọc scope binding, và đã có ít nhất 1 lần
**gỡ** code nhà để dùng type của FB.

**Còn dư địa ở lớp "tra dữ liệu để lấy giá trị" — xếp theo mức:**

| Chỗ | Mức | Vì sao |
|---|---|---|
| `lookup_rule` + `lookup_calc_pattern` | 🔴 | FB **đã có mã** `range_lookup` / `child_table_lookup` (`:2739`, `:2821`); chặn duy nhất còn lại là **batch multi-row** |
| Vocabulary `source_type` của Cost Bucket | 🔴 | Chép tay **3 nơi**; engine thực thi **1/8** giá trị mà UI cho admin chọn |
| `aluminum_price_composite` (+ `composite_pricing.py`) | 🟡 → **cần đối chiếu** | FB **đã có** `multiplier_chain`, nhưng **ngữ nghĩa hệ số khác** ⇒ §6.6 mục 2.2 |
| `glass_master_data` | 🟡 | Tra master data theo mã — đúng loại việc FB sinh ra để làm, nhưng ⛔ chưa có type tương đương rõ ràng |
| `_roundup` | 🟡 | ⛔ **GIỮ** — là **bản vá ngữ nghĩa** (FB sai dấu với số âm), ⛔ không phải code trùng |

⚠️ **Nhưng ⛔ đừng vội "migrate cho sạch":** các chỗ 🟡 đã được cân nhắc **có ghi vết** và **chủ động
giữ** (`BAN-FULL-A-Z.md` PHẦN I) — lý do nằm ở §6.6 nhóm 3. Migrate lại mà ⛔ không có gì mới ở FB là
đổi rủi ro lấy 0 lợi ích. Ngược lại, hai chỗ 🔴 **⛔ không còn lý do cũ nào đứng vững** — nhưng vẫn phải
qua §6.6 nhóm 1/2 (rủi ro thấp / cần phối hợp FB trước) chứ ⛔ không làm thẳng.

---

### 6.6 Đề xuất tận dụng thêm — chia theo rủi ro

#### Nhóm 1 — Làm được ngay, rủi ro thấp

| # | Việc | Vì sao | Chạm ở đâu |
|---|---|---|---|
| 1.1 | **Bỏ Select cứng `source_type` trên `AL Cost Bucket`, đồng bộ từ FB** | FB có API `list_source_types()` (19 built-in + mọi custom) — Select cứng ⛔ **không tự đồng bộ**, nên FB thêm type mới thì UI ⛔ không cho chọn (lệch đã được ghi nhận ở `docs/DANH-GIA-TOAN-DIEN-ALUMGLASS.md:116`) | DocType `AL Cost Bucket` |
| 1.2 | **Validate `source_config` lúc LƯU, dùng `validate_binding_source_config` của FB** | Hiện config sai chỉ lộ ra **lúc tính giá** (sau khi người dùng đã cấu hình xong) — FB có sẵn hàm validate theo `config_schema` để bắt ngay khi lưu | form binding / cost bucket |
| 1.3 | **Thêm nút "Test" cho binding, dùng `test_data_source_with_doc`** | FB có sẵn API test config trên **doc thật** + `preview_batch_groups` để xem trước nhóm batch. Admin tự kiểm được, ⛔ không phải tính cả báo giá rồi mới biết sai | form binding |
| 1.4 | **Sửa lệch giữa 2 nhánh tra giá** | Nhánh `multiplier_chain` ⛔ **không** gọi `_compute_color_price_overrides()` ⇒ màu theo **từng vị trí** bị bỏ qua (đã ghi ở §5 B2). Cho **cả 2 nhánh** đi qua cùng một hàm — sửa nhỏ, ⛔ không đổi số golden ở chế độ đang chạy | `bom_orchestrator.py:1618` |
| 1.5 | ⛔ **KHÔNG bỏ** `_roundup` — việc đúng là **báo FB sửa gốc** `roundup`/`rounddown` | FB dùng `ceil`/`floor` nên **sai dấu với số âm** (`roundup(-2.5, 0)`: FB `-2`, Excel & alumglass `-3`). Bản nhà là **bản vá đang thắng** (`safe_funcs` đè `BASE_FUNCS`) ⇒ ⛔ gỡ bây giờ là **hạ cấp ngữ nghĩa âm thầm**, ⛔ không ai thấy vì test hiện có đều dùng `H_mm` dương | `formula_utils/funcs/math.py:182-189` (**FB**) |
| 1.6 | **Đưa import FB về `formula_builder.integration`** | FB ghi rõ `integration.py` là **cửa chính thức**: *"Other apps should import from here rather than reaching into internals"*. Hiện alumglass nhập thẳng `api.*` / `formula_utils.*` / `security.*` | 12 điểm import (xem ghi chú dưới) |

⚠️ **Về 1.1 — ranh giới với "GATING" đang mở sẵn trong mã.** `bom_orchestrator.py:2287-2288` có ghi
chú: *"⚠ GATING (chưa quyết — báo Elon/Owner): giữ vocabulary Cost Bucket hiện có + handler resolve
(khuyến nghị). Đổi hẳn sang FVB (bỏ vocab 8) cần Owner duyệt."* ⇒ **1.1 ⛔ KHÔNG phải việc bị gate**:
1.1 ⛔ không đổi vocabulary, ⛔ không bỏ type nào — chỉ **lấy danh sách + luật validate từ FB** thay cho
bản chép tay. Việc **bị gate** là *"bỏ vocab 8, chuyển hẳn Cost Bucket sang FVB"* — ⛔ **đừng gộp hai
việc này làm một**, gộp là tự chặn một việc rủi ro thấp bằng một quyết định của Owner ⛔ chưa cần tới.

✅[V] **Về 1.2 — chỗ trùng cụ thể, ⛔ không phải suy đoán.** `al_cost_bucket.py:33-47` tự viết 4 luật
config: `doctype_query` cần `doctype` + `fieldname`; `aggregate_from_items` cần `sum_field`; `pipeline`
cần `steps`; `fallback_chain` cần `chain` — **đúng những gì `config_schema` của FB đã khai** cho từng
type. Cộng với vocabulary chép tay **3 nơi** (§6.5), đây là phần "viết lại tính năng FB đã có" **rõ
nhất và dễ sửa nhất** trong cả app.

✅[V] **Về 1.5 — thứ tự ưu tiên đã kiểm XONG, và kết quả ĐẢO CHIỀU đề xuất cũ.**
`engine_core.py:256-258` = `base = BASE_FUNCS.copy(); base.update(safe_funcs)` ⇒ **`safe_funcs` ĐÈ**
`BASE_FUNCS` (alumglass đã ghi nhận đúng điều này tại `al_cost_template.py:91-92`). Hệ quả: hôm nay
**bản vá của alumglass đang thắng** ⇒ `roundup` đang chạy **ĐÚNG** ngữ nghĩa Excel. ⛔ Vì vậy **tuyệt
đối ⛔ không bỏ bản nhà trước khi FB sửa `funcs/math.py`** — bỏ bây giờ là tự tay đưa lỗi số âm vào, mà
test hiện có ⛔ không bắt được (mọi cấu hình đang gọi `roundup(H_mm/700, 0)`, `H_mm` luôn dương).
Đây là ví dụ cho nguyên tắc: *"trùng tên hàm ⛔ không có nghĩa là trùng hành vi"*.

⚠️ **Về 1.6 — chỉ một PHẦN import đi được qua `integration.py`.** ✅[V] `integration.__all__`
(`integration.py:81-98`) **có**: `FlexibleFormulaEngine`, `EngineConfig`, `resolve_all_bindings_batch`,
`BatchBindingResolver`, `register_source`, `list_source_types`, `validate_binding_source_config`,
`test_data_source`, `MultiTableFormulaBuilder`, `normalize_global`. ⇒ **4 nhóm import của alumglass
đi được ngay**: `resolve_all_bindings_batch` (`bom_orchestrator.py:1580`, `:2316`;
`fb_config.py:44`), `normalize_global` (`:2136`; `formula_validate.py:36`),
`FlexibleFormulaEngine`/`EngineConfig` (`:2428`), `register_source` (`fb_handlers.py:14`).
Còn lại — `FormulaEngine` (từ `formula_utils`, vốn là API công khai của `formula_utils`),
`compile_expression`/`ExpressionPolicy` (`security.safe_eval`), `get_live_context`
(`api.formula_builder`), `get_scope_bindings_multi` (`api.binding_scope` — tài liệu FB **khuyến nghị
dùng**), `BASE_FUNCS`/`FormulaValidator` — **⛔ không** nằm trong `integration.py`, nên giữ nguyên
là hợp lệ. ⛔ Đừng "gom cho đẹp" mà nhập từ chỗ không được xuất.

#### Nhóm 2 — Nên làm, nhưng cần **phối hợp với FB** trước

| # | Việc | Chặn bởi |
|---|---|---|
| 2.1 | **FB bổ sung API resolve NHIỀU DÒNG một lần** ⇒ mở khoá migrate `lookup_rule` + `lookup_calc_pattern` sang `range_lookup` / `child_table_lookup` / `fallback_chain` | ⚠️ **Hai năng lực đích ĐÃ CÓ MÃ** (`data_source_registry.py:2739`, `:2821`) — chặn duy nhất còn lại là batch: `resolve_all_bindings_batch` nhận **1 row-context mỗi lần gọi**, mà rule resolve theo **từng dòng BOM** với `rule_input` riêng ⇒ chưa có API multi-row thì "batch" ⛔ không có ý nghĩa. Đây là chặn **kỹ thuật thật**, ⛔ không phải lười (`BAN-FULL-A-Z.md` PHẦN I) |
| 2.2 | **Đối chiếu `composite_key_lookup` (FB, có `multiplier_chain`) với `aluminum_price_composite` (nhà)** | ⚠️ **Lý do cũ đã hết hiệu lực**: `BAN-FULL-A-Z.md` PHẦN I giữ type nhà vì *"generic type chưa có 2 chế độ"* — nay FB **đã có** `multiplier_chain` + `multipliers` (`:2599-2601`). ⚠️ **Nhưng ⛔ chưa kết luận thay được**, vì **ngữ nghĩa khác nhau**: FB áp hệ số cho **chiều bị RỚT** khi `fallback_keys` rút dần chiều; alumglass áp hệ số **màu** tra từ `AL Color Standard`/mapping. Phải đọc kỹ `_handle_composite_key_lookup` rồi mới quyết |
| 2.3 | **Cân nhắc `matrix_lookup` / `reuse_formula_result` cho tra giá** | FB **đã có mã** (`:2013`, `:2283`). `matrix_lookup` = bảng 2 chiều + fallback `ANY`; `reuse_formula_result` = tái dùng kết quả chứng từ khác (⭐ có thể dùng cho ca nhiều báo giá cùng BOM/Version) |

#### Nhóm 3 — ⛔ **KHÔNG** nên làm (đã cân nhắc, giữ nguyên có lý do)

| Việc | Vì sao ⛔ không làm |
|---|---|
| Migrate `lookup_calc_pattern` + cache `_DB_PATTERN_CACHE` | `compile_expression` của FB **đã tự cache** bước compile; cache nhà chỉ cache **1 lượt tra DB** đơn giản và **có hook xoá đúng** (`AL Quantity Calc Method.on_update/on_trash`, `hooks.py:69-72`) ⇒ mức dư thừa **thấp**, ⛔ không đáng đổi một hệ đang chạy đúng có test riêng |
| Migrate `system_variable_resolver.py` sang `fallback_chain` + `child_table_lookup` | Cần khảo sát số biến hệ thống thật, xử lý hành vi *"parse số nếu được, giữ chuỗi nếu không"* mà `fallback_chain` chưa có, và 2 lớp fallback riêng của `bom_orchestrator` (`default_value`, `AL Calculation Rule CONSTANT`). ⇒ **dự án riêng**, ⛔ không chen vào |
| ⛔ **ĐÃ RÚT khỏi danh sách này:** *"Migrate `aluminum_price_composite` → `composite_key_lookup`"* | Lý do cũ (*"type generic chưa có 2 chế độ"*) **đã hết hiệu lực** — FB nay có `multiplier_chain`. ⇒ chuyển sang **§6.6 nhóm 2.2** để đối chiếu ngữ nghĩa ⛔ **trước khi** kết luận giữ hay bỏ |

✅[V] **Nguyên tắc chung rút ra:** tiêu chí để một việc thuộc nhóm 1/2 hay nhóm 3 ⛔ **không phải** "có
trùng code không", mà là **"FB đã có năng lực tương đương CHƯA"**. Trùng code mà FB chưa có năng lực ⇒
giữ (nhóm 3). FB đã có năng lực mà mình chưa dùng ⇒ làm (nhóm 1/2).

⚠️ **Nhưng "FB đã có" là trạng thái ĐỘNG — phải kiểm lại theo từng mốc.** ✅[V] Ba kết luận trong
`BAN-FULL-A-Z.md` PHẦN I đã **cũ** so với FB `0ed8e1b` (2 trong đó chính là `range_lookup` /
`child_table_lookup` **nay đã có mã**, và `multiplier_chain` **nay đã có trong type generic**). ⇒
**Trước khi viện dẫn "FB chưa có" để biện minh giữ code nhà, phải grep lại FB** — nếu không, cái cớ
đúng của năm ngoái thành lý do sai của năm nay.

---

### 6.7 Việc cần kiểm trước khi chốt đề xuất

**Đã giải quyết** (nhờ đọc trực tiếp registry FB tại `0ed8e1b`) — ⛔ không còn nằm trong danh sách mở:

| Mục | Kết luận |
|---|---|
| `matrix_lookup` | ✅ **Có mã** (`data_source_registry.py:2013`) — bảng 2 chiều + fallback `ANY`. ⇒ §6.6 nhóm 2.3 đứng vững |
| `range_lookup` · `child_table_lookup` | ✅ **Có mã** (`:2739`, `:2821`) ⇒ rào cản migrate `lookup_rule` **chỉ còn là batch multi-row** |
| `imported_reference_table` | ⛔ **Không có mã** — chỉ là design (`docs/imported_reference_table.md:3` ghi "DESIGN ONLY") ⇒ `alumglass.excel_io` ⛔ **không** trùng FB |
| `optimizer_solver` | ⛔ **Không có mã** (bản cắt 1D/2D). ⚠️ Nhưng FB **có** `AllocationEngine` (7 pp phân bổ) + `solve_linear_on_graph` — 2 thứ **khác** mục đích |
| `reuse_formula_result` | ✅ **Có mã** (`:2283`) |
| Danh sách `source_type` FB | ✅ **19 built-in** (đếm được 19 hàm `_handle_*` trong `data_source_registry.py`) + **2 custom của alumglass**. Số đo đầy đủ ở §6.5 |
| Thứ tự ưu tiên `safe_funcs` | ✅ **`safe_funcs` ĐÈ `BASE_FUNCS`** — `engine_core.py:256-258` (`base = BASE_FUNCS.copy(); base.update(safe_funcs)`). Alumglass đã ghi nhận đúng tại `al_cost_template.py:91-92` |
| `$snap.field` | ✅ **Đường dẫn CHẾT.** Nhánh đọc **có** mã (`variable_resolver.py:165-168`: `$` → `$snap.` → `_get_snapshot`), nhưng `_get_snapshot` (`:327-330`) đọc Redis khoá `formula_snapshot:{doctype}:{docname}` — ⚠️ grep **toàn bộ FB**: khoá này xuất hiện **đúng 1 lần, ở chính chỗ ĐỌC**; ⛔ không có chỗ nào GHI. ⇒ `$snap.*` **luôn trả `None`**, và với `on_error="default"` thì `None` thành `0` **im lặng**. ⚠️ Chưa loại trừ việc app khác ghi bằng khoá **ghép chuỗi** (grep chuỗi thô ⛔ không bắt được) — nhưng trong FB thì chắc chắn không có |
| `Formula Allowed Function` | ✅ **Hai lỗi đều thật, và ⛔ không phải chuyện đặt tên cho đẹp.** Field thật là **`enabled`** (Check, `default: "1"`), còn seed ghi key **`is_enabled`** (`install.py:29`, `patches/v30_0_0.py:65`, `api/formula_builder.py:731`) — key ⛔ **không phải field** nên bị bỏ **im lặng**. Nguy hơn: **2 chỗ đọc LỆCH NHAU** — `settings_cache.py:50` đọc `enabled` **trước** ✔, còn `formula_table_api.py:99` **chỉ** đọc `is_enabled` với `default=True` ✘ ⇒ **bỏ tick "Enabled" được tôn trọng ở đường này và ⛔ bị ngó lơ ở đường kia** |

**Còn mở — ⚠️ chưa kiểm:**

| Mục | Cần kiểm gì |
|---|---|
| **Binding thật trên site** | ⚠️ Toàn bộ số ở §6.5 đều đo từ **mã nguồn**; binding thật nằm ở DocType `Formula Variable Binding`. **Phải đếm trên site** mới chắc — và mới biết có binding nào đang bật mà ⛔ không ai nhớ |
| `ConfigSnapshot` vs `Formula Snapshot` | FB có DocType `Formula Snapshot` + hash kép SHA-256 + `revise`/`lock`/`revision_history`. `ConfigSnapshot` của alumglass có **trùng** năng lực không, hay chỉ là bản ghi cấu hình thuần? ⛔ Chưa đọc phần `ConfigSnapshot` phía alumglass |
| Hệ số của `composite_key_lookup` | ⚠️ Phải đọc `_handle_composite_key_lookup` (`data_source_registry.py:2619-2738` — ⛔ **không** phải `:2580-2669` như bản nháp ghi) để chốt §6.6 mục 2.2: ngữ nghĩa hệ số của FB có **thay được** `aluminum_price_composite` không |

⚠️ **Một cảnh báo dùng chung cho mọi đề xuất migrate:** bật một `source_type` mới hoặc đổi
`source_config` **có thể đổi số golden** — xem §11.2 mục 8 và §5 B2. Trước khi đổi, chạy lại
`run_test.py` (§12.2) và đối chiếu 22.717.289 / 47.430.808.

⚠️ **Và một cảnh báo về nguồn tin:** ⛔ **đừng tin README / docs của FB** khi chúng mâu thuẫn với mã —
đã đo được **7 chỗ lệch** (README nói 4 handler batchable, mã có 10; README nói `source_type` là
`Select` cứng, mã dùng `Autocomplete` nạp động từ `list_source_types`; 2 tài liệu mô tả config schema
của type **⛔ không tồn tại trong mã**). ✅[V] Điều này **có lợi cho alumglass**: vì `source_type` là
`Autocomplete` nạp động, nên **thêm type mới ⛔ không phải sửa JSON** của FB — nhưng Select cứng trên
`AL Cost Bucket` của alumglass thì **vẫn phải sửa** (§6.6 mục 1.1).

---

## §7. Ví dụ 1 — CDMQ-2C, tính từng bước

> Nguồn: `alumglass/run_test.py:64-79` (`test_cdmq_2c`) + số đã ghi vết ở
> `docs/quotation-pricing-flow.md` §9. Golden kỳ vọng `22,717,289` (dung sai `<1.000`).
> ⚠️ Chưa chạy lại trên máy soạn tài liệu.

**Sản phẩm:** cửa đi 2 cánh mở quay + ô kính trên. BOM `BOM-CDMQ-2C`.

### Bước 0 — Dữ liệu đầu vào

| Nguồn | Giá trị |
|---|---|
| Người dùng nhập | `W_mm = 2400`, `H_mm = 2600`, `n_panel = 2`, `TransomHeight_mm = 600`, `aluminum_color = WHITE`, `aluminum_origin = IMPORT`, `aluminum_thickness = 20`, `aluminum_surface = POWDER_COATED` |
| Biến hệ thống (B1) | `OFFSET_FRAME = 48`, `OFFSET_GLASS = 90`, `OFFSET_FIXED = 50`, `OFFSET_DO_NGANG = 48` |
| Tỉ lệ (B1) | `NC_SX_PCT = 0.08`, `NC_LD_PCT = 0.12`, `PROFIT_MARGIN = 0.16` |
| Hằng số (B1.2) | `VAT_RATE = 0.10`, `OH_VC_PCT = 0.03`, `OH_QLY_PCT = 0.03` |
| Không nhập | `installation_height_m` → mặc định `3` ⇒ `lookup_rule('RULE-HEIGHT-MULT', 3) = 1.0` |

### Bước 1 — B0: chốt phiên bản

`Quotation Item.al_bom = "BOM-CDMQ-2C"` → `AL BOM.current_version` → `AL BOM Version` đã Published.
Mọi số bên dưới lấy từ `bom_set_snapshot` của bản đó.

### Bước 2 — B1: gom biến

FB (`get_live_context`, scope `AL Bom Set`) phủ các biến `OFFSET_*` và `NC_*` qua FVB đã seed.
1.3 chỉ còn fill biến chưa seed. 1.7 chuẩn hoá: `8 → 0.08`, `12 → 0.12`, `16 → 0.16`,
`3 → 0.03`, `10 → 0.10`.

### Bước 3 — B2: tra giá & master data

Giá tra theo composite key (`aluminum_color=WHITE`, `aluminum_origin=IMPORT`, `aluminum_thickness=20`,
`aluminum_surface=POWDER_COATED`) — ví dụ này rơi vào dòng giá **phẳng**:

| Mã | Giá (`unit_price`) |
|---|---|
| `XF55-KB-20` (khung bao) | `113.000` |
| `XF55-CANH-20` (cánh) | `113.000` |
| `KINH-LOWE-24` (kính) | `1.150.000` |
| `GIO-EPDM-55` (gioăng) | `1.250` |
| `VIT-TK-35X16` (vít) | `850` |
| `KL-MZS20` (tay nắm) | `210.000` |
| `KL-KHOA-01` (khoá) | `350.000` |
| `KL-T-MJ06` (bản lề) | `180.000` |

**Rule chọn mã động** (batch #5): `glass_thick = 24` → `RULE-NEP-GLASSTHICK` → tier `16.01–999` →
`C3211-20`; `glass_type = LOWE` → `RULE-KEO-GLASSTYPE` → `KEO-TT-01` (`45.000`).

### Bước 4 — B3/B4: tính dòng vật tư

| slug | item_code | width (mm) | unit_qty | qty | total_qty | unit_price | line_total | bucket |
|---|---|---|---|---|---|---|---|---|
| khung_ngang_tren | XF55-KB-20 | `2400` | 3.017 | 1 | 3.017 | 113.000 | 340.898 | VL_NHOM |
| khung_ngang_duoi | XF55-KB-20 | `2400` | 3.017 | 1 | 3.017 | 113.000 | 340.898 | VL_NHOM |
| khung_dung | XF55-KB-20 | `2600` | 3.268 | 2 | 6.536 | 113.000 | 738.613 | VL_NHOM |
| do_ngang | XF55-KB-20 | `2400 − 2×48 = 2304` | 2.896 | 1 | 2.896 | 113.000 | 327.262 | VL_NHOM |
| canh_ngang | XF55-CANH-20 | `2400/2 − 48 = 1152` | 1.555 | 4 | 6.221 | 113.000 | 702.950 | VL_NHOM |
| canh_dung | XF55-CANH-20 | `(2600−600) − 48 = 1952` | 2.635 | 4 | 10.541 | 113.000 | 1.191.110 | VL_NHOM |
| kinh_tren | KINH-LOWE-24 | `2400 − 2×50 = 2300` | 1.265 | 1 | 1.265 | 1.150.000 | 1.454.750 | VL_KINH |
| kinh_duoi | KINH-LOWE-24 | `2400/2 − 90 = 1110` | 2.120 | 2 | 4.240 | 1.150.000 | 4.876.230 | VL_KINH |
| nep_kinh_tren | C3211-20 *(Rule)* | `2×(2300+550) = 5700` | 1.778 | 2 | 3.557 | 113.000 | 401.918 | VL_NHOM |
| nep_kinh_duoi | C3211-20 *(Rule)* | `2×(1110+1910) = 6040` | 1.884 | 4 | 7.538 | 113.000 | 851.785 | VL_NHOM |
| keo_tren | KEO-TT-01 *(Rule)* | `5700` | 5.700 | 1 | 5.700 | 45.000 | 256.500 | VL_VTP |
| keo_duoi | KEO-TT-01 *(Rule)* | `6040` | 6.040 | 2 | 12.080 | 45.000 | 543.600 | VL_VTP |
| gioang | GIO-EPDM-55 | `2400+2400+2×2600 = 10000` | 10.000 | 1 | 10.000 | 1.250 | 12.500 | VL_VTP |
| vit | VIT-TK-35X16 | — | 1.000 | 28 | 28.000 | 850 | 23.800 | VL_VTP |
| tay_nam | KL-MZS20 | — | 1.000 | 1 | 1.000 | 210.000 | 210.000 | VL_PK |
| khoa | KL-KHOA-01 | — | 1.000 | 1 | 1.000 | 350.000 | 350.000 | VL_PK |
| ban_le | KL-T-MJ06 | — | 1.000 | **8** | 8.000 | 180.000 | 1.440.000 | VL_PK |

> **Đọc bảng này thế nào** — lấy dòng `do_ngang` làm mẫu:
> 1. `width` = công thức khai trên `AL Bom Item` → `W_mm - 2*OFFSET_FRAME` = `2400 − 96` = **2304 mm**
> 2. `unit_qty` = `lookup_calc_pattern("LENGTH_TO_WEIGHT", 2304, 0, weight_per_unit, {...})` = **2.896**
> 3. `total_qty` = `unit_qty × qty` = `2.896 × 1` = **2.896**
> 4. `line_total` = `total_qty × unit_price` = `2.896 × 113.000` = **327.262**
>
> `ban_le`: `lookup_rule('RULE-BANLE-QTY', 2600)` → tier `2101–2700` = `4`/cánh `× 2` cánh = **8**.

### Bước 5 — B5: gom cost bucket

| Bucket | Σ line_total | Gồm |
|---|---|---|
| `VL_NHOM` | **4.895.437** | khung + đố + cánh + nẹp |
| `VL_KINH` | **6.330.980** | 2 tấm kính |
| `VL_VTP` | **836.400** | keo + gioăng + vít |
| `VL_PK` | **2.000.000** | tay nắm + khoá + bản lề |
| **`TONG_VL`** | **14.062.817** | tổng 4 bucket |

### Bước 6 — B6: Cost Template `CT-01-STANDARD`

| Dòng (`line_code`) | Công thức thật | Thay số | Kết quả |
|---|---|---|---|
| `TONG_M2` | `(W_mm/1000)*(H_mm/1000)` | `2.4 × 2.6` | **6.240 m²** |
| `NC_SX` | `NC_SX_PCT * TONG_VL` | `0.08 × 14.062.817` | 1.125.025 |
| `NC_LD` | `NC_LD_PCT * TONG_VL * lookup_rule('RULE-HEIGHT-MULT', installation_height_m)` | `0.12 × 14.062.817 × 1.0` | 1.687.538 |
| `TONG_NC` | `NC_SX + NC_LD` | | **2.812.563** |
| `OH_VC` | `OH_VC_PCT * TONG_VL` | `0.03 × 14.062.817` | 421.884 |
| `OH_QLY` | `OH_QLY_PCT * (TONG_VL + TONG_NC)` | `0.03 × 16.875.380` | 506.261 |
| `TONG_OH` | `OH_VC + OH_QLY` | | **928.146** |
| `GIA_THANH` | `TONG_VL + TONG_NC + TONG_OH` | | **17.803.526** |
| `PROFIT` | `PROFIT_MARGIN * GIA_THANH` | `0.16 × 17.803.526` | 2.848.564 |
| `GIA_BAN` | `GIA_THANH + PROFIT` | | **20.652.090** |
| `DON_GIA_M2` | `GIA_BAN / TONG_M2` | `20.652.090 / 6.24` | **3.309.630 VND/m²** |
| `VAT` | `VAT_RATE * GIA_BAN` | `0.10 × 20.652.090` | 2.065.209 |
| **`GIA_VAT`** | `GIA_BAN + VAT` | | **22.717.299** |

### Bước 7 — B7: ghi kết quả

| Nơi ghi | Giá trị |
|---|---|
| `Quotation Item.al_gia_vat` | `22.717.299` |
| `Quotation Item.al_gia_ban` | `20.652.090` |
| `Quotation Item.rate` | `20.652.090` |
| `Quotation Item.al_bom_result` | JSON đầy đủ |
| Quotation cha | 13 trường tổng tiền |

### Đối chiếu golden — vì sao lệch +10 VND

| Bước | Golden ghi (làm tròn từng bước) | Máy tính (float liên tục) |
|---|---|---|
| `do_ngang` | `2.8961 × 113.000 = 327.259` | `2.896128 × 113.000 = 327.262` (**+3**) |
| `VL_NHOM` | 4.895.431 | 4.895.437 (+6) |
| `TONG_VL` | 14.062.811 | 14.062.817 (+6) |
| `GIA_THANH` | 17.803.518 | 17.803.526 (+8) |
| `GIA_BAN` | 20.652.081 | 20.652.090 (+9) |
| **`GIA_VAT`** | **22.717.289** | **22.717.299 (+10)** |

Không phải lỗi logic — là **độ chính xác số thực tích luỹ** qua các phép nhân. `run_test.py`
chấp nhận `delta < 1.000` ⇒ PASS. Muốn khớp tuyệt đối phải làm tròn ở **từng dòng**, nhưng việc
đó sẽ đổi giá trị golden hiện tại.

⚠️ **Đọc bucket, ⛔ đừng đọc tổng các dòng hiển thị:** `lines[].line_total` hiển thị đã làm tròn
tới VND, còn bucket là tổng **full-precision** ⇒ cộng tay các dòng có thể lệch vài VND. **Số chính
thức là bucket / cost template.**

---

## §8. Ví dụ 2 — CDMQ-4C, tính từng bước

> Nguồn: `alumglass/run_test.py:85-159` (`test_cdmq_4c`). Golden `47.430.808`, **assert cứng**
> (`delta < 1.000`, nếu lệch ⇒ `AssertionError`). ⚠️ Chưa chạy lại trên máy soạn tài liệu.

Đây là ca demo **toàn bộ tính năng**: 22 dòng BOM + phụ kiện, dynamic rule 2 loại, `lookup_rule`
2 chỗ, tham chiếu chéo dòng, và cost template có hệ số theo tầng.

### Bước 0 — Đầu vào

| | |
|---|---|
| Người dùng nhập | `W_mm = 3600`, `H_mm = 3200`, `n_panel = 4`, `TransomHeightTop = 600`, `TransomHeightBottom = 400`, `SideLiteWidth = 800`, `SideLiteHeight = 2800`, `aluminum_color = DARK`, `aluminum_origin = IMPORT`, `aluminum_thickness = 20`, `aluminum_surface = POWDER_COATED`, `installation_height_m = 15` |
| Hệ thống | như 2C (`OFFSET` 48/90/50/48 · `NC` 8%/12% · `PROFIT` 16%) |

### Bước 1–3 — B0/B1/B2

Giống 2C. Điểm khác: `installation_height_m = 15` ⇒ ở B6,
`lookup_rule('RULE-HEIGHT-MULT', 15) = 1.2` — **nhân công lắp đặt tăng 20%**.

### Bước 4 — B3/B4: dòng vật tư (rút gọn)

| slug | item_code | width (mm) | unit_qty | qty | total_qty | line_total | bucket |
|---|---|---|---|---|---|---|---|
| khung_ngang_tren | XF55-KB-20 | `3600` | 4.525 | 1 | 4.525 | 511.348 | VL_NHOM |
| khung_ngang_duoi | XF55-KB-20 | `3600` | 4.525 | 1 | 4.525 | 511.348 | VL_NHOM |
| khung_dung_trai / _phai | XF55-KB-20 | `3200` | 4.022 | 2 | 8.045 | 909.062 ×2 | VL_NHOM |
| do_ngang_tren / _duoi | XF55-KB-20 | `3600 − 96 = 3504` | 4.405 | 1 | 4.405 | 497.712 ×2 | VL_NHOM |
| canh_dung_c1…c4 | XF55-CANH-20 | `(3200−600−400) − 48 = 2152` | 2.905 | 2 | 5.810 | 656.575 ×4 | VL_NHOM |
| canh_ngang_c1…c4 | XF55-CANH-20 | `3600/4 − 48 = 852` | 1.150 | 2 | 2.300 | 259.945 ×4 | VL_NHOM |
| kinh_fixed_top | KINH-LOWE-24 | `3600 − 100 = 3500` | 1.925 | 1 | 1.925 | 2.213.750 | VL_KINH |
| kinh_fixed_bottom | KINH-LOWE-24 | `3500` | 1.225 | 1 | 1.225 | 1.408.750 | VL_KINH |
| kinh_canh | KINH-LOWE-24 | `3600/4 − 90 = 810` | 1.709 | 4 | 6.836 | 7.861.860 | VL_KINH |
| kinh_sidelite | KINH-LOWE-24 | `800 − 100 = 700` | 1.890 | 1 | 1.890 | 2.173.500 | VL_KINH |
| nep_kinh_canh | C3211-20 | `2×(810+2110) = 5840` | 1.822 | 8 | 14.577 | 1.647.160 | VL_NHOM |
| nep_kinh_sidelite | C3211-20 | `2×(700+2700) = 6800` | 2.122 | 2 | 4.243 | 479.482 | VL_NHOM |
| keo_canh | KEO-TT-01 | `5840` | 5.840 | 4 | 23.360 | 1.051.200 | VL_VTP |
| keo_sidelite | KEO-TT-01 | `6800` | 6.800 | 1 | 6.800 | 306.000 | VL_VTP |
| gioang | GIO-EPDM-55 | `3600+3600+2×3200 = 13600` | 13.600 | 1 | 13.600 | 17.000 | VL_VTP |
| vit | VIT-TK-35X16 | — | 1.000 | 80 | 80.000 | 68.000 | VL_VTP |
| tay_nam | KL-MZS20 | — | 1.000 | 4 | 4.000 | 840.000 | VL_PK |
| khoa | KL-KHOA-01 | — | 1.000 | 1 | 1.000 | 350.000 | VL_PK |
| ban_le | KL-T-MJ06 | — | 1.000 | **16** | 16.000 | 2.880.000 | VL_PK |

> `ban_le`: `lookup_rule('RULE-BANLE-QTY', 3200)` → tier `2701+` = `4`/cánh `× 4` cánh = **16**.
> `kinh_sidelite`: vách kính bên = `SideLiteWidth − 2×OFFSET_FIXED` = `800 − 100` = **700 mm**.

### Bước 5 — B5: bucket

| Bucket | Σ |
|---|---|
| `VL_NHOM` | **9.628.967** |
| `VL_KINH` | **13.657.860** |
| `VL_VTP` | **1.442.200** |
| `VL_PK` | **4.070.000** |
| **`TONG_VL`** | **28.799.027** |

### Bước 6 — B6: cost template (có hệ số tầng)

| Dòng | Công thức | Kết quả |
|---|---|---|
| `TONG_M2` | `(3600/1000)*(3200/1000)` | **11.520 m²** |
| `NC_SX` | `0.08 × 28.799.027` | 2.303.922 |
| `NC_LD` | `0.12 × 28.799.027 × lookup_rule('RULE-HEIGHT-MULT', 15)` | **4.147.060** (×1.2 ★) |
| `TONG_NC` | | **6.450.982** |
| `OH_VC` | `0.03 × TONG_VL` | 863.971 |
| `OH_QLY` | `0.03 × (TONG_VL + TONG_NC)` | 1.057.500 |
| `TONG_OH` | | **1.921.471** |
| `GIA_THANH` | | **37.171.480** |
| `PROFIT` | `0.16 × GIA_THANH` | 5.947.437 |
| `GIA_BAN` | | **43.118.917** |
| `DON_GIA_M2` | `GIA_BAN / TONG_M2` | **3.742.962 VND/m²** |
| `VAT` | `0.10 × GIA_BAN` | 4.311.892 |
| **`GIA_VAT`** | | **47.430.808** ✅ delta 0 |

### Bốn điểm đáng chú ý của 4C

1. **Dynamic Item Rule 2 kiểu** — nẹp dùng `THRESHOLD` (theo `glass_thick = 24` → `C3211-20`),
   keo dùng `LOOKUP` (theo `glass_type = LOWE` → `KEO-TT-01`).
2. **Màu DARK ⛔ không được nhân 1.08 trong ví dụ này.** Cần phân biệt 2 cơ chế:
   - `exact_match` (đang seed): màu chỉ **chọn dòng giá**. Nhưng dữ liệu giá seed **không gắn
     dimension nào** (`seed_demo_data.py:288-289`), nên `best_partial_match` rơi về dòng "trần" ⇒
     DARK và WHITE **cùng ra `113.000` / `1.150.000`**.
   - `multiplier_chain`: mới thật sự nhân `AL Color Standard.price_multiplier` — DARK `×1.08`.
     Bật chế độ này phải **sửa code** (`install_fb_bindings.py:45`), ⛔ không sửa qua UI, và **sẽ
     làm số `47.430.808` ở bảng trên sai đi** (mọi dòng nhôm `×1.08`).

   Chi tiết đầy đủ + 2 giới hạn của `multiplier_chain`: xem **§5 B2 — Hệ số màu `price_multiplier`**.
3. **`lookup_rule` xuất hiện 2 chỗ** — `NC_LD` (hệ số tầng) và `ban_le` (số bản lề theo chiều cao).
4. **Tham chiếu chéo dòng** — `gioang` = `khung_ngang_tren__width + khung_ngang_duoi__width +
   2×khung_dung_trai__width`; nẹp/keo tham chiếu `kinh_*.width/height`. Đây chính là chỗ
   `_normalize_items_ref()` biến `items.kinh_canh.width` → `kinh_canh__width`.

---

## §9. Checklist cấu hình để một sản phẩm tính được giá

Làm theo đúng thứ tự — thiếu bước sau thì bước trước vô nghĩa.

| # | Việc | DocType | Kiểm gì |
|---|---|---|---|
| 1 | Khai **biến** | `AL Variable Library` | `var_name`, `is_system`, `source_doctype` + `source_field` (nếu hệ thống), `default_value` |
| 2 | Khai **hồ sơ nhôm** | `AL Profile System` (+ child `system_variables`) | `offset_frame/glass/fixed/do_ngang` |
| 3 | Khai **loại sản phẩm** | `AL Product Type` | `nc_sx_pct`, `nc_ld_pct`, `profit_margin` |
| 4 | Khai **chiều giá** | `AL Pricing Dimension` + `AL Variable Dimension Mapping` | Dimension nào, field `custom_pd_*` nào trên `Item Price` |
| 5 | Khai **nhóm vật tư** | `AL Material Category` | `default_scrap_pct`, `has_weight`, `requires_glass_master`, `default_calc_pattern` |
| 6 | Khai **kính** | `AL Glass Master` | `total_thick_mm`, `glass_type`, `max_area_m2` |
| 7 | Khai **cách tính số lượng** | `AL Quantity Calc Method` | `calc_fn` (lambda) hoặc dùng pattern có sẵn |
| 8 | Khai **rule tra bảng** | `AL Calculation Rule` | `rule_type` (CONSTANT / THRESHOLD / LOOKUP) + dòng con |
| 9 | Khai **rule chọn mã** | `AL Dynamic Item Rule` | điều kiện + dòng threshold/lookup |
| 10 | Khai **nhóm chi phí** | `AL Cost Bucket` | `bucket_code` — phải khớp `cost_bucket` của mọi dòng BOM |
| 11 | Khai **công thức giá thành** | `AL Cost Template` + Item | **thứ tự dòng đúng**, cờ `is_final_price` / `is_pre_vat_price` |
| 12 | Khai **bộ phụ kiện** | `AL Accessory Set` + Item | `qty_formula`, `unit_price`, `calc_pattern`, `cost_bucket` |
| 13 | Khai **sản phẩm BOM** | `AL Bom Set` + `AL Bom Item` | mỗi dòng đủ `slug`, `category`, `calc_pattern`, `cost_bucket`, công thức `width/height/qty`; `apply_scrap_pct` nếu muốn hao hụt |
| 14 | Khai **giá** | `Item Price` | mỗi item phải khớp **ít nhất 1 dòng** theo composite key (hoặc 1 dòng không gắn dimension làm phương án dự phòng) |
| 15 | Nối BOM | `AL BOM` | `bom_set` trỏ đúng Bom Set, có `current_version` |
| 16 | **Tạo & xuất bản phiên bản** | `AL BOM Version` | ⚠️ **bắt buộc** — B0 sẽ `throw` nếu BOM chưa có phiên bản nào |
| 17 | Gán vào báo giá | `Quotation Item` | `al_bom` (+ `al_bom_version` nếu muốn ghim bản cụ thể) |

**Nguyên tắc bao trùm:** muốn thêm sản phẩm/ngành mới ⇒ ⛔ **0 dòng code**, chỉ thêm dữ liệu.

---

## §10. Xử lý sự cố

| Triệu chứng / thông báo | Nguyên nhân | Cách sửa |
|---|---|---|
| `BOM '…' chưa có phiên bản nào nên chưa tính giá được` | B0: BOM chưa có `AL BOM Version` nào | Mở BOM → **"Tạo BOM Version mới"** → duyệt → **Xuất bản** → tính lại |
| `BOM Version không có snapshot` | `bom_set_snapshot` rỗng | Tạo/xuất bản lại phiên bản |
| `Không tìm được Item Price khớp cho '…' với composite key hiện tại` | Không có dòng `Item Price` nào khớp màu/xuất xứ/độ dày/bề mặt, hoặc dòng giá đã hết hiệu lực / sai tiền tệ | Thêm dòng `Item Price` khớp, **hoặc** thêm 1 dòng giá **không gắn dimension** làm phương án dự phòng |
| Cảnh báo `thieu_gia_item:<code>` | Nhánh FB `allow_missing=True` trả giá 0 | Như trên — dòng đó đang được tính **giá 0** |
| `Công thức chia cho 0 — kiểm tra lại kích thước/số lượng đầu vào (W, H, số cánh…)` | `FormulaZeroDivisionError` | Xem lại công thức dòng / biến `W_mm`, `H_mm`, `n_panel` — thường do `TONG_M2 = 0` |
| `Tính giá thất bại, vui lòng thử lại hoặc báo quản trị.` | Lỗi khác (chi tiết nằm ở **Error Log**) | Mở Error Log tìm bản ghi `AlumGlass:` |
| Cảnh báo `[ENGINE.UNKNOWN_FUNCTION]` | Cost Template gọi hàm engine chưa tiêm | Chỉ dùng `lookup_rule`, `lookup_calc_pattern`, `roundup` |
| Cảnh báo `lookup_rule_thieu_ma:<code>` | Công thức viết sai mã `AL Calculation Rule` | Sửa mã trong công thức hoặc tạo rule |
| Cảnh báo `<slug>__max_area_exceeded` | Diện tích kính > `AL Glass Master.max_area_m2` | Chia khung / ghép kính / đổi kính — hoặc **cố ý chấp nhận** (chỉ cảnh báo, ⛔ không chặn) |
| Cảnh báo `phan_tram_mo_ho_bang_1__warn:<key>` | Biến % = đúng `1` (1% hay 100%?) | Sửa giá trị về `1`(=1%) hoặc `100`(=100%) cho rõ |
| Cảnh báo `bucket_source_type_chua_ho_tro:<code>` | Cost Bucket khai `source_type` lạ | Đổi về `aggregate_from_items` hoặc để trống |
| `Báo giá '…' đã gửi khách nên không tính lại giá được` | `Quotation.docstatus = 1` | Huỷ báo giá rồi **Amend**, hoặc tạo báo giá mới |
| `Bạn không có quyền truy cập báo giá này` | Thiếu quyền `read` trên Quotation cha | Cấp quyền / dùng đúng tài khoản |
| `Gỡ Pricing Rule / giảm giá trên dòng rồi tính lại…` | ERPNext tính lại `rate` khác giá hệ thống | Gỡ Pricing Rule hoặc giảm giá trên dòng |
| Kết quả cũ vẫn hiện | Cache `Formula Global Variable` (Redis, TTL 60s) | Chờ ≤60s. ⚠️ Ghi bằng `frappe.db.set_value` ⛔ không xoá cache — TTL là lưới an toàn |
| Dòng báo giá kẹt `Queued` mãi | Job nền ⛔ không chạy/⛔ chết (queue `long`, worker, Redis) | Kiểm worker queue `long`; xem Error Log; chạy lại |
| Sửa `AL Quantity Calc Method.calc_fn` nhưng kết quả không đổi | Cache hàm tính | `on_update`/`on_trash` đã tự xoá cache — kiểm lại đã lưu chưa |
| Giá khác với bản đã chốt cho khách | Đang đọc **cấu hình sống** thay vì snapshot | Kiểm `_cost_template` / `_profile_system` trong `al_bom_vars` — các override này đọc doc sống |

---

## §11. Hành vi hiện tại cần biết

> Danh sách dưới đây **cập nhật theo mã tại `main`/`ad79edb`**, ⛔ không chép lại các bản review cũ.
> Nhiều mục trong tài liệu cũ (`fb4f73f`) **đã được vá** — chênh lệch được ghi rõ.

### 11.1 Những điều đã thay đổi so với tài liệu cũ

| Mục cũ | Tài liệu cũ nói | **Thực tế tại `main`/`ad79edb`** |
|---|---|---|
| Tạo phiên bản | "Tính giá tự tạo & xuất bản BOM Version" | ⛔ **Không**. B0 `throw` yêu cầu người dùng tự tạo/xuất bản (`:311-316`) |
| `rate` | "chỉ trình duyệt ghi" | ✅ **Máy chủ ghi luôn** `rate = giá trước VAT` (`:2578`) + tính lại tổng tiền cha |
| Cache `calc_fn` | "không bao giờ được xoá" | ✅ `AL Quantity Calc Method.on_update`/`on_trash` → `clear_calc_fn_cache()` |
| `roundup(x, y)` | "bỏ qua `y`" | ✅ Ngữ nghĩa **Excel ROUNDUP** đầy đủ (`:97-111`) |
| Tra `Item Price` | "không lọc hiệu lực/tiền tệ" | ✅ Có lọc `valid_from`/`valid_upto` + `currency` |
| Batch #6 | "ghi đè giá composite, trộn 2 bảng giá" | ✅ Dùng chung `price_list` đang hoạt động (`_active_price_list()` `:1395`) |
| Lỗi hiển thị UI | "phơi stack trace" | ✅ `_bom_error_message()` `:110` đổi lỗi thành **một câu tiếng Việt**, stack chỉ vào `log_error` |
| Quyền API | "không kiểm quyền" | ✅ `_require_quotation_item_permission` (`read` trên Quotation cha) |
| `ConfigSnapshot` | "B7 tạo mỗi lần tính" | ⛔ **Không** — chỉ tạo khi **submit** Quotation |

### 11.2 Hành vi đang sống, cần biết trước khi kết luận "hệ thống sai"

1. **Một dòng lỗi ⛔ không giết cả BOM.** `on_error="default"`, `default_value=0` — dòng lỗi nhận
   giá 0 và **cảnh báo nằm trong `al_bom_result["errors"]`**. Nhìn màn hình không thấy gì bất
   thường ⇒ phải mở `errors` ra đọc. **Ngoại lệ:** chia cho 0 vẫn **chết cả BOM**.
2. **Giá 0 có thể là "không tìm thấy giá", ⛔ không phải "miễn phí".** Luôn đối chiếu túi
   `errors.bom_items`.
3. **Số chính thức là bucket / cost template, ⛔ không phải tổng các dòng hiển thị.** Dòng hiển thị
   đã làm tròn; bucket là full-precision.
4. **`DON_GIA_M2 = GIA_BAN / TONG_M2` ⛔ không có `safe_div`.** `W_mm` hoặc `H_mm` = 0 ⇒
   `TONG_M2 = 0` ⇒ `FormulaZeroDivisionError` chặn cả BOM (cố ý).
5. **Thứ tự dòng trong `AL Cost Template` là thứ tự tính.** Đặt sai thứ tự ⇒ giá trị sai **im lặng**.
6. **Cờ `is_final_price` / `is_pre_vat_price` quyết định dòng nào là giá bán.** ⛔ Đừng đổi tên
   `line_code` và trông chờ engine nhận ra — engine đọc **cờ**; không có cờ mới fallback về tên
   `GIA_VAT`/`GIA_BAN`.
7. **Hao hụt vật tư là OPT-IN.** `AL Bom Set.apply_scrap_pct` phải bật, khi đó
   `total_qty ×= (1 + scrap_pct/100)` với `scrap_pct` lấy từ `AL Material Category.default_scrap_pct`.
   Tắt ⇒ hệ số = 1 ⇒ ⛔ kết quả không đổi (an toàn với category chưa cấu hình).
8. **Hệ số màu chỉ chạy ở chế độ `multiplier_chain`, mà chế độ này ⛔ không đổi được qua UI.**
   Binding đang seed là `exact_match`; `install_composite_pricing_binding()` **ghi đè lại
   `source_config` mỗi lần migrate** nên sửa trên form sẽ bị revert im lặng. Muốn bật phải sửa
   `setup/install_fb_bindings.py:45` và **chạy lại golden** (số sẽ đổi). Xem §5 B2.
   *Ngay cả khi bật, **màu theo vị trí** vẫn ⛔ không tham gia nhân hệ số — chỉ `aluminum_color`
   toàn cục có tác dụng.*
9. **Giá trị 1 trong biến phần trăm là nhập nhằng** ⇒ hệ thống **cảnh báo** chứ ⛔ không đoán.
10. **`_cost_template` / `_profile_system` / `_accessory_set` đọc doc SỐNG**, ⛔ không đọc snapshot
    — chúng là override có chủ đích của người dùng, nên tính bất biến của BOM Version ⛔ không bảo
    vệ được các đường này.
11. **BOM Version là bất biến ⛔ chỉ một phần.** Snapshot chụp `bom_set_snapshot`,
    `cost_template_snapshot`, `pricing_dimension_snapshot` — nhưng `al_bom_vars` (đầu vào người
    dùng) lưu **thô**, ⛔ không lưu giá trị đã resolve.
12. **Async: ngưỡng 150 dòng.** Vượt ngưỡng ⇒ job nền queue `long`, timeout 600s, client nhận kết
    quả qua realtime `alumglass_bom_calc_done`. Đóng dialog rồi mở lại → trạng thái đọc từ
    `al_calc_status`.
13. **B1 chạy `_normalize_percent_inputs()` SAU CÙNG** — nên mọi nguồn (FB, legacy, user, default)
    đều được chuẩn hoá, ⛔ không có đường lọt.
14. **`roundup(x, 0)` giữ nguyên hành vi `math.ceil`** — cấu hình hiện có dùng
    `roundup(H_mm/700, 0)` vẫn chạy như cũ.
15. **3 hàm được phép trong công thức:** `lookup_calc_pattern`, `lookup_rule`, `roundup`. Gọi hàm
    khác ⇒ `[ENGINE.UNKNOWN_FUNCTION]`.

---

## §12. Phụ lục

### 12.1 Bảng tra nhanh — bước nào ghi/đọc cái gì

| Bước | Đọc | Ghi vào bộ nhớ | Ghi DB |
|---|---|---|---|
| B0 | `Quotation Item`, `AL BOM`, `AL BOM Version` | `bom_version`, `bom_code` | — |
| B1 | `al_bom_vars`, `Formula Global Variable`, `Formula Variable Binding`, `AL Variable Library`, `AL Profile System` | `self.inputs` | — |
| B2 | `bom_set_snapshot`, `AL Bom Set`, `AL Accessory Set`, `Item`, `Item Price`, `AL Glass Master`, `AL Material Category`, `AL Dynamic Item Rule` | `bom_items`, `row_literals`, `_glass_data` | — |
| B3 | `bom_items` + `row_literals` | `bom_formulas`, `inputs["items"]` | — |
| B4 | `bom_formulas` + `inputs` | `bom_result`, `bom_engine_errors` | — |
| B5 | `bom_result`, `AL Cost Bucket` | `buckets` | — |
| B6 | `cost_template_snapshot` (+ `_cost_template`), `inputs`, `buckets` | `cost_result`, `gia_vat`, `cost_template_trace` | — |
| B7 | — | — | `Quotation Item` (4 field) + `Quotation` (13 field), **1 commit** |

### 12.2 Chạy golden case

```bash
# Toàn bộ (2C + 4C) — 4C assert cứng, lệch là raise
bench --site <site> execute alumglass.run_test.main

# Đơn lẻ
bench --site <site> execute alumglass.run_test.test_cdmq_2c
bench --site <site> execute alumglass.run_test.test_cdmq_4c

# Bộ test của app
bench --site <site> run-tests --app alumglass
```

⚠️ **Điều kiện tiên quyết:** site phải có `alumglass` **và** `formula_builder`, đã `bench migrate`
(chạy các patch seed FVB + `install_fb_bindings`), và đã seed dữ liệu demo
(`from alumglass.setup.seed_demo_data import seed_all; seed_all()`).

⚠️ **`run_test.py` ghi dữ liệu thật** vào site: nó `INSERT` thẳng `Quotation` + `Quotation Item`
(`run_test.py:18-29`). ⛔ **Không chạy trên production.**

### 12.3 Tài liệu liên quan

| Tài liệu | Nội dung |
|---|---|
| `docs/quotation-pricing-flow.md` | Bản full-flow trước — vẫn đúng phần lớn, nhưng một số mục đã cũ (xem §11.1) |
| `docs/design/fvb-guide-alumglass-pricing.md` | Formula Variable Binding a–z + ứng dụng vào tính giá |
| `docs/design/quotation-pricing.md` | Thiết kế luồng tính giá theo từng phase B1–B6 + v28_11 |
| `docs/design/p1-pricing-dimension-versioning.md` | Snapshot `AL Pricing Dimension` |
| `docs/design/p2-async-bom-calculation.md` | Tính BOM lớn trong nền |
| `docs/design/p3-quotation-pricing-patch-3-full.md` | Ghi nhận lần merge gói vá V6 P10 |
| `docs/usage/quotation-pricing.vi.md` | Hướng dẫn dùng cho người dùng cuối |
| `docs/usage/bom-calculation-dialog.vi.md` | Chi tiết dialog "Tham số BOM" |
| `docs/design/fvb-seed.md` | Các bản seed FVB |
| `TONG_QUAN_KIEN_TRUC.md` | Kiến trúc toàn app |
| `formula_builder/docs/design/fvb-single-resolution-layer.md` | ADR nền của lớp resolve |

### 12.4 Mã nguồn cốt lõi

| Tệp | Dòng | Vai trò |
|---|---|---|
| `alumglass/engine/bom_orchestrator.py` | 2.696 | **Trái tim** — B0→B7 + mọi helper |
| `alumglass/engine/composite_pricing.py` | 272 | `best_partial_match`, lọc dòng giá, túi cảnh báo |
| `alumglass/api/__init__.py` | 1.406 | Endpoint + async + chuẩn hoá lỗi |
| `alumglass/formula_handlers.py` | 365 | `PATTERN_FORMULAS`, `lookup_calc_pattern`, cache |
| `alumglass/fb_handlers.py` | 308 | Đăng ký `aluminum_price_composite`, `glass_master_data` |
| `alumglass/al_bom_engine/glass_group_resolver.py` | 53 | Nhóm kính theo vị trí |
| `alumglass/al_bom_engine/color_group_resolver.py` | 24 | Nhóm màu theo vị trí |
| `alumglass/al_bom_engine/system_variable_resolver.py` | 128 | Resolve biến hệ thống (dùng chung với autocomplete) |
| `alumglass/al_bom_engine/fb_config.py` | 52 | Hằng số có tên qua FVB |
| `alumglass/setup/install_fb_bindings.py` | — | Seed binding giá composite mỗi lần migrate |
| `alumglass/run_test.py` | 164 | Golden case 2C + 4C |
