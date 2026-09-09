# BẢN FULL A-Z — Triển khai toàn diện alumglass ↔ formula_builder

> Đây là bản **hợp nhất cuối cùng**, thay thế TOÀN BỘ các file trước đó trong quá trình review (`ke-hoach-trien-khai...`, `trien-khai-chi-tiet-...`, `audit-du-thua-...`, `trien-khai-chi-tiet-BAN-CUOI.md`, `sua-toan-dien-BAN-CUOI-2.md`, `dinh-chinh-PHU_KIEN.md`). Nếu có mâu thuẫn giữa file này và các file cũ, **file này đúng** (đã sửa mọi sai sót phát hiện được qua nhiều vòng đọc code thật). Đi kèm file này là `tai-lieu-thay-doi-va-nguyen-tac-FB.md` (changelog + nguyên tắc).

**Phạm vi 2 repo:** `lengoc1490/AlumGlass` (app ngành), `lengoc1490/Formula-Builder` (platform dùng chung, `develop` branch) — đã clone và đọc trực tiếp source, không dựa vào tài liệu/README (README của FB đã lỗi thời so với code thật).

---

## MỤC LỤC

- **PHẦN A** — Nguyên tắc chỉ đạo & phân loại hardcode
- **PHẦN B** — Fix N+1 composite pricing *(repo alumglass)*
- **PHẦN C** — Hardcode `"KINH"` (3 chỗ) *(repo alumglass)*
- **PHẦN D** — Hardcode `"MAU_SAC"` *(repo alumglass)*
- **PHẦN E** — Hardcode `"PHU_KIEN"` — qua Formula Variable Binding *(repo alumglass, dùng cơ chế FB)*
- **PHẦN F** — `range_lookup` — source type mới *(repo formula_builder)*
- **PHẦN G** — `linked_doctype_field` — mở rộng auto-discover *(repo formula_builder)*
- **PHẦN H** — `child_table_lookup` — source type mới *(repo formula_builder)*
- **PHẦN I** — Việc CHỦ ĐỘNG KHÔNG làm (và vì sao)
- **PHẦN J** — Thứ tự triển khai, phụ thuộc, rollout
- **PHẦN K** — Checklist test tổng hợp
- **PHẦN L** — Việc cần bạn xác nhận trước khi deploy

---

# PHẦN A — Nguyên tắc chỉ đạo & phân loại hardcode

### A.1 Nguyên tắc "tận dụng tối đa formula_builder"

`formula_builder` là platform dùng chung nhiều ngành. Phép thử cho mọi capability: **"ngành khác có cần y hệt cơ chế này không, chỉ khác data?"** — nếu có, thuộc core `formula_builder`; nếu không, thuộc `alumglass`.

### A.2 Phân loại hardcode — QUAN TRỌNG, quyết định cách sửa

| Loại | Ví dụ | Cách sửa đúng |
|---|---|---|
| **Property lặp lại trên NHIỀU record** — dùng để lọc SQL | `requires_glass_master`, `represents_color` | **Check field trên doctype** — đúng chuẩn, KHÔNG phải hardcode xấu, nhất quán với 6 field Check khác đã có sẵn trên `AL Material Category`. |
| **Con trỏ tới ĐÚNG 1 record cho 1 mục đích cụ thể** — 1 giá trị cấu hình đơn | "category đại diện phụ kiện" | **Formula Variable Binding (`source_type=constant`)** — dùng đúng cơ chế lõi FB, admin sửa qua UI có sẵn, không cần deploy lại. |
| **Năng lực tính toán/tra cứu generic, không đặc thù ngành** | tra khoảng số, tra 1 dòng child table theo key, auto-discover link field | **Source type mới hoặc mở rộng handler trong `formula_builder` core** |

Nhầm loại 1↔2 là lỗi tôi đã mắc phải với `PHU_KIEN` ở vòng review trước — đã sửa trong PHẦN E.

---

# PHẦN B — Fix N+1 composite pricing

**File:** `alumglass/engine/bom_orchestrator.py`

### Vấn đề
`_fetch_composite_prices_via_fb` gọi `resolve_all_bindings_batch` theo TỪNG `item_code` (M lần) → handler `aluminum_price_composite` tự query lại `AL Variable Dimension Mapping` + `Item Price` mỗi lần → 2×M query thay vì 2 query tổng.

**Rủi ro đã xử lý:** 2 nhánh khác hành vi ở case "không tìm được giá khớp" — `fb_handlers.aluminum_price_composite` trả `0`, còn `_match_composite_price` (fallback) mặc định `throw`. Đã vá bằng tham số `allow_missing`.

**Phát hiện thêm:** `_fetch_composite_prices` cũ chỉ loop qua `item_code` CÓ dòng Item Price (`rows_by_item.items()`) — item 0 dòng bị THIẾU hẳn khỏi kết quả (không phải throw, không phải 0). Đã sửa loop qua toàn bộ `item_codes` được yêu cầu.

### B.1 — Thay thế hàm `_fetch_composite_prices_via_fb` (dòng ~1095-1158)

```python
def _fetch_composite_prices_via_fb(self, item_codes):
    """B2 FB-max: resolve composite price — batch 1 lần cho TẤT CẢ item_codes.

    FIX N+1 (2026-09): bản cũ gọi resolve_all_bindings_batch theo TỪNG
    item_code (M lần) → 2×M query. resolve_all_bindings_batch không có API
    multi-row, nên sửa tại đây: đọc CONFIG (price_list, pricing_mode) từ
    binding đúng 1 lần, rồi tái dùng _fetch_composite_prices(allow_missing=True)
    — đã cache mapping ở self._dim_mapping_raw_cache, cùng thuật toán
    best_partial_match với fb_handlers.

    allow_missing=True bắt buộc — 2 nhánh khác hành vi no-match (fb_handlers
    trả 0, fallback mặc định throw); không xử lý sẽ đổi hành vi ngầm.

    Chỉ tối ưu N+1 cho ĐÚNG 1 binding chủ (source_type=aluminum_price_
    composite). 0 hoặc >1 binding loại này active cùng lúc → rơi về nhánh
    chậm _fetch_composite_prices_via_fb_slow (an toàn hơn đoán config nào ưu tiên).
    """
    bindings = self._get_pricing_bindings()
    if not bindings:
        return None

    fast_path_bindings = [
        b for b in bindings if b.get("source_type") == "aluminum_price_composite"
    ]
    other_bindings = [b for b in bindings if b not in fast_path_bindings]
    if len(fast_path_bindings) != 1 or other_bindings:
        return self._fetch_composite_prices_via_fb_slow(bindings, item_codes)

    import json
    cfg = json.loads(fast_path_bindings[0].get("source_config") or "{}")
    pricing_mode = cfg.get("pricing_mode", "exact_match")
    price_list = cfg.get("price_list") or _default_price_list()

    if pricing_mode == "exact_match":
        return self._fetch_composite_prices(
            item_codes, price_list=price_list, allow_missing=True)

    if pricing_mode == "multiplier_chain":
        return self._fetch_composite_prices_multiplier_chain(item_codes, price_list=price_list)

    return None


def _fetch_composite_prices_via_fb_slow(self, bindings, item_codes):
    """Đường cũ (per-item, có N+1) — CHỈ dùng cho case lạ (0/nhiều hơn 1
    binding aluminum_price_composite active, hoặc có binding khác xen vào).
    Giữ nguyên logic gốc, ưu tiên đúng behavior hơn tối ưu.
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
    frappe.get_cached_value cho multiplier (đã request-cache sẵn trong Frappe).
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
        base_price_by_item.setdefault(r["item_code"], r["price_list_rate"])

    category_by_code = self._category_by_code()
    mappings, dims_raw = self._get_dim_mappings_raw()
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

### B.2 — Thay thế `_fetch_composite_prices` + `_match_composite_price` (dòng ~1160-1238)

```python
def _fetch_composite_prices(self, item_codes, price_list=None, allow_missing=False):
    """Tra Item Price theo composite key, trả về {item_code: price_list_rate}.

    ★ LƯỚI AN TOÀN — chỉ chạy khi _fetch_composite_prices_via_fb trả None.
    Caller mặc định (allow_missing=False, price_list=None): 100% golden cũ.

    Args (MỚI): price_list — ghi đè _default_price_list(), cho phép FB-max
    truyền price_list từ binding.source_config. allow_missing — True: item
    không khớp giá (kể cả 0 dòng Item Price) trả 0 thay vì throw, khớp đúng
    hành vi fb_handlers.aluminum_price_composite.
    """
    if not item_codes:
        return {}
    price_list = price_list or _default_price_list()

    category_by_code = self._category_by_code()
    color_category_by_code = self._color_category_by_code()
    color_overrides = self._compute_color_price_overrides()

    all_fieldnames = set()
    for code in item_codes:
        fns = self._dim_fieldnames_for_category(category_by_code.get(code, ""))
        all_fieldnames |= set(fns.values())
    price_fields = ["name", "item_code", "price_list_rate"] + list(all_fieldnames)

    rows_by_item = defaultdict(list)
    for ip in frappe.get_all(
        "Item Price",
        filters={"item_code": ("in", item_codes), "price_list": price_list},
        fields=price_fields,
    ):
        rows_by_item[ip["item_code"]].append(ip)

    prices = {}
    # SỬA: loop TOÀN BỘ item_codes yêu cầu, không chỉ rows_by_item.keys() —
    # item 0 dòng Item Price trước đây bị THIẾU khỏi kết quả (không 0, không throw).
    for item_code in item_codes:
        rows = rows_by_item.get(item_code, [])
        dim_fieldnames = self._dim_fieldnames_for_category(
            category_by_code.get(item_code, ""))
        row_inputs = dict(self.inputs)
        color_var = self._color_variable_for_category(
            color_category_by_code.get(item_code, ""))
        if color_var:
            override_val = color_overrides.get((item_code, color_var))
            if override_val:
                row_inputs[color_var] = override_val
        prices[item_code] = self._match_composite_price(
            item_code, rows, dim_fieldnames, row_inputs, allow_missing=allow_missing)
    return prices


def _match_composite_price(self, item_code, rows, dim_fieldnames, inputs=None, allow_missing=False):
    """Chọn dòng Item Price khớp nhất — thuật toán thật ở engine/composite_
    pricing.best_partial_match (dùng chung với fb_handlers.aluminum_price_composite).
    allow_missing=True: trả 0 thay vì throw khi không khớp. Mặc định False =
    hành vi golden cũ.
    """
    from alumglass.engine.composite_pricing import best_partial_match

    price = best_partial_match(rows, dim_fieldnames, inputs if inputs is not None else self.inputs)
    if price is not None:
        return price
    if allow_missing:
        return 0
    frappe.throw(
        f"Không tìm được Item Price khớp cho '{item_code}' với composite "
        f"key hiện tại. Kiểm tra lại bảng giá (Item Price) hoặc thêm 1 "
        f"dòng giá mặc định không gắn dimension nào."
    )
```

---

# PHẦN C — Hardcode `"KINH"` (3 chỗ)

### C.1 — Helper dùng chung, file mới: `alumglass/al_bom_engine/glass_group_resolver.py`

Thêm vào ĐẦU file (module này hiện chưa `import frappe`):

```python
import frappe


def fetch_glass_category_codes(category_codes):
    """{category} có requires_glass_master=1 — NGUỒN DUY NHẤT nhận diện
    "category kính" (thay hardcode "KINH"). Dùng chung bom_orchestrator.py
    (2 chỗ) + api/__init__.py (glass_groups) — 3 nơi KHÔNG bao giờ lệch.
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
*(giữ nguyên hàm `glass_group_rep()` đã có sẵn bên dưới, không đổi)*

### C.2 — `alumglass/engine/bom_orchestrator.py`, `b2_prefetch_master_data` (đoạn "Batch query #4")

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
        self._glass_categories = fetch_glass_category_codes(cat_codes)   # ← THÊM
```

### C.3 — `bom_orchestrator.py` dòng 721 và 781

```python
# TRƯỚC (2 chỗ):
if (item.get("category") or "").upper() == "KINH":
# SAU:
if item.get("category") in self._glass_categories:
```

### C.4 — `alumglass/api/__init__.py` dòng 729

```python
# TRƯỚC:
    for item in bom_set.get("items", []) or []:
        if (item.get("category") or "").upper() != "KINH":
            continue

# SAU:
    from alumglass.al_bom_engine.glass_group_resolver import fetch_glass_category_codes
    _glass_cats = fetch_glass_category_codes(
        {it.get("category", "") for it in bom_set.get("items", []) or [] if it.get("category")})
    for item in bom_set.get("items", []) or []:
        if item.get("category") not in _glass_cats:
            continue
```

**Dữ liệu:** bạn đã xác nhận `"KINH"` đã bật `requires_glass_master=1` — không cần patch backfill.

---

# PHẦN D — Hardcode `"MAU_SAC"`

### D.1 — Field mới: `alumglass/al_master_data/doctype/al_pricing_dimension/al_pricing_dimension.json`

Thêm vào mảng `fields` (cạnh `is_required_for_price`/`is_active`):

```json
{
    "fieldname": "represents_color",
    "fieldtype": "Check",
    "label": "Represents Color Dimension?",
    "description": "Bật nếu dimension này đại diện cho \"màu sắc\" — engine tự nhận diện biến màu theo category (_color_variable_for_category), thay hardcode dimension_code = \"MAU_SAC\"."
}
```

### D.2 — Patch: `alumglass/patches/v28_12/set_represents_color_flag.py`

*(version `v28_12` — xác nhận qua `alumglass/patches.txt`, không phải `v29_XX` như bản nháp đầu ghi sai)*

```python
import frappe


def execute():
    """Backfill represents_color=1 cho dimension MAU_SAC hiện có."""
    if frappe.db.exists("AL Pricing Dimension", "MAU_SAC"):
        frappe.db.set_value("AL Pricing Dimension", "MAU_SAC", "represents_color", 1)
```

Thêm vào `alumglass/patches.txt` (khối `[post_model_sync]`, sau dòng `v28_11.rebackfill_cost_template_pre_vat_price`):
```
alumglass.patches.v28_12.set_represents_color_flag
```

### D.3 — `bom_orchestrator.py`, hàm `_color_variable_for_category` (dòng ~1295-1309)

```python
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
            "AL Pricing Dimension", filters={"represents_color": 1}, fields=["name"])
    }
    self._color_dim_codes_cache = codes
    return codes
```

---

# PHẦN E — Hardcode `"PHU_KIEN"` — qua Formula Variable Binding

> **Đây là hardcode loại 2** (con trỏ tới 1 record cho 1 mục đích, KHÔNG phải property lặp lại) — xác nhận qua truy vết: `color_group_category="PHU_KIEN"` được `_color_category_by_code()` đưa vào `_color_variable_for_category()`, hàm này **query thật** `AL Variable Dimension Mapping.material_category`. Sửa bằng Formula Variable Binding, KHÔNG thêm field mới — đúng tinh thần "tận dụng tối đa FB".

**Phát hiện dữ liệu:** `seed_demo_data.py` seed category phụ kiện tên `"PK"`, khác hardcode hiện tại `"PHU_KIEN"` — **cần bạn xác nhận tên thật trong production** trước khi seed (mục L).

### E.1 — Module mới: `alumglass/al_bom_engine/fb_config.py`

```python
"""Đọc "named constant" (1 giá trị cấu hình đặt tên) qua Formula Variable
Binding — cơ chế DUY NHẤT dùng cho MỌI nhu cầu "chọn 1 giá trị cho 1 mục đích
cụ thể" (khác Check field — dành cho property lặp lại trên nhiều record).
Admin cấu hình qua UI Formula Variable Binding sẵn có — sửa được ngay, không
cần bench migrate, không cần thêm field/doctype mới cho mỗi nhu cầu phát sinh.
"""
import frappe


def get_named_constant(variable_name, default=None):
    """Đọc giá trị 1 Formula Variable Binding (thường source_type="constant")
    theo tên biến. Cache theo request (frappe.local).

    Args:
        variable_name: tên binding cần đọc (vd "DEFAULT_ACCESSORY_CATEGORY").
        default: giá trị trả về nếu binding không tồn tại/inactive/lỗi —
            KHÔNG default ngầm 1 chuỗi đoán mò trong code.
    """
    cache = getattr(frappe.local, "_al_named_constant_cache", None)
    if cache is None:
        cache = {}
        frappe.local._al_named_constant_cache = cache
    if variable_name in cache:
        return cache[variable_name]

    rows = frappe.get_all(
        "Formula Variable Binding",
        filters={"variable_name": variable_name, "is_active": 1},
        fields=["source_type", "source_config", "data_type"],
        limit=1,
    )
    if not rows:
        frappe.log_error(
            f"get_named_constant: chưa có Formula Variable Binding active "
            f"tên '{variable_name}' — dùng default={default!r}. Tạo binding "
            f"qua UI Formula Variable Binding (source_type=constant).",
            "fb_config: named constant missing",
        )
        cache[variable_name] = default
        return default

    binding = dict(rows[0], variable_name=variable_name)
    try:
        from formula_builder.api.batch_binding_resolver import resolve_all_bindings_batch
        resolved = resolve_all_bindings_batch([binding], doc=None, pre_resolved={})
        value = resolved.get(variable_name, default)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"get_named_constant({variable_name})")
        value = default

    cache[variable_name] = value
    return value
```

### E.2 — Seed idempotent, thêm vào cuối `alumglass/setup/install_fb_bindings.py` (không đổi phần `COMPOSITE_PRICING_BINDING` đã có)

```python
DEFAULT_ACCESSORY_CATEGORY_BINDING = {
    "variable_name": "DEFAULT_ACCESSORY_CATEGORY",
    "variable_label": "Category đại diện cho phụ kiện (AL Accessory Item)",
    "source_type": "constant",
    "source_config": {
        # ⚠️ SEED LẦN ĐẦU — XÁC NHẬN ĐÚNG TÊN CATEGORY THẬT TRONG PRODUCTION
        # trước khi merge (seed demo dùng "PK", hardcode cũ dùng "PHU_KIEN").
        # Sau khi seed, admin sửa trực tiếp qua UI Formula Variable Binding
        # nếu seed sai — KHÔNG cần sửa code.
        "value": "PK",
    },
    "applies_to_doctype": "",
    "is_global": 1,
    "is_active": 1,
    "resolve_priority": 100,
    "data_type": "Data",
    "default_value": "",
}


def install_named_constant_bindings():
    """Idempotent — seed Formula Variable Binding dạng "named constant" nếu
    CHƯA TỒN TẠI. Khác install_composite_pricing_binding(): KHÔNG ép cấu
    hình lại nếu admin đã sửa qua UI (chỉ tạo lần đầu nếu thiếu).
    """
    if not frappe.db.exists("DocType", "Formula Variable Binding"):
        return
    import json
    for payload in (DEFAULT_ACCESSORY_CATEGORY_BINDING,):
        existing = frappe.db.exists(
            "Formula Variable Binding", {"variable_name": payload["variable_name"]})
        if existing:
            continue
        doc = frappe.new_doc("Formula Variable Binding")
        doc.update(dict(payload, source_config=json.dumps(payload["source_config"])))
        doc.insert(ignore_permissions=True)
```

### E.3 — `alumglass/hooks.py` — wire vào cả `_after_install` và `_after_migrate`

```python
    from alumglass.setup.install_fb_bindings import install_composite_pricing_binding
    from alumglass.setup.install_fb_bindings import install_named_constant_bindings   # ← THÊM
    ...
    install_composite_pricing_binding()
    install_named_constant_bindings()   # ← THÊM (cả 2 hàm _after_install và _after_migrate)
```

### E.4 — `alumglass/engine/bom_orchestrator.py`, hàm `_load_accessories`

```python
        from alumglass.al_bom_engine.fb_config import get_named_constant
        accessory_color_group_category = get_named_constant("DEFAULT_ACCESSORY_CATEGORY", default="")
        # ← Resolve 1 LẦN trước vòng lặp (không phải per-accessory-row).

        for acc in (acc_doc.get("items") or []):
            ...
            self.bom_items.append({
                ...
                "color_group_category": accessory_color_group_category,   # trước: "PHU_KIEN"
                ...
            })
```

### E.5 — `alumglass/api/__init__.py` (dòng ~805-813)

```python
    if bom_set.get("default_accessory_set"):
        from alumglass.al_bom_engine.fb_config import get_named_constant
        accessory_category_code = get_named_constant("DEFAULT_ACCESSORY_CATEGORY", default="")
        try:
            acc_doc = frappe.get_cached_doc("AL Accessory Set", bom_set.default_accessory_set)
            for acc_item in (acc_doc.get("items") or []):
                _add_color_group(acc_item, accessory_category_code, _("Phụ kiện"))
        except frappe.DoesNotExistError:
            pass
```

---

# PHẦN F — `range_lookup` — source type mới (repo `formula_builder`)

**Gap xác nhận:** `grep -in "range_lookup\|threshold\|bracket" data_source_registry.py` → 0 kết quả. Tổng quát hoá `AL Dynamic Item Rule` (THRESHOLD mode).

### F.1 — File: `formula_builder/api/data_source_registry.py` — chèn sau khối `composite_key_lookup`

```python
# ═══════════════════════════════════════════════════════════════════════════
# range_lookup — tra giá trị theo khoảng số (from-to → result)
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_range_rows(cfg):
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
        "mọi ngành cần phân bậc theo ngưỡng số. Tổng quát hoá AL Dynamic Item "
        "Rule (THRESHOLD mode) — data vẫn nằm ở doctype ngành, chỉ engine dùng chung."
    ),
    config_schema={
        "type": "object",
        "required": ["doctype", "value_field", "input_value", "range_from_field", "range_to_field"],
        "properties": {
            "doctype": {"type": "string"},
            "value_field": {"type": "string"},
            "input_value": {"type": "string", "description": "Hỗ trợ template {{row.x}}/{{doc.x}}/{{resolved.x}}"},
            "range_from_field": {"type": "string", "description": "Cận dưới (inclusive)"},
            "range_to_field": {"type": "string", "description": "Cận trên (inclusive)"},
            "filters": {"type": "array"},
            "default_value": {"type": ["number", "string"]},
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
    """Fetch rows 1 lần/group (cùng doctype+filters — xem fingerprint_fn),
    resolve từng binding. CHỈ an toàn khi các binding trong cùng group thật
    sự cùng (doctype, filters) — nếu mở rộng logic gom nhóm sau này, giữ
    đúng ràng buộc này (đọc cfg0 của binding ĐẦU rồi áp cho cả nhóm)."""
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

### F.2 — Docs: `formula_builder/docs/range_lookup.md`

Theo mẫu `composite_key_lookup.md`: mô tả, config_schema, ví dụ JSON thật (ngưỡng độ dày kính → mã nẹp, bài toán `RULE-NEP-GLASSTHICK`), lưu ý inclusive cả 2 đầu, lưu ý `filters` không bắt buộc nhưng NÊN có (thiếu → `get_all` toàn bộ doctype mỗi lần resolve).

### F.3 — Test: `formula_builder/tests/test_range_lookup.py`

- [ ] Khớp giữa khoảng; khớp biên (`val == from`, `val == to`); không khớp → `default_value`.
- [ ] Template `input_value` dạng `{{row.glass_thick}}`.
- [ ] `resolve_batch`: 2 binding cùng (doctype, filters) → 1 lần `frappe.get_all` (mock đếm call count).
- [ ] Đăng ký cả central registry lẫn legacy dict (`get_handler("range_lookup")` trả callable).
- [ ] `config_schema` validate: thiếu `range_from_field` → lỗi.

Chạy: `python -m unittest formula_builder.tests.test_platform_source_types formula_builder.tests.test_config_io formula_builder.tests.test_fb1_revised formula_builder.tests.test_range_lookup`.

**⚠️ Blast radius:** `formula_builder` là app dùng chung — additive nhưng vẫn chạy **toàn bộ suite FB** trước khi merge. Tự kiểm tra `bench list-apps` trên site thật để biết app nào khác đang phụ thuộc `formula_builder`, đừng tin bất kỳ tên app cụ thể nào chưa tự xác minh.

---

# PHẦN G — `linked_doctype_field` — mở rộng auto-discover (repo `formula_builder`)

**Vấn đề:** handler hiện tại đã auto-suy-ra `target_doctype` TỪ `link_field` (`dt = target_doctype or meta.get_field(link_field).options`), nhưng **chiều ngược lại chưa có**: bỏ trống `link_field`, tự dò field Link nào trên `doc` trỏ tới `target_doctype` cho sẵn — đúng cái `alumglass.al_bom_engine.system_variable_resolver.resolve_source_link_fields` đang tự viết tay.

### G.1 — File: `formula_builder/api/data_source_registry.py`, sửa `_handle_linked_doctype_field` (dòng ~279-307) + hàm batch tương ứng (dòng ~310-345)

```python
@register_source("linked_doctype_field")
@batchable(fingerprint_fn=lambda cfg: "linked:" + cfg.get("target_doctype", "") + ":" + cfg.get("target_field", ""))
def _handle_linked_doctype_field(binding: dict, doc, resolved_so_far: dict) -> Any:
    cfg = json.loads(binding.get("source_config") or "{}")
    link_field = cfg.get("link_field", "")
    target_doctype = cfg.get("target_doctype", "")
    target_field = cfg.get("target_field", "")
    fallback = cfg.get("fallback")

    if not doc or not target_field:
        return fallback

    # MỞ RỘNG: link_field bỏ trống + có target_doctype → tự dò field Link
    # trên doc.doctype trỏ tới target_doctype (chiều ngược auto-discovery đã
    # có). Generic, không đặc thù ngành — tổng quát hoá alumglass.system_
    # variable_resolver.resolve_source_link_fields.
    if not link_field:
        if not target_doctype:
            return fallback
        link_field = _auto_discover_link_field(doc.doctype, target_doctype)
        if not link_field:
            return fallback

    linked_name = doc.get(link_field)
    if not linked_name:
        return fallback

    dt = target_doctype or frappe.get_meta(doc.doctype).get_field(link_field).options
    if not dt:
        return fallback

    try:
        val = frappe.db.get_value(dt, linked_name, target_field)
        return val if val is not None else fallback
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"DataSource: linked_doctype_field ({binding.get('variable_name')})")
        return fallback


def _auto_discover_link_field(source_doctype, target_doctype):
    """Fieldname của field Link ĐẦU TIÊN (theo thứ tự khai báo) trên
    source_doctype trỏ tới target_doctype. None nếu không có field khớp.
    frappe.get_meta đã tự cache — không cần cache thêm ở đây."""
    meta = frappe.get_meta(source_doctype)
    for f in meta.get("fields", []):
        if f.fieldtype == "Link" and f.options == target_doctype:
            return f.fieldname
    return None
```

*(áp dụng đúng thay đổi tương tự — thêm nhánh `if not link_field: link_field = _auto_discover_link_field(...)` — vào hàm `resolve_batch` tương ứng, để nhánh batch không lệch hành vi với nhánh đơn.)*

**Rủi ro:** nếu `source_doctype` có NHIỀU field Link cùng trỏ `target_doctype`, chỉ lấy field đầu tiên — khớp đúng hành vi `resolve_source_link_fields` gốc của alumglass (cũng lấy đầu tiên, dedup theo target).

### G.2 — Test

- [ ] 1 field Link khớp → đúng fieldname; 0 field khớp → `None`; nhiều field khớp → lấy đầu tiên theo thứ tự khai báo (test cố định thứ tự).
- [ ] `link_field` bỏ trống + `target_doctype` có → hoạt động qua auto-discovery.
- [ ] `link_field` VÀ `target_doctype` đều có (case cũ) → hành vi không đổi (golden).

---

# PHẦN H — `child_table_lookup` — source type mới (repo `formula_builder`)

**Vấn đề:** `child_table_aggregate` (có sẵn) chỉ hỗ trợ aggregate (sum/avg/count...) — không có mode "tra ĐÚNG 1 dòng theo key". Pattern phổ biến: "bảng override cấu hình theo key" (vd `AL Profile System.system_variables`).

### H.1 — File: `formula_builder/api/data_source_registry.py`

```python
def _fetch_child_table_row(cfg, doc):
    """Trả row (dict) khớp key_value trong child table, hoặc None."""
    child_field = cfg.get("child_table_field", "")
    key_field = cfg.get("key_field", "")
    if not (doc and child_field and key_field):
        return None
    key_value = cfg.get("_resolved_key_value")
    filter_active_field = cfg.get("filter_active_field")
    for row in (doc.get(child_field) or []):
        if row.get(key_field) != key_value:
            continue
        if filter_active_field and not row.get(filter_active_field):
            continue
        return row
    return None


@register_source(
    "child_table_lookup",
    label="Child Table Row Lookup",
    description=(
        "Tra ĐÚNG 1 dòng trong child table theo key, trả 1 field khác — khác "
        "child_table_aggregate (chỉ aggregate). Dùng cho pattern 'bảng "
        "override cấu hình theo key' nhúng trong doc cha."
    ),
    config_schema={
        "type": "object",
        "required": ["child_table_field", "key_field", "key_value", "value_field"],
        "properties": {
            "child_table_field": {"type": "string"},
            "key_field": {"type": "string"},
            "key_value": {"type": "string", "description": "Hỗ trợ template {{binding.variable_name}}/{{row.x}}/{{doc.x}}"},
            "value_field": {"type": "string"},
            "filter_active_field": {"type": "string"},
            "default_value": {"type": ["number", "string"]},
        },
    },
    app="formula_builder",
    batchable=True,
    fingerprint_fn=lambda cfg: "child_table_lookup:" + cfg.get("child_table_field", ""),
    supports_cache=False,   # đọc trực tiếp từ doc đã load sẵn — không có DB round-trip để cache
)
def _handle_child_table_lookup(binding, doc, resolved_so_far):
    cfg = json.loads(binding.get("source_config") or "{}")
    default_value = cfg.get("default_value", binding.get("default_value"))
    if not doc:
        return default_value
    row = _binding_row(binding, resolved_so_far)
    key_value = _resolve_template_val(cfg.get("key_value"), doc, resolved_so_far, row)
    if key_value is None or key_value == "":
        return default_value
    cfg = dict(cfg, _resolved_key_value=key_value)
    match = _fetch_child_table_row(cfg, doc)
    if match is None:
        return default_value
    return _cast(match.get(cfg.get("value_field")), binding.get("data_type") or "Data")


def _resolve_child_table_lookup_batch(bindings, doc, resolved_so_far):
    return {b["variable_name"]: _handle_child_table_lookup(b, doc, resolved_so_far) for b in bindings}


_handle_child_table_lookup.resolve_batch = _resolve_child_table_lookup_batch
```

### H.2 — Ví dụ kết hợp `fallback_chain` (đã có sẵn, không đổi) — mẫu cấu hình cho tương lai

```json
{
  "variable_name": "OFFSET_DO_NGANG",
  "source_type": "fallback_chain",
  "source_config": {
    "chain": [
      { "source_type": "child_table_lookup", "config": {
          "child_table_field": "system_variables", "key_field": "variable",
          "key_value": "OFFSET_DO_NGANG", "value_field": "value",
          "filter_active_field": "is_active" } },
      { "source_type": "linked_doctype_field", "config": {
          "target_doctype": "AL Bom Set", "target_field": "offset_crossbar" } },
      { "source_type": "constant", "config": { "value": 0 } }
    ]
  }
}
```

### H.3 — Test

- [ ] Khớp đúng 1 dòng theo key; không khớp → `default_value`; `filter_active_field` lọc đúng dòng inactive.
- [ ] Phối hợp `fallback_chain` + `child_table_lookup` + `linked_doctype_field` theo ví dụ H.2 — dừng đúng ở nguồn đầu tiên có giá trị.

---

# PHẦN I — Việc CHỦ ĐỘNG KHÔNG làm (và vì sao — tránh làm lại nhầm)

| Việc | Vì sao không làm |
|---|---|
| Migrate `aluminum_price_composite` → `composite_key_lookup` built-in | Không cần — đã cùng tồn tại, `aluminum_price_composite` gói sẵn nghiệp vụ 2-mode mà generic type chưa có. Đổi chỉ tăng rủi ro, không lợi ích rõ. |
| Sửa "rule_code collision" trong Dynamic Item Rule | **Đã sửa sẵn trong code** (`bom_orchestrator.py:731-759`, comment `# FIX (bug thật)`). |
| Coi `AL Dynamic Item Rule.resolve_item()` là bug hiệu năng | Không phải — dùng `frappe.get_cached_doc`, không N+1 thật. |
| Migrate `lookup_calc_pattern` (`formula_handlers.py`) sang core mới | Đã đính chính: `compile_expression` của FB **đã tự cache** bước compile; cache riêng của alumglass chỉ cache 1 DB-lookup đơn giản, có invalidate hook đúng. Mức độ dư thừa THẤP, không đáng đổi 1 hệ đang chạy đúng có test riêng. |
| Migrate `system_variable_resolver.py` sang `fallback_chain`+`child_table_lookup` thật (chạy production) | 2 năng lực core (PHẦN G, H) đã sẵn sàng, nhưng migrate thật cần: (1) khảo sát số lượng system variable thật (bảng `AL Variable Library is_system=1`), (2) xử lý hành vi "parse số nếu được, giữ string nếu không" hiện có mà `fallback_chain` chưa có sẵn, (3) 2 lớp fallback riêng của `bom_orchestrator` (`default_value`, `AL Calculation Rule CONSTANT`) không thuộc phạm vi module này. → Dự án riêng, làm sau. |
| Wiring `AL Dynamic Item Rule` (THRESHOLD) qua `range_lookup` production | `resolve_all_bindings_batch` chỉ nhận 1 row-context/lần gọi — Dynamic Item Rule resolve theo TỪNG dòng BOM với `rule_input` riêng → cần API multi-row ở core mới thật sự có ý nghĩa "batch". Việc riêng, không chen vào đợt này. |
| Field data-driven cho `PHU_KIEN` kiểu Check field | Đã đính chính ở PHẦN E — đây là hardcode loại 2 (con trỏ 1 record), đúng cách là Formula Variable Binding, không phải Check field. |

---

# PHẦN J — Thứ tự triển khai, phụ thuộc, rollout

```
Repo formula_builder (độc lập, làm trước hoặc song song):
  1. PHẦN F (range_lookup)       — additive, an toàn
  2. PHẦN G (linked_doctype_field mở rộng) — additive, an toàn
  3. PHẦN H (child_table_lookup) — additive, an toàn
  → Chạy full test suite FB, merge riêng, KHÔNG chung PR với alumglass.

Repo alumglass (tuần tự trong CÙNG bom_orchestrator.py — tránh conflict):
  4. PHẦN B (N+1 fix)            — 🔴 ưu tiên cao nhất, giá trị đo được ngay
  5. PHẦN C (hardcode KINH)      — dữ liệu đã sẵn sàng (bạn xác nhận requires_glass_master đã bật)
  6. PHẦN D (hardcode MAU_SAC)   — cần chạy patch v28_12 sau khi field JSON deploy
  7. PHẦN E (hardcode PHU_KIEN)  — 🔶 CẦN bạn xác nhận tên category thật trước (mục L)
```

PHẦN F/G/H không phụ thuộc B/C/D/E — làm song song được nếu có 2 người. PHẦN E phụ thuộc xác nhận dữ liệu ở mục L trước khi seed.

---

# PHẦN K — Checklist test tổng hợp

**PHẦN B (N+1):**
- [ ] Đếm `frappe.get_all` — trước tăng tuyến tính theo M item_code, sau hằng số.
- [ ] So sánh giá trị CŨ/MỚI trên data thật, cả 2 mode giá.
- [ ] Binding lạ (0/>1 `aluminum_price_composite`) → rơi đúng nhánh slow.
- [ ] No-match (`allow_missing=True`) → trả `0`, không throw — kể cả item 0 dòng Item Price.
- [ ] Caller cũ (`allow_missing=False` mặc định) → hành vi throw không đổi.
- [ ] Đặt file test tại `standalone_tests/` (KHÔNG trong `alumglass/tests/` — tránh phá suite qua `bench run-tests` os.walk).

**PHẦN C (KINH):**
- [ ] Hành vi glass_data giống hệt trước khi sửa, ở cả 3 chỗ gọi.
- [ ] Category mới bật `requires_glass_master=1` → tự nhận không cần sửa code.
- [ ] `grep -rn "upper() == .KINH.\|upper() != .KINH."` → 0 kết quả code thực thi.

**PHẦN D (MAU_SAC):**
- [ ] Golden: `_color_variable_for_category("NHOM")` trước/sau patch giống hệt.
- [ ] Dimension mới bật `represents_color=1` → tự nhận không cần sửa code.

**PHẦN E (PHU_KIEN):**
- [ ] `install_named_constant_bindings()` chạy 2 lần (idempotent) → 1 record, lần 2 không ghi đè.
- [ ] Sửa giá trị qua UI Formula Variable Binding → lần gọi tiếp theo (request mới) trả giá trị mới.
- [ ] Binding bị xoá/inactive → trả `default=""`, có `log_error`, không throw giữa lúc tính BOM.
- [ ] `grep -rn '"PHU_KIEN"' alumglass/ --include=*.py` → 0 kết quả (chỉ còn `"PK"` trong dict seed rõ ràng).

**PHẦN F/G/H (core FB):** xem checklist trong từng phần tương ứng.

---

# PHẦN L — Việc CẦN bạn xác nhận trước khi deploy

- [ ] **Bắt buộc:** tên category đại diện phụ kiện thật trong production (`"PK"`, `"PHU_KIEN"`, hay khác) — sửa `DEFAULT_ACCESSORY_CATEGORY_BINDING["source_config"]["value"]` (PHẦN E.2) trước lần seed đầu.
- [ ] Đã xác nhận trước đó, không cần hỏi lại: category `"KINH"` đã bật `requires_glass_master=1`; không có category "ẩn" nào khác cần coi là kính.
- [ ] Khuyến nghị (không bắt buộc): chạy `bench list-apps` trên site thật trước khi merge PHẦN F/G/H để biết chính xác app nào khác phụ thuộc `formula_builder`.
