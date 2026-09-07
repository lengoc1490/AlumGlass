# Triển khai chi tiết — đã đối chiếu code thật (clone trực tiếp 07/09/2026)

> File này thay thế phần "Task 0.1" của kế hoạch trước — mình đã tự clone `Formula-Builder` (branch `develop`) và `AlumGlass`, đọc trực tiếp source, không dựa vào bản review AI cũ nữa. Mọi đoạn code trích dưới đây là **nguyên văn từ repo thật**, kèm số dòng để bạn đối chiếu.

---

## 0. Đính chính so với kế hoạch trước (rất quan trọng, đọc trước khi code)

Bản review AI gốc có nhiều chỗ sai hoặc lỗi thời. Đây là sai khác thật đã xác nhận:

| # | Bản review AI nói gì | Thực tế trong code | Ảnh hưởng |
|---|---|---|---|
| 1 | README chỉ liệt kê 10 source type, không có `composite_key_lookup` | **Có thật** trong code (`data_source_registry.py:2461`), cùng `matrix_lookup` (:1858), `aggregate_from_items` (:2727), `pipeline`, `conditional`, `fallback_chain`, `reuse_formula_result`. README chỉ là tài liệu lỗi thời, không phải code. | Nhánh "migrate sang composite_key_lookup" đi đúng — **nhưng thực ra đã migrate xong rồi**, xem #2. |
| 2 | Composite pricing "chưa migrate", `aluminum_price_composite` là 1 bản viết tay song song | **Đã migrate và đang là đường chạy CHÍNH trong production.** `alumglass/setup/install_fb_bindings.py` tự seed 1 `Formula Variable Binding` (`COMPOSITE_MATERIAL_PRICE`, `source_type=aluminum_price_composite`) mỗi lần `bench migrate`, tự động, không cần thao tác tay. `bom_orchestrator._fetch_composite_prices()` (nhánh Python thuần) giờ chỉ là **lưới an toàn**, comment trong code ghi rõ: *"về lý thuyết KHÔNG còn được gọi trong vận hành bình thường"*. | Không cần làm lại việc migrate — việc thật còn lại là **sửa N+1** (vẫn còn, xem mục 2). |
| 3 | Bug "rule_code collision khi nhiều vị trí dùng chung rule" chưa sửa | **Đã sửa.** `bom_orchestrator.py:731-759` có hẳn 1 đoạn comment `# FIX (bug thật): ...` giải thích rõ bug cũ và cách sửa — cache theo cặp `(rule_code, rule_input)` thay vì chỉ `rule_code`. | Bỏ khỏi backlog — không cần làm lại. |
| 4 | `AL Dynamic Item Rule.resolve_item()` là vòng lặp Python "kém hiệu năng", cần đưa qua FB để tránh N+1 | **Không phải vấn đề hiệu năng thật.** `resolve_item()` dùng `frappe.get_cached_doc("AL Dynamic Item Rule", rule_code)` — Frappe tự cache doc (kèm child table) theo request, nên gọi lại nhiều lần cùng `rule_code` **không tốn thêm query nào**. Vòng lặp `threshold_rows`/`lookup_rows` bên trong là thuần Python, không đụng DB. | Việc đưa Dynamic Item Rule qua FB vẫn có giá trị **kiến trúc** (1 formula engine duy nhất) nhưng **không phải fix hiệu năng** — hạ ưu tiên xuống, không khẩn cấp. |
| 5 | Hardcode `"KINH"` "chỉ còn trong comment, không còn trong code thực thi" | **Sai — vẫn còn 3 chỗ thật trong code thực thi:** `bom_orchestrator.py:721` và `:781` (`if (item.get("category") or "").upper() == "KINH":`), **cộng 1 chỗ thứ 3 ngoài `bom_orchestrator`**: `api/__init__.py:729` (`if (item.get("category") or "").upper() != "KINH":` — dùng để build `glass_groups` cho dialog "Kính theo vị trí", đường chạy thật khi mở dialog báo giá). Bản review cũ (và bản mục 5 trước) chỉ đếm 2 chỗ — **thiếu chỗ thứ 3 này**. | Đưa lại vào backlog thật, xem mục 5 (đã bổ sung chỗ 3). |
| 6 | Hardcode `"MAU_SAC"` trong `_color_variable_for_category`, đề xuất thêm field `represents_color` | **Đúng, xác nhận còn** (`bom_orchestrator.py:1307`). `AL Pricing Dimension` **chưa có** field `represents_color`. | Giữ nguyên trong backlog, xem mục 6. |
| 7 | `AL Variable Dimension Mapping.material_category` là `Link → "AL Material Category"` | **Đúng, xác nhận qua doctype JSON.** | Giữ nguyên là quyết định chiến lược (Giai đoạn 5), chưa làm ở đây. |
| 8 | Không có source type nào tra theo khoảng số (threshold/range) | **Đúng, xác nhận — grep toàn bộ `data_source_registry.py`, 0 kết quả cho `range/threshold/bracket`.** | Gap thật — mục 3 dưới đây là code cụ thể. |
| 9 | `AL Material Category` không có field nào để phân biệt "đây là category kính" ngoài so sánh chuỗi | **Sai — đã có sẵn field `requires_glass_master` (Check)**, vốn đang dùng đúng mục đích này (yêu cầu chọn Glass Master) nhưng chưa được tái dùng để thay hardcode `"KINH"`. | Dùng field có sẵn, không cần thêm field mới — xem mục 5. |

---

## 1. Việc nào KHÔNG cần làm (đã xong hoặc không phải bug)

- ❌ Migrate `aluminum_price_composite` → `composite_key_lookup`: **không cần** — 2 source type đã cùng tồn tại, alumglass chủ động chọn giữ `aluminum_price_composite` vì nó gói sẵn nghiệp vụ 2-mode (`exact_match`/`multiplier_chain`) đọc trực tiếp từ `AL Variable Dimension Mapping`; đổi sang `composite_key_lookup` (generic) sẽ yêu cầu 1 tầng config JSON build từ mapping mỗi lần — không có lợi ích rõ ràng, chỉ tăng rủi ro. Khuyến nghị: **giữ nguyên**, chỉ sửa N+1 (mục 2).
- ❌ Sửa rule_code collision: đã sửa.
- ❌ Coi `_resolve_dynamic_item`/`resolve_item()` là bug hiệu năng: không phải, đã có `get_cached_doc`.

## 2. Việc thật #1 — Sửa N+1 query trong `_fetch_composite_prices_via_fb`

### Xác nhận bug bằng code thật

File: `alumglass/engine/bom_orchestrator.py`, hàm `_fetch_composite_prices_via_fb` (dòng 1095-1158):

```python
for item_code in item_codes:
    row_ctx = dict(self.inputs)
    row_ctx["item_code"] = item_code
    ...
    resolved = resolve_all_bindings_batch(
        bindings, doc=self._qi_doc, pre_resolved=row_ctx)   # ← gọi lại cho MỖI item_code
```

`resolve_all_bindings_batch` (từ `formula_builder/api/batch_binding_resolver.py`) resolve **1 row-context** mỗi lần gọi — nó KHÔNG có API multi-row. Bên trong, handler `aluminum_price_composite` (`fb_handlers.py:46-113`, mode `exact_match`) tự chạy:
```python
mappings = frappe.get_all("AL Variable Dimension Mapping", filters=mapping_filters, ...)   # query #1
...
rows = frappe.get_all("Item Price", filters={"item_code": item_code, ...}, ...)             # query #2
```
→ với M mã vật tư khác nhau trong 1 BOM, tốn **tới 2×M query** thay vì 2 query tổng.

So sánh: nhánh fallback `_fetch_composite_prices()` (dòng 1160-1216) đã làm ĐÚNG — 1 query `Item Price` cho TẤT CẢ `item_codes` (`filters={"item_code": ("in", item_codes), ...}`), cache mapping ở `self._dim_mapping_raw_cache` (dòng 917-951, cache theo instance, ưu tiên đọc snapshot bất biến), rồi loop Python thuần (không DB) gọi `best_partial_match`.

### ⚠️ RỦI RO CHƯA XỬ LÝ (bổ sung 2026-09-07) — hành vi "no-match" khác nhau giữa 2 nhánh

Fix "FB-max gọi thẳng fallback" (bên dưới) chỉ AN TOÀN nếu xử lý đúng case **KHÔNG
tìm được Item Price khớp** — vì 2 nhánh hiện khác nhau ở đúng case đó:

| | FB handler (production hiện tại) | Fallback `_fetch_composite_prices` |
|---|---|---|
| Không match, không có row "trần" | `best_partial_match` → `None` → **return `0`** (`fb_handlers.py:112-113`) — không crash, BOM vẫn tính | `_match_composite_price` → **`frappe.throw(...)`** (`bom_orchestrator.py:1234-1238`) — **crash cả BOM** |

→ Nếu theo đúng code đề xuất cũ (gọi thẳng `self._fetch_composite_prices(item_codes, price_list=...)`),
một BOM đang chạy êm (FB-max trả `0`) sẽ chuyển sang **THROW** khi có item thiếu giá
khớp — đúng loại "lệch kết quả 2 nhánh" mà chính file này cảnh báo, nhưng nguồn lệch
cụ thể này chưa được chỉ ra và xử lý. Phải xử lý trước khi merge (xem sửa chữ ký ở dưới).

### Cách sửa: KHÔNG đổi core `formula_builder`, sửa ngay trong `bom_orchestrator.py`

Nguyên tắc: nhánh FB-max vẫn phải **đọc config từ binding** (price_list, pricing_mode — để tôn trọng nguyên tắc data-driven, không hardcode), nhưng phần fetch dữ liệu phải làm **1 lần cho cả nhóm item_code**, y hệt cách nhánh fallback đang làm — tái dùng lại đúng `_dim_fieldnames_for_category` + `best_partial_match` đã có sẵn và đã cache tốt.

**Thay thế toàn bộ hàm `_fetch_composite_prices_via_fb`** (dòng 1095-1158) bằng:

```python
def _fetch_composite_prices_via_fb(self, item_codes):
    """B2 FB-max: resolve composite price — batch 1 lần cho TẤT CẢ item_codes.

    FIX N+1 (2026-09): bản cũ gọi `resolve_all_bindings_batch` theo TỪNG
    item_code (M lần), khiến handler `aluminum_price_composite` tự query lại
    "AL Variable Dimension Mapping" + "Item Price" mỗi lần — 2×M query thay vì
    2 query tổng. `resolve_all_bindings_batch` không có API multi-row, nên sửa
    tại đây: đọc CONFIG (price_list, pricing_mode) từ binding đúng 1 lần, rồi
    tái dùng thẳng `_dim_fieldnames_for_category` + `engine/composite_pricing.
    best_partial_match` (đã cache mapping ở `self._dim_mapping_raw_cache`,
    y hệt nhánh fallback `_fetch_composite_prices`) — không còn khác biệt
    thuật toán giữa 2 nhánh, chỉ khác nguồn config (binding vs hardcode).

    Trả về {item_code: price} hoặc None nếu binding không cấu hình pricing_mode
    hỗ trợ (caller fallback `_fetch_composite_prices` cũ — bảo toàn golden).
    """
    bindings = self._get_pricing_bindings()
    if not bindings:
        return None

    # Chỉ hỗ trợ đúng 1 binding chủ (COMPOSITE_MATERIAL_PRICE, source_type=
    # aluminum_price_composite) — nếu có nhiều binding pricing khác cấu hình
    # (vd composite_key_lookup thuần), giữ nguyên đường cũ (per-item) cho các
    # binding đó, KHÔNG tối ưu (hiếm gặp, an toàn hơn viết thêm nhánh mới).
    fast_path_bindings = [
        b for b in bindings
        if b.get("source_type") == "aluminum_price_composite"
    ]
    other_bindings = [b for b in bindings if b not in fast_path_bindings]
    if not fast_path_bindings or other_bindings:
        return self._fetch_composite_prices_via_fb_slow(bindings, item_codes)

    import json
    cfg = json.loads(fast_path_bindings[0].get("source_config") or "{}")
    pricing_mode = cfg.get("pricing_mode", "exact_match")
    price_list = cfg.get("price_list") or _default_price_list()

    if pricing_mode == "exact_match":
        # Y hệt thuật toán fallback — tái dùng thẳng, chỉ price_list đến từ
        # binding.source_config thay vì hardcode.
        return self._fetch_composite_prices(item_codes, price_list=price_list)

    if pricing_mode == "multiplier_chain":
        return self._fetch_composite_prices_multiplier_chain(item_codes, price_list=price_list)

    return None


def _fetch_composite_prices_via_fb_slow(self, bindings, item_codes):
    """Đường cũ (per-item, có N+1) — CHỈ dùng khi có binding pricing khác
    thường (không phải aluminum_price_composite chuẩn), trường hợp hiếm.
    Giữ nguyên logic gốc để không phá vỡ hành vi cho case lạ.
    """
    from formula_builder.api.batch_binding_resolver import resolve_all_bindings_batch

    category_by_code = self._category_by_code()
    color_category_by_code = self._color_category_by_code()
    color_overrides = self._compute_color_price_overrides()
    prices = {}
    for item_code in item_codes:
        row_ctx = dict(self.inputs)
        row_ctx["item_code"] = item_code
        row_ctx["price_base_item"] = item_code
        row_ctx["category"] = category_by_code.get(item_code, "")
        color_var = self._color_variable_for_category(
            color_category_by_code.get(item_code, ""))
        if color_var:
            override_val = color_overrides.get((item_code, color_var))
            if override_val:
                row_ctx[color_var] = override_val
        row_ctx["row"] = {
            "item_code": item_code,
            "price_base_item": item_code,
            "category": category_by_code.get(item_code, ""),
        }
        try:
            resolved = resolve_all_bindings_batch(
                bindings, doc=self._qi_doc, pre_resolved=row_ctx)
        except Exception:
            continue
        for _var_name, val in resolved.items():
            if isinstance(val, (int, float)) and val:
                prices[item_code] = float(val)
                break
    return prices if prices else None


def _fetch_composite_prices_multiplier_chain(self, item_codes, price_list):
    """multiplier_chain mode — batch 1 query base price cho TẤT CẢ item_codes,
    `frappe.get_cached_value` cho multiplier theo linked doctype (đã request-
    cache sẵn trong Frappe, không cần tự cache thêm).
    """
    if not item_codes:
        return {}

    base_rows = frappe.get_all(
        "Item Price",
        filters={"item_code": ("in", item_codes), "price_list": price_list},
        fields=["item_code", "price_list_rate"],
    )
    base_price_by_item = {}
    for r in base_rows:
        # Giữ đúng hành vi cũ: lấy dòng ĐẦU TIÊN gặp cho mỗi item_code
        # (code cũ dùng limit=1 không order_by — không có thứ tự đảm bảo,
        # nên "first encountered" là tương đương hợp lệ).
        base_price_by_item.setdefault(r["item_code"], r["price_list_rate"])

    category_by_code = self._category_by_code()
    mappings, dims_raw = self._get_dim_mappings_raw()
    # dims_raw: {dimension_code: custom_fieldname} — cần thêm link_doctype,
    # nên query riêng 1 lần (không có trong _get_dim_mappings_raw cache).
    dim_codes = list({m["pricing_dimension"] for m in mappings})
    dim_link_doctype = {}
    if dim_codes:
        for d in frappe.get_all(
            "AL Pricing Dimension",
            filters={"name": ("in", dim_codes)},
            fields=["name", "link_doctype"],
        ):
            dim_link_doctype[d["name"]] = d.get("link_doctype")

    prices = {}
    for item_code in item_codes:
        base_price = base_price_by_item.get(item_code)
        if not base_price:
            prices[item_code] = 0
            continue
        category = category_by_code.get(item_code, "")
        total_multiplier = 1.0
        for m in mappings:
            if category and m.get("material_category") != category:
                continue
            var_value = self.inputs.get(m["variable_name"])
            if var_value is None or var_value == "":
                continue
            map_mult = m.get("price_multiplier", 1.0) or 1.0
            link_doctype = dim_link_doctype.get(m["pricing_dimension"])
            linked_mult = 1.0
            if link_doctype and var_value:
                try:
                    linked_mult = frappe.get_cached_value(
                        link_doctype, var_value, "price_multiplier") or 1.0
                except Exception:
                    linked_mult = 1.0
            effective_mult = linked_mult if linked_mult != 1.0 else map_mult
            total_multiplier *= effective_mult
        prices[item_code] = base_price * total_multiplier
    return prices
```

**Sửa chữ ký `_fetch_composite_prices`** (dòng 1160) để nhận `price_list` tuỳ chọn thay vì luôn gọi `_default_price_list()` bên trong — giữ tương thích ngược 100% (tham số mặc định `None`):

```python
def _fetch_composite_prices(self, item_codes, price_list=None, allow_missing=False):
    """..."""
    if not item_codes:
        return {}
    price_list = price_list or _default_price_list()
    ...
    for ip in frappe.get_all(
        "Item Price",
        filters={"item_code": ("in", item_codes),
                 "price_list": price_list},          # ← đổi từ _default_price_list() sang biến price_list
        fields=price_fields,
    ):
```
**BỔ SUNG 2026-09-07 — KHÔNG "chỉ đổi đúng dòng `filters={...}`" như ghi chú cũ.**
Kèm theo phải sửa call-site `_match_composite_price` trong `_fetch_composite_prices`
(~dòng 1214) để no-match KHÔNG throw khi được yêu cầu — xem ⚠️ rủi ro ở đầu mục 2.
Cách tối thiểu: dùng thẳng `best_partial_match` trong vòng lặp và tôn trọng `allow_missing`:

```python
        # ── Thay toàn bộ phần chọn giá trong vòng lặp rows_by_item ──
        for item_code, rows in rows_by_item.items():
            dim_fieldnames = self._dim_fieldnames_for_category(
                category_by_code.get(item_code, ""))
            row_inputs = dict(self.inputs)
            color_var = self._color_variable_for_category(
                color_category_by_code.get(item_code, ""))
            if color_var:
                override_val = color_overrides.get((item_code, color_var))
                if override_val:
                    row_inputs[color_var] = override_val
            price = best_partial_match(rows, dim_fieldnames, row_inputs)
            if price is None:
                if not allow_missing:
                    frappe.throw(
                        f"Không tìm được Item Price khớp cho '{item_code}' với composite "
                        f"key hiện tại. Kiểm tra lại bảng giá (Item Price) hoặc thêm 1 "
                        f"dòng giá mặc định không gắn dimension nào."
                    )
                continue          # allow_missing=True: bỏ qua item — semantics FB cũ (trả 0/không set)
            prices[item_code] = price
        return prices
```

> **Caller dùng tham số mới:** FB-max reuse (`_fetch_composite_prices_via_fb` mới ở
> trên) → gọi `allow_missing=True` (giữ nguyên hành vi FB production). Caller cũ —
> "lưới an toàn" dòng 676-677 — giữ mặc định `False` (golden không đổi, vẫn throw
> khi thiếu giá như hiện tại).

**Note quan trọng — `_get_pricing_bindings()`**: hàm này (dòng 981-1029) hiện lọc theo `_PRICING_SOURCE_TYPES = ("composite_key_lookup", "aluminum_price_composite")`. Không cần đổi gì ở đây — fix chỉ nằm ở cách *dùng* kết quả trả về.

### Test bắt buộc trước khi merge (Task 1.1 áp dụng riêng cho việc này)
- [ ] Viết test: BOM có ≥5 mã nhôm khác category, đếm số lần `frappe.get_all` được gọi (mock/spy) — **trước fix**: tăng tuyến tính theo số item_code; **sau fix**: hằng số (2-3 query bất kể bao nhiêu item_code).
- [ ] Test so sánh giá trị trả về CŨ (hàm gốc, lưu lại 1 bản backup trước khi sửa) vs MỚI trên cùng 1 tập BOM item thật — cả 2 mode `exact_match` và `multiplier_chain`.
- [ ] Test case "binding pricing lạ" (không phải `aluminum_price_composite`) vẫn rơi đúng vào `_fetch_composite_prices_via_fb_slow`.
- [ ] **Test no-match (BỔ SUNG 2026-09-07):** BOM có 1 item KHÔNG có Item Price khớp (không có row "trần") → TRƯỚC fix FB-max trả `0` cho item đó, BOM vẫn tính. SAU fix với `allow_missing=True` phải **GIỮ NGUYÊN (không throw)** — golden bắt buộc.
- [ ] **Test đếm query standalone (BỔ SUNG):** test N+1 nên theo khuôn `standalone_tests/test_phase_b_fbmax.py` (FakeFrappe/FakeDB, chạy `python3 -m pytest standalone_tests/...` KHÔNG cần bench/site). ⛔ KHÔNG đưa file test dùng stub `frappe` vào `alumglass/tests/` package — `bench run-tests` os.walk collect TOÀN BỘ package (mọi `test_*.py` bên trong bị import) → stub thay `frappe` sẽ phá toàn bộ suite (chính comment đầu file standalone đã cảnh báo, tránh tái phạm).

---

## 3. Việc thật #2 — `range_lookup`: source type mới cho THRESHOLD lookup

Xác nhận gap: `grep -in "range_lookup\|threshold\|bracket" formula_builder/api/data_source_registry.py` → **0 kết quả**. Đây là source type thật sự chưa tồn tại.

### File cần sửa: `formula_builder/api/data_source_registry.py`

Chèn đoạn sau **ngay sau khối `composite_key_lookup`** (sau dòng 2549, trước comment `# aggregate_from_items` ở dòng ~2552), theo đúng `docs/fb_source_type_contract.md` (đã đọc — decorator `@register_source` từ `source_type_registry`, KHÔNG dùng decorator cục bộ cũ):

```python
# ═══════════════════════════════════════════════════════════════════════════
# range_lookup — tra giá trị theo khoảng số (from-to → result)
#   Tổng quát hoá AL Dynamic Item Rule (THRESHOLD mode) của alumglass, dùng
#   được cho MỌI ngành cần phân bậc theo ngưỡng số (thuế lũy tiến, cước phí
#   theo trọng lượng, quy cách vật liệu theo độ dày...).
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_range_rows(cfg):
    """Fetch toàn bộ dòng khoảng (from/to/value) theo doctype + filters."""
    doctype = cfg.get("doctype", "")
    value_field = cfg.get("value_field", "")
    from_field = cfg.get("range_from_field", "")
    to_field = cfg.get("range_to_field", "")
    if not (doctype and value_field and from_field and to_field):
        return []
    fields = ["name", value_field, from_field, to_field]
    filters = cfg.get("filters") or []
    try:
        return frappe.get_all(doctype, filters=filters or None, fields=fields) or []
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"DataSource: range_lookup ({doctype})")
        return []


def _match_range_value(rows, cfg, input_val, default_value, data_type):
    from_field = cfg.get("range_from_field", "")
    to_field = cfg.get("range_to_field", "")
    value_field = cfg.get("value_field", "")
    try:
        val = float(input_val)
    except (TypeError, ValueError):
        return default_value
    for r in rows:
        try:
            lo = float(r.get(from_field))
            hi = float(r.get(to_field))
        except (TypeError, ValueError):
            continue
        if lo <= val <= hi:
            return _cast(r.get(value_field), data_type)
    return default_value


@register_source(
    "range_lookup",
    label="Range / Threshold Lookup",
    description=(
        "Tra giá trị từ bảng khoảng số (from-to → result), dùng chung cho "
        "mọi ngành cần phân bậc theo ngưỡng số (thuế lũy tiến, cước phí theo "
        "trọng lượng, quy cách vật liệu theo độ dày...). Tổng quát hoá "
        "AL Dynamic Item Rule (THRESHOLD mode) của alumglass — data (bảng "
        "ngưỡng) vẫn nằm ở doctype ngành, chỉ engine tra cứu dùng chung."
    ),
    config_schema={
        "type": "object",
        "required": ["doctype", "value_field", "input_value",
                     "range_from_field", "range_to_field"],
        "properties": {
            "doctype": {"type": "string", "description": "DocType chứa các dòng khoảng (from/to/value)"},
            "value_field": {"type": "string", "description": "Field chứa kết quả trả về"},
            "input_value": {"type": "string", "description": "Giá trị cần tra; hỗ trợ template {{row.x}}/{{doc.x}}/{{resolved.x}}"},
            "range_from_field": {"type": "string", "description": "Field chứa cận dưới (inclusive)"},
            "range_to_field": {"type": "string", "description": "Field chứa cận trên (inclusive)"},
            "filters": {"type": "array", "description": "Frappe filters bổ sung (vd lọc theo parent rule_code)"},
            "default_value": {"type": ["number", "string"], "description": "Giá trị trả về khi không khớp khoảng nào"},
        },
    },
    app="formula_builder",
    batchable=True,
    fingerprint_fn=lambda cfg: "range_lookup:" + cfg.get("doctype", "") + "|" + json.dumps(cfg.get("filters") or [], sort_keys=True),
    supports_transform=True,
    supports_cache=True,
    default_cache_ttl=300,
)
def _handle_range_lookup(binding, doc, resolved_so_far):
    cfg = json.loads(binding.get("source_config") or "{}")
    default_value = cfg.get("default_value", binding.get("default_value"))
    data_type = binding.get("data_type") or cfg.get("type", "Float")

    row = _binding_row(binding, resolved_so_far)
    input_val = _resolve_template_val(cfg.get("input_value"), doc, resolved_so_far, row)
    if input_val is None or input_val == "":
        return default_value

    rows = _fetch_range_rows(cfg)
    if not rows:
        return default_value

    return _match_range_value(rows, cfg, input_val, default_value, data_type)


def _resolve_range_lookup_batch(bindings, doc, resolved_so_far):
    """Batch: fetch rows 1 lần/group (cùng doctype+filters), resolve từng binding."""
    results = {}
    if not bindings:
        return results
    cfg0 = json.loads(bindings[0].get("source_config") or "{}")
    rows = _fetch_range_rows(cfg0)
    for b in bindings:
        cfg = json.loads(b.get("source_config") or "{}")
        default_value = cfg.get("default_value", b.get("default_value"))
        data_type = b.get("data_type") or cfg.get("type", "Float")
        row = _binding_row(b, resolved_so_far)
        input_val = _resolve_template_val(cfg.get("input_value"), doc, resolved_so_far, row)
        if input_val is None or input_val == "" or not rows:
            results[b["variable_name"]] = default_value
            continue
        results[b["variable_name"]] = _match_range_value(rows, cfg, input_val, default_value, data_type)
    return results


_handle_range_lookup.resolve_batch = _resolve_range_lookup_batch
```

**Lưu ý bám đúng contract (mục 4 của `fb_source_type_contract.md`):** `@register_source` tự đăng ký vào cả `SourceTypeRegistry` (central) và `_data_source_handlers` (legacy dict) — không cần đăng ký tay thêm ở đâu khác. Vì `app="formula_builder"` (không phải `"alumglass"`), source type này xuất hiện cho MỌI app dùng chung platform, đúng tinh thần "generic capability thuộc core".

**BỔ SUNG 2026-09-07 — 3 lưu ý trước khi merge `range_lookup`:**

1. **Blast radius core platform:** `formula_builder` là app dùng chung — eupapp đang
   dùng (xem `eupapp/docs/dev/costing-fb-sp-price-plan.md`). Source type mới là
   **additive** (không phá code cũ), nhưng test bắt buộc phải chạy **toàn bộ suite
   FB** (`python -m unittest formula_builder.tests...` theo contract) + smoke test
   costing eupapp trước khi merge — KHÔNG chỉ test alumglass.
2. **2 repo riêng:** code + docs + test `range_lookup` thuộc repo **`formula_builder`**
   (`~/myfrappe/apps/formula_builder`), commit ở đó — ⛔ KHÔNG nằm chung PR/commit với
   các fix alumglass mục 2/5/6 (repo khác nhau).
3. **Giới hạn `_fetch_range_rows`:** `filters` KHÔNG bắt buộc trong `config_schema` —
   nếu binding seed quên filter (`parent=rule_code`...) source type sẽ `get_all`
   **TOÀN BỘ doctype** mỗi lần resolve. Trong `docs/range_lookup.md` ghi rõ: config
   nên kèm filter; cân nhắc thêm `limit_page_length` mặc định trong code trước khi
   ship. Nhóm batch `_resolve_range_lookup_batch` chỉ AN TOÀN khi các binding cùng
   `(doctype, filters)` — fingerprint đã gom đúng, nhưng phải ghi ràng buộc này vào
   docstring hàm để người sau không "mở rộng" nhóm batch sai (đọc 2 config khác nhau
   mà fetch 1 lần theo `cfg0`).

### File cần thêm: `docs/range_lookup.md`

Theo đúng checklist mục 7 của contract ("Docs: `docs/<source_type>.md` theo mẫu composite_key_lookup.md, kèm ví dụ ứng dụng thực tế"). Nội dung tối thiểu: mô tả, config_schema, 1 ví dụ JSON config thật (dùng ví dụ ngưỡng độ dày kính → mã nẹp, đúng bài toán RULE-NEP-GLASSTHICK của alumglass), lưu ý inclusive cả 2 đầu `[from, to]`.

### File cần thêm: test — `formula_builder/tests/test_range_lookup.py`

Theo đúng khuôn `test_platform_source_types.py` (import trực tiếp module, mock `frappe.get_all`, không cần site thật). Test tối thiểu:
- [ ] Khớp đúng 1 khoảng (giữa from-to).
- [ ] Khớp biên (val == from, val == to) — vì điều kiện là `<=` cả 2 đầu.
- [ ] Không khớp khoảng nào → trả `default_value`.
- [ ] `input_value` template `{{row.glass_thick}}`.
- [ ] `resolve_batch`: 2 binding cùng doctype/filters → chỉ 1 lần `frappe.get_all` (spy/mock đếm call count).
- [ ] Đăng ký cả central registry lẫn legacy dict (`get_handler("range_lookup")` phải trả về callable).
- [ ] `config_schema` validate: thiếu `range_from_field` → lỗi.

Chạy theo đúng lệnh trong contract: `python -m unittest formula_builder.tests.test_platform_source_types formula_builder.tests.test_config_io formula_builder.tests.test_fb1_revised` (thêm `test_range_lookup` vào danh sách này).

---

## 4. Wiring `range_lookup` vào `AL Dynamic Item Rule` (THRESHOLD mode) — ưu tiên THẤP, không khẩn cấp

Vì mục 0.4 đã xác nhận **không có vấn đề hiệu năng thật** (nhờ `get_cached_doc`), việc này chỉ có giá trị kiến trúc ("1 formula engine duy nhất"), **không nên làm trước** mục 2 và 3. Nếu vẫn muốn làm sau này:

- **KHÔNG đổi** `AL Dynamic Item Rule.resolve()` (giữ nguyên `al_dynamic_item_rule.py:33-49`) — admin UI, doctype, versioning giữ y nguyên.
- Thêm 1 API mới song song (không thay thế) trong `al_dynamic_item_rule.py`:
  ```python
  @frappe.whitelist()
  def build_range_lookup_config(rule_code):
      """Sinh source_config JSON cho binding range_lookup từ 1 AL Dynamic Item
      Rule (THRESHOLD mode) — dùng khi admin muốn seed binding FB cho rule
      này thay vì gọi resolve_item() trực tiếp."""
      doc = frappe.get_cached_doc("AL Dynamic Item Rule", rule_code)
      if doc.rule_type != "THRESHOLD":
          frappe.throw("Chỉ áp dụng cho rule_type=THRESHOLD")
      return {
          "doctype": "AL Dynamic Item Rule Threshold Row",
          "value_field": "result_item",
          "range_from_field": "from_value",
          "range_to_field": "to_value",
          "filters": [["parent", "=", rule_code]],
      }
  ```
- Việc quyết định CÓ seed binding hay không (giống cách `install_fb_bindings.py` đã làm cho composite pricing) là quyết định sản phẩm riêng — **để ở Giai đoạn 5**, không code ngay.
- **Blocker bổ sung (2026-09-07) củng cố quyết định "để Giai đoạn 5":** Dynamic Item
  Rule resolve theo **TỪNG dòng BOM** với `rule_input` riêng (`glass_thick`/`glass_type`
  khác nhau từng vị trí kính) — nhưng `resolve_all_bindings_batch` chỉ nhận **đúng 1
  row-context** (`pre_resolved`) mỗi lần gọi. Muốn qua FB phải loop per-row như hiện
  tại (mất ý nghĩa "batch") HOẶC thêm **API multi-row** ở FB core — không phải chỉ
  "seed 1 binding" là xong. Việc này tự thân là 1 dự án con, không nên chen vào đợt
  fix này.

---

## 5. Fix hardcode `"KINH"` — dùng field có sẵn `AL Material Category.requires_glass_master`

Xác nhận: `AL Material Category` đã có sẵn field `requires_glass_master` (Check) — đúng mục đích cần, không cần thêm field mới.

⚠️ **BỔ SUNG 2026-09-07:** hardcode `"KINH"` trong code thực thi là **3 chỗ**, không phải 2:
1. `bom_orchestrator.py:721`
2. `bom_orchestrator.py:781`
3. **`api/__init__.py:729`** (`if (item.get("category") or "").upper() != "KINH": continue` — build `glass_groups` cho dialog "Kính theo vị trí", đường chạy thật khi mở dialog báo giá).

→ Để tránh lần sau lại sót chỗ thứ N, gom thành **1 helper dùng chung** (mục Bước 0 dưới)
thay vì rải fetch logic ở từng call-site.

### File mới/helper: `alumglass/al_bom_engine/glass_group_resolver.py`

**Bước 0** — thêm hàm dùng chung (module này `bom_orchestrator` (qua `glass_group_rep`) VÀ `api/__init__.py` (qua `glass_group_rep`) đều đã import — không sợ vòng import):

```python
def fetch_glass_category_codes(category_codes):
    """{category} có requires_glass_master=1 — NGUỒN DUY NHẤT để nhận diện
    "category kính" (thay hardcode "KINH"). Dùng chung bom_orchestrator +
    api/__init__ (glass_groups) để 2 nơi KHÔNG bao giờ lệch.
    """
    if not category_codes:
        return set()
    return {
        mc["name"] for mc in frappe.get_all(
            "AL Material Category",
            filters={"name": ("in", list(set(category_codes))),
                     "requires_glass_master": 1},
            fields=["name"],
        )
    }
```

### File: `alumglass/engine/bom_orchestrator.py`

**Bước 1** — trong `b2_prefetch_master_data` (ngay sau đoạn "Batch query #4: Material Categories", khoảng dòng 700-709): query `material_categories` GIỮ NGUYÊN nhưng **bỏ cột `requires_glass_master`** (không còn dùng ở đây — tránh 2 nơi đọc cùng 1 cờ). Tập category-kính lấy từ **helper Bước 0** (1 query riêng, code dùng chung 100% với `api/__init__`, không fork logic):

```python
        material_categories = {}
        cat_codes = list({item.get("category", "") for item in self.bom_items if item.get("category")})
        if cat_codes:
            for mc in frappe.get_all("AL Material Category",
                                      filters={"name": ("in", cat_codes)},
                                      fields=["name", "default_scrap_pct", "has_weight"]):
                material_categories[mc["name"]] = {
                    "scrap_pct": mc.get("default_scrap_pct", 0) or 0,
                    "has_weight": 1 if mc.get("has_weight") else 0,
                }
        from alumglass.al_bom_engine.glass_group_resolver import fetch_glass_category_codes
        self._glass_categories = fetch_glass_category_codes(cat_codes)   # ← THÊM — helper chung, 1 query
```

**Bước 2** — thay 2 chỗ hardcode trong `bom_orchestrator.py` (dòng 721 và 781 — code hiện
đang có sẵn `material_categories` dict nhưng query KHÔNG còn cần cột `requires_glass_master`
nữa vì đã chuyển sang helper ở Bước 1):

```python
# TRƯỚC (2 chỗ giống nhau trong bom_orchestrator):
if (item.get("category") or "").upper() == "KINH":

# SAU:
if item.get("category") in self._glass_categories:
```

**Bước 3** — chỗ thứ 3 trong `api/__init__.py:729` (build `glass_groups` — KHÔNG có
`self` instance như orchestrator, nên tính `set` tạm từ chính `bom_set` đang xử lý):

```python
# TRƯỚC (api/__init__.py ~729, trong vòng lặp build glass_groups):
    for item in bom_set.get("items", []) or []:
        if (item.get("category") or "").upper() != "KINH":
            continue
        ...

# SAU:
    from alumglass.al_bom_engine.glass_group_resolver import fetch_glass_category_codes
    _glass_cats = fetch_glass_category_codes(
        {it.get("category", "") for it in bom_set.get("items", []) or [] if it.get("category")})
    for item in bom_set.get("items", []) or []:
        if item.get("category") not in _glass_cats:
            continue
        ...
```

**Rủi ro cần lưu ý:** nếu category "KINH" hiện tại trong dữ liệu thật **chưa bật** `requires_glass_master=1` (dù về mặt nghiệp vụ nó nên là kính), việc đổi này sẽ **âm thầm đổi hành vi**. Bắt buộc trước khi deploy: `SELECT name, requires_glass_master FROM \`tabAL Material Category\` WHERE name = 'KINH'` (hoặc tương đương qua UI) — nếu chưa bật, bật trước hoặc thêm data migration patch bật cờ này cho category kính hiện có.

- [ ] Test: BOM có dòng category="KINH" (đã bật `requires_glass_master`) → hành vi glass_data giống hệt trước khi sửa.
- [ ] Test: thêm 1 category mới tên khác (vd "KINH_CUONG_LUC") có bật `requires_glass_master=1` → tự động được coi là kính mà KHÔNG cần sửa code — chứng minh hết hardcode.
- [ ] **Test chỗ thứ 3 (BỔ SUNG 2026-09-07):** BOM Set có dòng category="KINH_CUONG_LUC" (bật cờ) → dialog "Kính theo vị trí" (`api/__init__.py` build `glass_groups`) vẫn sinh đúng selector cho dòng đó — KHÔNG phụ thuộc chuỗi "KINH".
- [ ] **Kiểm tra rà soát (BỔ SUNG):** sau khi fix, grep toàn repo phải về 0 kết quả hardcode so sánh category chuỗi: `grep -rn "upper() == .KINH.\|upper() != .KINH." alumglass/ --include=*.py` → 0 (chỉ còn trong comment/seed demo cho phép).

---

## 6. Fix hardcode `"MAU_SAC"` — thêm field `represents_color`

### File: `alumglass/al_master_data/doctype/al_pricing_dimension/al_pricing_dimension.json`

Thêm 1 field Check mới vào mảng `fields` (đặt cạnh `is_required_for_price`/`is_active`, cùng column break hiện có ở `column_1`):

```json
{
    "fieldname": "represents_color",
    "fieldtype": "Check",
    "label": "Represents Color Dimension?",
    "description": "Bật nếu dimension này đại diện cho \"màu sắc\" — dùng để engine tự nhận diện biến màu theo category (_color_variable_for_category), thay vì hardcode dimension_code = \"MAU_SAC\"."
}
```
*(Chèn ngay sau field `is_required_for_price` trong danh sách `fields`, trước `is_active` hoặc `sort_order` — vị trí chính xác không quan trọng về mặt chức năng, chỉ ảnh hưởng thứ tự hiển thị form.)*

Sau khi thêm field JSON, chạy `bench migrate` để Frappe tự sync doctype (không cần patch riêng vì đây là field mới, không có data cũ cần backfill logic — nhưng **cần 1 patch nhỏ để set `represents_color=1`** cho đúng 1 bản ghi `AL Pricing Dimension` có `name="MAU_SAC"` hiện có, xem bên dưới).

### File mới: patch data — `alumglass/patches/v29_XX_set_represents_color_flag.py`
*(đặt tên patch theo đúng version hiện tại của app, xem `alumglass/patches.txt` để lấy số version kế tiếp đúng)*

```python
import frappe


def execute():
    """Backfill represents_color=1 cho dimension MAU_SAC hiện có — để
    _color_variable_for_category() có thể chuyển từ hardcode string sang
    đọc cờ này mà không đổi hành vi."""
    if frappe.db.exists("AL Pricing Dimension", "MAU_SAC"):
        frappe.db.set_value("AL Pricing Dimension", "MAU_SAC", "represents_color", 1)
```
Thêm dòng `alumglass.patches.v29_XX_set_represents_color_flag` vào `alumglass/patches.txt`.

### File: `alumglass/engine/bom_orchestrator.py`, hàm `_color_variable_for_category` (dòng 1295-1309)

```python
# TRƯỚC:
def _color_variable_for_category(self, category):
    if not category:
        return None
    mappings, _dims = self._get_dim_mappings_raw()
    for m in mappings:
        if m.get("pricing_dimension") == "MAU_SAC" and m.get("material_category") == category:
            return m.get("variable_name")
    return None

# SAU:
def _color_variable_for_category(self, category):
    """Tên biến (variable_name) đại diện cho dimension "màu sắc" của ĐÚNG
    material_category — data-driven qua AL Variable Dimension Mapping +
    AL Pricing Dimension.represents_color (KHÔNG còn hardcode "MAU_SAC")."""
    if not category:
        return None
    mappings, _dims = self._get_dim_mappings_raw()
    color_dim_codes = self._get_color_dimension_codes()
    for m in mappings:
        if m.get("pricing_dimension") in color_dim_codes and m.get("material_category") == category:
            return m.get("variable_name")
    return None


def _get_color_dimension_codes(self):
    """{dimension_code} có represents_color=1 — cache theo instance."""
    if getattr(self, "_color_dim_codes_cache", None) is not None:
        return self._color_dim_codes_cache
    codes = {
        d["name"] for d in frappe.get_all(
            "AL Pricing Dimension",
            filters={"represents_color": 1},
            fields=["name"],
        )
    }
    self._color_dim_codes_cache = codes
    return codes
```

- [ ] Test: sau patch, `_color_variable_for_category("NHOM")` trả về đúng y hệt kết quả trước khi sửa (golden test).
- [ ] Test: thêm 1 dimension mới (vd `"MAU_KINH"`) bật `represents_color=1`, gán mapping cho category kính → `_color_variable_for_category("KINH")` tự nhận ra mà không cần sửa code.

---

## 7. Thứ tự thi công đề xuất (đã cập nhật theo phát hiện thật)

| # | Việc | File chính | Effort ước lượng | Rủi ro |
|---|---|---|---|---|
| 1 | Sửa N+1 `_fetch_composite_prices_via_fb` (mục 2) | `alumglass/engine/bom_orchestrator.py` | Vừa — cần test kỹ 2 mode giá | Trung bình (vùng có lịch sử bug lệch kết quả 2 nhánh) |
| 2 | Fix hardcode `KINH` — **3 chỗ**: `bom_orchestrator.py:721,781` + `api/__init__.py:729` (mục 5) | `bom_orchestrator.py` · `api/__init__.py` · helper mới `al_bom_engine/glass_group_resolver.py` | Nhỏ | Thấp, **nhưng cần verify data `requires_glass_master` trước** (category kính thật phải bật cờ) |
| 3 | Fix hardcode `MAU_SAC` (mục 6) | `al_pricing_dimension.json` + `bom_orchestrator.py` + 1 patch | Nhỏ | Thấp |
| 4 | `range_lookup` source type mới (mục 3) | `formula_builder/api/data_source_registry.py` + docs + test | Vừa | Thấp (source type mới, không đụng code cũ) |
| 5 | Wiring Dynamic Item Rule qua `range_lookup` (mục 4) | `al_dynamic_item_rule.py` | Nhỏ, KHÔNG khẩn cấp | Thấp — chỉ làm khi có nhu cầu kiến trúc thật |

Việc #1 nên làm trước vì giá trị đo được ngay (giảm query thật). Việc #4 làm trước hoặc sau #1/#2/#3 đều được vì độc lập hoàn toàn (source type mới trong core, không đụng code alumglass hiện có) — có thể làm song song nếu có 2 người.

## 8. Việc CẦN bạn cung cấp thêm trước khi mình viết patch/test chạy thật

- [ ] Xác nhận version hiện tại của app `alumglass` (xem `alumglass/patches.txt` dòng cuối) để đặt đúng tên patch ở mục 6.
- [ ] Xác nhận trong DB thật, category `"KINH"` đã bật `requires_glass_master=1` chưa (mục 5) — nếu chưa, cho biết để mình viết thêm 1 dòng patch bật cờ này trước khi đổi code.
- [ ] Cho biết có category nào khác ngoài `"KINH"` cũng đang được BOM coi là "kính" (nếu có) — để patch bật `requires_glass_master` cho đủ, tránh sót.


=====================================================================

# Audit: alumglass có triển khai dư thừa không? formula_builder cần thêm gì?

> Đọc trực tiếp code thật (đã clone), không suy đoán. Trả lời 2 câu hỏi:
> 1. alumglass có chỗ nào tự viết tay dù `formula_builder` đã/nên có sẵn không?
> 2. `formula_builder` có cần thêm năng lực generic nào để thật sự là platform đa ngành?

**Kết luận ngắn gọn trước:** mức độ "dư thừa" **thấp hơn nhiều** so với ấn tượng từ bản review AI gốc — code alumglass hiện tại có kỷ luật kiến trúc rất tốt (nhiều comment kiểu "REFACTOR — dọn nợ, không trùng lặp", "FB-first", "golden-safe"), và đội ngũ trước đã chủ động dọn hầu hết chỗ trùng lặp rõ ràng (cost bucket → `aggregate_from_items`, composite pricing → FVB seed tự động). Cái còn lại là **1 khoảng trống thật, đáng giá** ở phía `formula_builder` core (mục 2), chứ không phải alumglass "lười dùng FB".

---

## 1. alumglass — chỗ nào thật sự dư thừa / chưa tận dụng FB

### 1.1 `formula_handlers.py::lookup_calc_pattern` — dư thừa MỘT PHẦN (mức độ: đáng chú ý)

**Hiện trạng** (đọc `alumglass/formula_handlers.py`, 366 dòng): đây là 1 "thư viện hàm tính số lượng" data-driven — `AL Quantity Calc Method.calc_fn` (chuỗi lambda trong DB) → compile bằng `formula_builder.security.safe_eval.compile_expression` → cache (positive + negative) → fallback 14 pattern built-in (`PATTERN_FORMULAS`, Python lambda cứng trong code) nếu DB không có record.

**Điểm đã làm ĐÚNG (không phải dư thừa):** dùng `compile_expression` của FB thay vì tự viết `eval()` — đây chính xác là điều `fb_source_type_contract.md` mục 8 yêu cầu ("Mọi config user-controlled KHÔNG bao giờ eval() trần"). Alumglass đã tuân thủ đúng.

**Điểm dư thừa thật:** cơ chế "named parameterized function, DB-first + code fallback, có cache" này về bản chất là **1 registry hàm tuỳ biến do admin định nghĩa** — hoàn toàn không đặc thù ngành nhôm kính (ngành nào cũng có thể cần "công thức tính số lượng tuỳ biến theo pattern", vd ngành in ấn tính theo khổ giấy, ngành vải tính theo mét vải). Alumglass đã tự xây riêng: cache dict, negative cache, AST validator riêng (`_validate_calc_fn`, ~70 dòng trùng lặp logic với `SecurityValidator` của FB), doctype riêng (`AL Quantity Calc Method`). **Không có cơ chế tương đương trong FB core** để alumglass "tận dụng tối đa" — nên đây không hẳn là lỗi của alumglass, mà là **bằng chứng cho 1 gap thật ở core** (xem mục 2.1).

→ **Không sửa alumglass ngay** — chờ core có `db_function_library` (mục 2.1), rồi migrate `lookup_calc_pattern` sang gọi core đó, xoá `_validate_calc_fn`/cache tay.

### 1.2 `al_bom_engine/system_variable_resolver.py` — dư thừa NHẸ, ưu tiên thấp

**Hiện trạng:** tự dò field Link trên doctype gọi (`resolve_source_link_fields`) để tìm ra bản ghi nguồn cho từng "System Variable" (`AL Variable Library.is_system=1`), rồi đọc field + áp override từ child table `AL Profile System.system_variables` (ưu tiên: child override > linked field > default_value).

**Đã KHÔNG dư thừa ở phần quan trọng nhất:** code đã tự nhận ra và sửa việc có 2 bản viết tay lệch nhau trước đây (`bom_orchestrator` vs `api/__init__.py`), gộp về 1 module dùng chung — đúng nguyên tắc DRY. Và kiến trúc hiện tại là **"FB-first, module này chỉ fill-missing"** (comment rõ ràng trong `bom_orchestrator._resolve_system_variables`, tham số `fill_missing_only`) — nghĩa là FVB (`linked_doctype_field`) đã là đường chính, module này chỉ là lưới an toàn cho biến FVB chưa phủ tới.

**Phần còn dư thừa thật:** 2 khả năng module này có mà FB's `linked_doctype_field` không có:
- **Auto-discover link field** theo tên doctype đích (không cần khai `link_field` tường minh mỗi binding).
- **Priority override qua child table** (child row > linked field > default) — đây chính là pattern `fallback_chain` (đã có trong core!) CÓ THỂ làm được, nếu core có thêm 1 source type đọc "1 dòng trong child table theo key" (hiện `child_table_aggregate` chỉ AGGREGATE — sum/avg/count — không có mode "lookup 1 giá trị theo key field", xem mục 2.2).

→ **Ưu tiên thấp** — hệ thống hiện tại đã chạy đúng, đây là dọn nợ kiến trúc dài hạn, không phải bug. Chỉ đáng làm SAU khi core có `child_table_lookup` (mục 2.2), lúc đó có thể thay `system_variable_resolver` bằng N binding `fallback_chain` (mỗi link: `child_table_lookup` trên `system_variables` → `linked_doctype_field` → `constant` default) — xoá hẳn module Python riêng.

### 1.3 Việc đã kiểm tra — KHÔNG dư thừa (để tránh bạn tưởng nhầm)

| Chỗ | Vì sao KHÔNG phải dư thừa |
|---|---|
| `engine/composite_pricing.py` + `fb_handlers.py::aluminum_price_composite` | Đây LÀ cách "tận dụng FB" — đăng ký đúng contract, được FVB seed tự động chạy production. Không cần đổi sang `composite_key_lookup` built-in vì đã gói sẵn 2-mode nghiệp vụ mà generic source type chưa có. |
| `al_formula_rules/.../al_dynamic_item_rule.py` | Vòng lặp Python thuần trên `frappe.get_cached_doc` — không phải N+1, không phải "chưa qua FB gây chậm". Việc đưa qua `range_lookup` (core mới) là lựa chọn kiến trúc, không phải sửa lỗi. |
| `al_bom_engine/doctype/configsnapshot/` | Đây là 1 doctype nghiệp vụ (lưu snapshot khi submit báo giá) với `autoname()` sinh mã có ý nghĩa — không liên quan đến `EnterpriseSnapshot` (hệ audit/hash 5-layer của FB dùng cho trace tính toán). 2 khái niệm "snapshot" khác nhau hoàn toàn, không trùng lặp. |
| `glass_group_resolver.py` / `color_group_resolver.py` (24-35 dòng) | Business logic thuần nhôm-kính (nhóm các dòng BOM theo mã kính/màu đại diện) — không có capability generic tương ứng nào trong FB, đúng chỗ (thuộc alumglass). |
| Patches `v28_11/migrate_cost_bucket_aggregate_to_aggregate_from_items.py` | Bằng chứng đội ngũ ĐÃ chủ động dọn dư thừa trước đây (cost bucket viết tay → `aggregate_from_items` built-in). Không còn việc gì để làm ở đây. |

---

## 2. formula_builder core — 2 năng lực generic thật sự nên thêm

### 2.1 `db_function_library` (hoặc tên tương đương) — ưu tiên CAO

**Vấn đề:** FB có 80+ hàm built-in (`BASE_FUNCS`), nhưng thêm hàm mới đòi hỏi **sửa code + `bench migrate`** (README mục 17: *"Adding a New Built-in Function: 1. Implement... 2. Add to BASE_FUNCS... 4. Run bench migrate"*). Không có cơ chế để **admin tự định nghĩa hàm tuỳ biến qua DB**, dùng được trực tiếp trong formula string như 1 hàm bình thường (`MY_FUNC(a, b, c)`).

**Bằng chứng nhu cầu có thật:** alumglass đã tự xây `lookup_calc_pattern` (mục 1.1) đúng để giải quyết chính xác vấn đề này — và làm đúng cách (tái dùng `compile_expression`/`safe_eval` của FB) nhưng phải tự viết registry, cache, validator riêng vì core không có sẵn.

**Đề xuất thiết kế** (không phải doctype mới nếu tránh được — có thể dùng lại `Formula Set` + `Formula Set Line` đã có, chỉ cần 1 lớp gọi mới):

- Thêm 1 built-in function mới vào `BASE_FUNCS` tên `CALL_NAMED(set_code, *args)` hoặc tương tự, resolve như sau:
  1. Cache dương/âm theo `set_code` (giống `_DB_PATTERN_CACHE`/`_NEGATIVE_CACHE` alumglass đã làm — chuyển nguyên logic này vào core).
  2. Đọc `Formula Set` theo `set_code`, lấy `formulas[0].formula` làm biểu thức (hoặc thêm 1 field `positional_args: "w,h,tlr"` trên `Formula Set` để map đối số theo vị trí vào scope).
  3. Compile bằng `compile_expression` (đã có), cache compiled expression.
  4. Không có `Formula Set` nào khớp → fallback lỗi rõ ràng (không silent).
- Việc này **generic 100%** — bất kỳ ngành nào cần "công thức tuỳ biến gọi được từ formula khác" đều dùng được, không cần biết gì về nhôm kính.
- **Lợi ích phụ:** khi có cái này, `AL Quantity Calc Method` (doctype riêng của alumglass) có thể cân nhắc thay bằng `Formula Set` chuẩn của FB — giảm 1 doctype, 1 UI riêng cần bảo trì.

### 2.2 `child_table_lookup` — ưu tiên TRUNG BÌNH

**Vấn đề:** `child_table_aggregate` (built-in có sẵn) chỉ hỗ trợ **aggregate** (sum/avg/min/max/count/list) — không có mode "tra đúng 1 dòng theo key, trả field khác". Đây là pattern rất phổ biến: "bảng override cấu hình theo key" (VD `AL Profile System.system_variables`: mỗi dòng có `variable` + `value`, cần tra theo `variable` → trả `value`).

**Đề xuất:** thêm `mode: "lookup"` vào `child_table_aggregate` (không cần source type mới hoàn toàn — chỉ mở rộng config_schema hiện có), hoặc source type riêng `child_table_lookup` nếu muốn tách bạch:
```json
{
  "child_table_field": "system_variables",
  "key_field": "variable",
  "key_value": "{{binding.variable_name}}",
  "value_field": "value",
  "filter_active_field": "is_active"
}
```
Kết hợp với `fallback_chain` đã có sẵn → thay được hoàn toàn pattern "child override > linked field > default" mà `system_variable_resolver.py` (mục 1.2) đang tự viết tay.

### 2.3 Việc đã kiểm tra — core KHÔNG thiếu (để tránh làm lại)

| Nghĩ là thiếu | Thực tế |
|---|---|
| `composite_key_lookup` | Đã có, đủ dùng (mục 2 file trước). |
| `matrix_lookup`, `aggregate_from_items`, `pipeline`, `conditional`, `fallback_chain`, `reuse_formula_result` | Đã có, đủ dùng. |
| `range_lookup` (tra theo khoảng số) | Xác nhận thiếu thật — đã có code cụ thể ở file triển khai trước, giữ nguyên đề xuất đó. |

---

## 3. Tổng hợp việc nên làm (bổ sung vào backlog, không thay thế các mục trước)

| # | Việc | Vị trí | Ưu tiên | Ghi chú |
|---|---|---|---|---|
| A | Thêm `CALL_NAMED`/tương đương — DB-defined function library | `formula_builder` core (`formula_utils/funcs/` + `data_source_registry.py` hoặc built-in function mới) | 🟠 Trung bình-cao | Giá trị dài hạn lớn nhất — giải quyết đúng nhu cầu alumglass đã tự chứng minh bằng `lookup_calc_pattern` |
| B | Migrate `lookup_calc_pattern` → gọi core (A) | `alumglass/formula_handlers.py` | 🟢 Sau khi A xong | Xoá `_validate_calc_fn`, `_DB_PATTERN_CACHE` tay |
| C | Thêm mode `lookup` cho `child_table_aggregate` (hoặc `child_table_lookup` mới) | `formula_builder` core | 🟢 Thấp | Không khẩn cấp, hệ hiện tại chạy đúng |
| D | Migrate `system_variable_resolver` → `fallback_chain` + (C) | `alumglass/al_bom_engine/system_variable_resolver.py` | 🟢 Sau khi C xong | Không khẩn cấp |

Không có việc nào ở mức 🔴 khẩn cấp trong audit này — khác với việc sửa N+1 ở file triển khai trước (vẫn là ưu tiên cao nhất, không đổi).

=============================================
