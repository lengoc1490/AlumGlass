# D3 — Seed Formula Variable Binding (FVB) từ AL Variable Library

> **Trạng thái:** Implemented (D3 v28_9) + **D6 mở rộng full v28_11** · 2026-09-03
> **Job:** `2026-08-16_alumglass-sprint1-quotation` (D3) · `2026-09-03_alumglass-patch3-merge-fb-platform-ph0-1` (D6, Phase 2)
> **Patch:** `alumglass.patches.v28_9.seed_fvb_from_variable_library` (D3) · `alumglass.patches.v28_11.seed_fvb_full_from_variable_library` (D6)

## Vấn đề

Engine đã có sẵn luồng FB-max (B1.4 `_resolve_fb_context` → `get_live_context`):
khi `Formula Variable Binding` (FVB) được seed, FB resolve global binding + system
variable một cách data-driven. Nhưng chưa có FVB nào → `_get_pricing_bindings()`
trả `[]` → luồng FB chưa active, luôn chạy fallback cũ (Variable Library).

D3 seed FVB để bật FB-max **mà không đụng core calculation**: engine vẫn giữ
merge order B1 (1.3 Variable Library → 1.4 FB override), Variable Library là
fallback backward-compat.

## Mapping decision

### Group 1 — Global constant (is_global=1, applies_to_doctype="")

Từ **Formula Global Variable** (`is_active=1`, `value_source="CONSTANT"`,
`var_type` số) — demo hiện có: `VAT_RATE=0.10`, `OH_VC_PCT=0.03`, `OH_QLY_PCT=0.03`.

| FVB field | Giá trị |
| --- | --- |
| `variable_name` | `gv.var_name` |
| `source_type` | `constant` |
| `source_config` | `{"value": gv.constant_value}` |
| `data_type` | `gv.var_type` (Float/Int/Currency/Percent) |
| `default_value` | `gv.constant_value` (bằng value resolve được) |
| `is_global` | `1` |
| `applies_to_doctype` / `applies_to_field` | `""` |

→ resolve được ở **mọi scope**. Giá trị giống section 7 legacy (Formula Global
Variable) của `get_live_context` → không conflict.

### Group 2 — System variable (is_global=0, applies_to_doctype="AL Bom Set")

Từ **AL Variable Library** (`is_system=1`, có `source_doctype` + `source_field`):

| Variable Library | source_doctype | source_field | link_field trên AL Bom Set |
| --- | --- | --- | --- |
| `OFFSET_FRAME` | AL Profile System | `offset_frame` | `profile_system` |
| `OFFSET_GLASS` | AL Profile System | `offset_glass` | `profile_system` |
| `OFFSET_FIXED` | AL Profile System | `offset_fixed` | `profile_system` |
| `OFFSET_DO_NGANG` | AL Profile System | `offset_crossbar` | `profile_system` |
| `NC_SX_PCT` | AL Product Type | `nc_pct` | `product_type` |
| `NC_LD_PCT` | AL Product Type | `nc_ld_rate` | `product_type` |
| `PROFIT_MARGIN` | AL Product Type | `profit_margin` | `product_type` |

| FVB field | Giá trị |
| --- | --- |
| `source_type` | `linked_doctype_field` |
| `source_config` | `{"link_field": ..., "target_doctype": source_doctype, "target_field": source_field}` |
| `applies_to_doctype` | `"AL Bom Set"` |
| `data_type` | map `var_type` → FVB (`Float→Float`, `Int→Int`, `Currency→Currency`, `Check→Check`, `Data/Select/Link→Data`) |
| `default_value` | `sv.default_value` (giữ nguyên từ Variable Library) |
| `is_global` | `0` |

**Vì sao scope "AL Bom Set" mà không "Quotation Item"?**

Chuỗi doc trong báo giá: `Quotation Item` → `AL BOM` (al_bom) → `AL BOM Version`
(al_bom_version) → `AL BOM` (bom) → `AL Bom Set` (bom_set). Chỉ **AL Bom Set**
có link trực tiếp tới `AL Profile System` (`profile_system`) và `AL Product Type`
(`product_type`). Quotation Item **không** có link tới 2 doctype này (parent
Quotation đã **bỏ** `al_profile_system` — V6 P6; profile system là override
item-level trong `al_bom_vars._profile_system`).

Nếu scope "Quotation Item" → `linked_doctype_field` không resolve được (thiếu
link_field) → rơi về `default_value` → override giá trị thật → **BREAK GOLDEN**.

### Engine change đi kèm (cùng job D3)

`bom_orchestrator._resolve_fb_context()` đổi scope:

1. **Scope ưu tiên "AL Bom Set"** khi resolve được Bom Set (qua
   `self._get_bom_set()`); ngược lại giữ scope "Quotation Item" (hành vi cũ).
2. **Bỏ qua chuỗi rỗng** khi merge (`""` không vào `inputs`) — bảo vệ trường hợp
   FVB `linked_doctype_field` fail → `default_value=""` (OFFSET_*) không override
   giá trị thật từ 1.3.
3. **Coerce giá trị từ binding** (source ≠ `"field"`) về `float` nếu là số:
   `linked_doctype_field` trả Decimal/numeric-string từ DB → để nguyên sẽ
   TypeError khi arithmetic (vd `NC_SX_PCT * TONG_VL`). Doc field (source="field")
   giữ nguyên type gốc.

## Quyết định default_value (deviation ghi nhận)

Spec yêu cầu "default_value từ Variable Library" — patch **giữ nguyên** literal
này. An toàn nhờ 2 thay đổi engine trên:

- `OFFSET_*` có `default_value=""` → nếu binding fail, `""` bị skip → 1.3 giữ
  giá trị thật (vd `OFFSET_FRAME=48`).
- `NC_*`/`PROFIT_MARGIN` có `default_value="0.08"/"0.12"/"0.16"` → nếu binding
  fail (Bom Set thiếu product_type), cả 1.3 lẫn FVB đều fallback cùng default
  → không lệch. Nếu binding resolve OK (normal case) → giá trị thật, không phải
  default.

Trước khi có engine change, để nguyên default sẽ BREAK golden (vd `""` override
`OFFSET_FRAME=48`, `"0.08"` string override `NC_SX_PCT`). Devation này là bắt
buộc để đúng ý đồ spec (default_value từ Variable Library) mà không phá số.

## Backward-compat

- System variable **không** có FVB (vd `source_doctype` ngoài 2 doctype trên,
  hoặc không có source_field) → patch **skip**, engine 1.3
  `_resolve_system_variables` vẫn resolve như cũ.
- FVB chưa chạy patch / chưa seed → `get_live_context` trả ít/không binding →
  engine 1.4 trả `{}` → giữ resolver cũ 1.3.
- Golden **CDMQ-2C = 22,717,289** / **CDMQ-4C = 47,430,808** không đổi: FVB
  resolve ra cùng giá trị thật với 1.3 (cùng source doctype + field), sau khi
  coerce về float → merge B1 cho `inputs` giống hệt trước D3.

## Idempotency

Patch check tồn tại theo `(variable_name, applies_to_doctype, is_global)` trước
khi insert; wrap try/except từng record (record lỗi chỉ log, không abort cả
patch); `frappe.db.commit()` 1 lần cuối. Chạy lại nhiều lần → không nhân đôi.

---

# D6 — Mở rộng seed FULL (v28_11, Phase 2) — mọi System Variable mappable

D3 seed CỨNG 2 doctype link (`AL Profile System → profile_system`,
`AL Product Type → product_type`). D6 generalize **theo data**: seed MỌI System
Variable (`AL Variable Library.is_system=1` có `source_doctype`+`source_field`)
mà **AL Bom Set có field Link trỏ tới `source_doctype`** — link field dò bằng
ĐÚNG hàm engine dùng (`al_bom_engine/system_variable_resolver.py`:
`resolve_source_link_fields("AL Bom Set")`, refactor từ phần dò meta của
`resolve_source_record_names` — D6 thêm hàm public dùng chung).

## Quy tắc seed / fallback (semantics == engine 1.3)

| Trường hợp | Hành động | Lý do |
|---|---|---|
| AL Bom Set có link → source_doctype | Seed FVB `linked_doctype_field`, `applies_to_doctype="AL Bom Set"`, source_config `{link_field, target_doctype, target_field}`, data_type theo `var_type`, default_value từ Variable Library, resolve_priority 100 | Scope FB `_resolve_fb_context` = AL Bom Set → binding resolve từ ĐÚNG doc/nơi 1.3 legacy resolve → cùng nguồn ⇒ giá trị ĐẢM BẢO == 1.3 cũ. Thêm var mới sau này = chỉ cần thêm link trên AL Bom Set. |
| AL Bom Set KHÔNG có link → source_doctype | **KHÔNG seed** — ghi vào fallback set (log + report) | FVB không resolve được nguồn từ scope engine ⇒ không đảm bảo semantics == 1.3. Engine giữ resolver 1.3 (guard `fill_missing_only`) cho các var này. |
| Đã có binding CÙNG `(variable_name, "AL Bom Set", global=0)` | Skip (không tạo duplicate) | Idempotent + không đè binding seed v28_9 / cấu hình tay. |
| Đã có binding KHÁC active cùng `variable_name` (vd `COMPOSITE_MATERIAL_PRICE`, global constant) | Skip (ghi `other-binding`) | 2 binding cùng tên chỉ gây mơ hồ thứ tự thắng trong get_live_context; FB đã resolve biến đó — seed thêm vô ích. |

**KHÔNG làm chain_link_lookup** — nếu source_doctype cần nối thêm chain từ AL
Bom Set (1.3 cũ không đi chain đó) → bỏ qua, để engine fallback.

## Interplay với flip B1 (Phase 3a, cùng v28_11)

B1 giờ chạy FB **trước** (1.4), rồi 1.3 `fill_missing_only=True` cho biến CHƯA
có. Hệ quả:

- Var **seed được** (có link) → FB resolve → 1.3 bỏ qua (đã có) → KHÔNG resolve
  2 lần. Value cuối = FB (giống 1.3 cũ vì cùng nguồn).
- Var **không seed được** (fallback set) → 1.3 resolve như trước D3/D6 → hành vi
  y hệt cũ. Đây chính là "safe fallback" mà spec yêu cầu giữ.
- Child-table override (`AL Profile System.system_variables`) không nằm trong
  FVB → 1.4b áp lại SAU FB + SAU 1.3 (capture trực tiếp từ child row) → thứ tự
  cuối không đổi: child table > FB > source_field > default > AL Calculation Rule.

## Idempotency

Giống D3 (check tồn tại + try/except từng record + commit 1 lần). Chạy lại
không nhân đôi; chạy sau v28_9 không tạo duplicate (check trùng lặp chặn).

## Golden

Không đổi (2C=22,717,289 / 4C=47,430,808): FVB mới resolve cùng giá trị với 1.3
(cùng source doctype + field + scope AL Bom Set). Vars fallback (không seed) →
không có binding → engine 1.3 giữ nguyên như trước. **KHÔNG verify site** trong
job này (constraint Owner) — patch chạy ở lần migrate kế tiếp; nếu var mới
không có link trên AL Bom Set → chúng sẽ nằm trong log "D6 FALLBACK".
