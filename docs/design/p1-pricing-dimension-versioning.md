# P1 — Pricing Dimension Versioning (snapshot đóng băng cho báo giá tái lập)

> **Trạng thái:** Implemented (C2, Nhóm I quotation production-ready) · 2026-08-21
> **Job:** `2026-08-16_alumglass-sprint1-quotation`
> **Design gốc:** `P1-pricing-dimension-versioning.md` (repo root)

## Vấn đề

`AL BOM Version` đã snapshot `bom_set_snapshot` + `cost_template_snapshot` khi
publish — nhưng **Pricing Dimension** (bảng giá composite key: màu/xuất xứ/độ
dày/bề mặt → custom fieldname trên Item Price) **không được đóng băng**. Hệ
quả:

1. Sau khi version đã publish, nếu AI/user sửa `AL Pricing Dimension` hoặc
   `AL Variable Dimension Mapping` (vd đổi `custom_fieldname`, đổi
   `price_multiplier`) → cùng 1 version BOM, cùng 1 bộ input báo giá lại ra
   **giá khác** → không tái lập được báo giá đã gửi khách hàng.
2. `bom_orchestrator._get_dim_fieldnames()` query **live** mỗi lần chạy → phụ
   thuộc config hiện tại, không phải config tại thời điểm publish.

## Giải pháp

### 1. Field mới trên `AL BOM Version`

`pricing_dimension_snapshot` (`Long Text`, `read_only`, `no_copy`,
`print_hide`) — chụp **toàn bộ** 2 bảng:

```json
{
  "captured_at": "2026-08-21T...",
  "dimensions": [
    {"dimension_code": "MAU_SAC", "dimension_type": "Link", "custom_fieldname": "custom_pd_mau_sac"},
    ...
  ],
  "mappings": [
    {"variable_name": "aluminum_color", "pricing_dimension": "MAU_SAC", "price_multiplier": 1.0},
    ...
  ]
}
```

**Lệch design gốc (có ghi nhận):** design gốc đề xuất snapshot có `pricing_mode`
(trên dimensions) và `custom_fieldname` (trên mappings). Sau khi verify doctype
JSON thật:

- `AL Pricing Dimension` **KHÔNG có** field `pricing_mode` — có
  `dimension_type`, `link_doctype`, `select_options`, `custom_fieldname`.
- `AL Variable Dimension Mapping` **KHÔNG có** field `custom_fieldname` — có
  `variable_name`, `pricing_dimension`, `material_category`, `price_multiplier`.

→ Snapshot chỉ capture field **tồn tại thật** (tránh `frappe.get_all` throw).
`BomOrchestrator._get_dim_fieldnames()` tự nối `pricing_dimension →
custom_fieldname` qua bảng dimensions đã chụp — không cần `custom_fieldname`
trong mappings.

### 2. Điểm chụp snapshot

| Điểm | File | Hành vi |
|---|---|---|
| `before_insert` | `al_bom_version.py` | Chụp nếu field rỗng (mọi version mới, kể cả tạo trực tiếp Published như seed) |
| `on_update` | `al_bom_version.py` | Lưới an toàn: version **Published** mà snapshot rỗng (tạo trước patch) → chụp bù + `db_set` (set lần đầu hợp lệ, không tái kích hoạt guard) |

### 3. Immutability — mở rộng guard

`_guard_published_immutability()` giờ guard 3 snapshot:

```python
guarded = [
    ("bom_set_snapshot", "BOM Set"),
    ("cost_template_snapshot", "Cost Template"),
    ("pricing_dimension_snapshot", "Pricing Dimension"),
]
```

Sau Published, sửa bất kỳ snapshot nào → `frappe.throw`. Chỉ được đổi
`workflow_state` (Published → Retired), hoặc tạo version mới.

### 4. Engine đọc snapshot trước, live fallback

`bom_orchestrator._get_dim_fieldnames()`:

```
pricing_dimension_snapshot có nội dung
  → parse JSON → build {variable_name: custom_fieldname} từ dimensions + mappings
  → KHÔNG query live (immutable, tái lập được)
snapshot rỗng (version cũ chưa backfill)
  → FALLBACK query live (có warning log) — chỉ cho version cũ
```

Cấu trúc trả về giữ nguyên `{variable_name: custom_fieldname}` — engine
`_match_composite_price` và FB handler không đổi.

### 5. Backfill cho BOM Version cũ

**Repo `alumglass` chưa có cơ chế patches** — `patches.txt` (app root) +
`alumglass/patches/v28_9/` mới được tạo lần đầu trong job này (cùng lúc dùng
cho C5 print format patch). Patch `backfill_pricing_dimension_snapshot.py`:

- Query mọi `AL BOM Version` Published có `pricing_dimension_snapshot` rỗng.
- Build snapshot từ config **HIỆN TẠI**, đánh dấu `"backfilled": True`.
- `frappe.db.set_value(..., update_modified=False)` → không chạy `on_update`,
  không tái kích hoạt guard (field đang rỗng → set lần đầu hợp lệ).
- Idempotent: filter field rỗng, chạy lại nhiều lần không ghi đè.

**Quyết định ghi nhận (deviation từ design gốc):**

> **Backfill không thể khôi phục config quá khứ.** Dữ liệu config tại đúng thời
> điểm publish gốc không còn lưu ở đâu. Backfill dùng config **hiện tại** →
> với version cũ, nếu config đã đổi từ lúc publish, backfill **không sửa sai
> được quá khứ**, chỉ chặn sai lệch từ giờ trở đi. Với version tạo sau patch,
> snapshot là config đúng tại thời điểm tạo → tái lập chính xác.

## File thay đổi

| File | Thay đổi |
|---|---|
| `alumglass/al_bom_engine/doctype/al_bom_version/al_bom_version.json` | + field `pricing_dimension_snapshot` |
| `alumglass/al_bom_engine/doctype/al_bom_version/al_bom_version.py` | + `_snapshot_pricing_dimensions()`, `before_insert`, `on_update` safety net, mở rộng guard |
| `alumglass/engine/bom_orchestrator.py` | `_get_dim_fieldnames()` đọc snapshot trước, live fallback |
| `alumglass/patches/v28_9/backfill_pricing_dimension_snapshot.py` | Patch backfill (idempotent) |
| `patches.txt` | Đăng ký patch |
| `alumglass/tests/test_pricing_dimension_snapshot.py` | Test snapshot/guard/orchestrator |

## Test

`test_pricing_dimension_snapshot.py` — verify 3 hành vi:
1. Snapshot chụp tự động khi insert (có dimensions + mappings đầy đủ).
2. Guard chặn sửa snapshot sau Published.
3. `_get_dim_fieldnames()` đọc từ snapshot, không query live (mock chặn
   `frappe.get_all`).
