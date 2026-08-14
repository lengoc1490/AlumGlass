# Patch: Composite Key Pricing trong BomOrchestrator

## Vấn đề
`BomOrchestrator.b2_prefetch_master_data()` tra Item Price chỉ theo
`(item_code, price_list)`, bỏ qua các custom field composite key
(`custom_pd_MAU_SAC`, `custom_pd_XUAT_XU`...) do `AL Pricing Dimension` tự
sinh ra. Hệ quả:
1. Đổi màu/xuất xứ/độ dày/bề mặt không làm đổi giá.
2. Nếu 1 `item_code` có nhiều dòng Item Price, `dict` bị ghi đè bởi dòng cuối
   DB trả về → giá không xác định (non-deterministic) giữa các lần chạy.

## Cách áp dụng
Trong file `alumglass/engine/bom_orchestrator.py`:

### 1. Thêm cache field vào `__init__`

```python
def __init__(self, quotation_item_name):
    ...
    self._dim_fieldname_cache = None   # <-- THÊM DÒNG NÀY
```

### 2. Thay thế đoạn "Batch query #2: Item Prices" trong `b2_prefetch_master_data`

**XÓA đoạn code cũ:**
```python
        # ── Batch query #2: Item Prices ──────────────────────────────
        prices = {}
        all_price_items = list(set(item_codes + price_base_items))
        if all_price_items:
            for ip in frappe.get_all("Item Price",
                                      filters={"item_code": ("in", all_price_items),
                                               "price_list": "Standard Selling"},
                                      fields=["item_code", "price_list_rate"]):
                prices[ip["item_code"]] = ip["price_list_rate"]
```

**THAY BẰNG:**
```python
        # ── Batch query #2: Item Prices (composite-key aware) ────────
        # Lưu ý: 1 item_code có thể có NHIỀU dòng Item Price (khác màu/
        # xuất xứ/độ dày/bề mặt) — phải match đúng theo composite key
        # hiện tại (self.inputs), không được ghi đè tùy tiện theo thứ tự DB.
        all_price_items = list(set(item_codes + price_base_items))
        prices = self._fetch_composite_prices(all_price_items)
```

### 3. Thêm 2 method mới vào class `BomOrchestrator` (đặt ngay sau `b2_prefetch_master_data`)

```python
    def _get_dim_fieldnames(self):
        """Map variable_name -> custom_fieldname trên Item Price.

        Đọc từ AL Variable Dimension Mapping + AL Pricing Dimension
        (data-driven, giống hệt logic trong fb_handlers.aluminum_price_composite
        nhưng batch 1 lần cho toàn bộ B2 thay vì gọi lại mỗi dòng BOM).
        """
        if self._dim_fieldname_cache is not None:
            return self._dim_fieldname_cache

        mappings = frappe.get_all(
            "AL Variable Dimension Mapping",
            fields=["variable_name", "pricing_dimension"])
        dim_codes = list({m["pricing_dimension"] for m in mappings})
        dims = {}
        if dim_codes:
            for d in frappe.get_all(
                "AL Pricing Dimension",
                filters={"name": ("in", dim_codes)},
                fields=["name", "custom_fieldname"]):
                dims[d["name"]] = d["custom_fieldname"]

        self._dim_fieldname_cache = {
            m["variable_name"]: dims.get(m["pricing_dimension"])
            for m in mappings if dims.get(m["pricing_dimension"])
        }
        return self._dim_fieldname_cache

    def _fetch_composite_prices(self, item_codes):
        """Tra Item Price theo composite key, trả về {item_code: price_list_rate}.

        Với mỗi item_code, chọn dòng Item Price khớp NHIỀU field composite
        nhất với self.inputs hiện tại (đã có từ B1 — gather_inputs chạy
        trước B2 trong flow run()). Nếu không dòng nào khớp đủ, fallback về
        dòng "trần" (không set field composite nào) làm giá mặc định.
        """
        if not item_codes:
            return {}

        dim_fieldnames = self._get_dim_fieldnames()
        price_fields = ["name", "item_code", "price_list_rate"] + list(
            set(dim_fieldnames.values()))

        rows_by_item = defaultdict(list)
        for ip in frappe.get_all(
            "Item Price",
            filters={"item_code": ("in", item_codes),
                     "price_list": "Standard Selling"},
            fields=price_fields,
        ):
            rows_by_item[ip["item_code"]].append(ip)

        prices = {}
        for item_code, rows in rows_by_item.items():
            prices[item_code] = self._match_composite_price(
                item_code, rows, dim_fieldnames)
        return prices

    def _match_composite_price(self, item_code, rows, dim_fieldnames):
        if len(rows) == 1:
            return rows[0]["price_list_rate"]

        best_row, best_score = None, -1
        for row in rows:
            score, mismatch = 0, False
            for var_name, fieldname in dim_fieldnames.items():
                row_val = row.get(fieldname)
                if not row_val:
                    continue  # dòng không set field này -> bỏ qua, không loại
                if str(row_val) == str(self.inputs.get(var_name, "")):
                    score += 1
                else:
                    mismatch = True
                    break
            if mismatch:
                continue
            if score > best_score:
                best_score, best_row = score, row

        if best_row:
            return best_row["price_list_rate"]

        # Fallback: dòng không set field composite nào (giá mặc định)
        for row in rows:
            if all(not row.get(fn) for fn in dim_fieldnames.values()):
                return row["price_list_rate"]

        frappe.throw(
            f"Không tìm được Item Price khớp cho '{item_code}' với composite "
            f"key hiện tại. Kiểm tra lại bảng giá (Item Price) hoặc thêm 1 "
            f"dòng giá mặc định không gắn dimension nào."
        )
```

## Vì sao patch này khớp với kiến trúc hiện có
- Không cần gọi lại `fb_handlers.aluminum_price_composite()` qua FB
  `BatchBindingResolver` (tránh N lần gọi riêng cho từng dòng BOM) — patch
  này giữ đúng tinh thần "batch query 1 lần" đã có trong B2 (giống cách
  `weights`, `glass_masters`, `material_categories` đang được gộp).
- Vẫn 100% data-driven: không hardcode `custom_color`/`aluminum_color` — đọc
  từ `AL Variable Dimension Mapping` + `AL Pricing Dimension.custom_fieldname`
  đúng như thiết kế "Accounting Dimension-style" đã có.
- Không phá `multiplier_chain` mode: patch này chỉ thay `exact_match`
  (mode mặc định, đang dùng trong `bom_orchestrator`). Nếu muốn hỗ trợ cả
  `multiplier_chain` trong orchestrator, cần đọc thêm `source_config` của
  binding — có thể làm ở version sau khi mode này thực sự cần dùng.

## Sau khi patch — chạy lại để xác nhận
```bash
bench --site <site> run-tests --app alumglass \
    --module alumglass.tests.test_composite_pricing
# Cả 2 test phải PASS: test_same_item_different_color_yields_different_price
# và test_price_lookup_is_deterministic
```

Đồng thời chạy lại `run_test.py` để đảm bảo `GIA_VAT ≈ 22,717,289 VND` vẫn
đúng (patch này không đổi kết quả cho case chỉ có 1 dòng Item Price/item_code
— vì `len(rows) == 1` trả thẳng, không đổi hành vi cũ cho các item không có
composite key).
