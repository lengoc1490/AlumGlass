# P1 — Pricing Dimension Versioning: Triển khai chi tiết

> Mục tiêu: khi `AL BOM Version` được Publish, đóng băng luôn cấu hình composite-key
> pricing (Pricing Dimension + Variable Dimension Mapping) tại thời điểm đó, để
> `BomOrchestrator` không bao giờ query "live" config nữa cho version đã publish.
> Vì Quotation đã Submit bị khoá bởi workflow (theo thiết kế hiện tại của bạn),
> patch này chỉ xử lý đúng 1 lỗ hổng còn lại: **giữa lúc BOM Version được Publish
> và lúc Quotation được Submit**, nếu ai đó sửa Pricing Dimension / multiplier,
> các phép tính "Tính giá" trong khoảng thời gian đó (trên các Quotation Item
> nháp) sẽ dùng config khác nhau cho cùng 1 BOM Version — vi phạm nguyên tắc
> "tái lập được" (principle #7 trong TONG_QUAN_KIEN_TRUC.md).

---

## 0. Tóm tắt thay đổi

| File | Thay đổi |
|---|---|
| `al_bom_engine/doctype/al_bom_version/al_bom_version.json` | +1 field `pricing_dimension_snapshot` |
| `al_bom_engine/doctype/al_bom_version/al_bom_version.py` | +method snapshot, mở rộng guard immutability |
| `engine/bom_orchestrator.py` | B2: đọc dimension config từ snapshot thay vì query live, fallback nếu snapshot rỗng |
| `patches.py` + `patches/v28_9/backfill_pricing_dimension_snapshot.py` | Backfill cho BOM Version cũ đã Published |
| `tests/test_pricing_dimension_snapshot.py` | Test mới |

---

## 1. Schema — `al_bom_version.json`

Thêm field ngay cạnh `cost_template_snapshot` hiện có (giữ cùng nhóm để dễ maintain):

```json
{
    "fieldname": "pricing_dimension_snapshot",
    "fieldtype": "Long Text",
    "label": "Pricing Dimension Snapshot",
    "read_only": 1,
    "no_copy": 1,
    "print_hide": 1,
    "description": "Auto-captured at publish time. Immutable — dùng để BomOrchestrator resolve composite pricing mà không phụ thuộc config Pricing Dimension hiện tại."
}
```

Chạy `bench migrate` sau khi thêm.

---

## 2. `al_bom_version.py` — snapshot + guard

```python
# al_bom_engine/doctype/al_bom_version/al_bom_version.py

import json
import frappe
from frappe.model.document import Document


class ALBOMVersion(Document):

    def validate(self):
        # ... code hiện có (bom_set_snapshot, cost_template_snapshot) ...
        self._guard_published_immutability()

    def before_submit(self):
        # Hoặc hook tương ứng chỗ bạn đang gọi _take_snapshots() hiện tại
        self._take_snapshots()
        self._snapshot_pricing_dimensions()

    # ------------------------------------------------------------------
    # NEW: Snapshot toàn bộ Pricing Dimension + Variable Dimension Mapping
    # ------------------------------------------------------------------
    def _snapshot_pricing_dimensions(self):
        """
        Chụp toàn bộ bảng — không filter theo BOM. Lý do: filter theo
        "dimension nào BOM này dùng" đòi hỏi parse hết Bom Set + Variable Set
        trước, dễ sót (VD: multiplier_chain có thể tham chiếu dimension
        không xuất hiện trực tiếp trong formula). Dữ liệu 2 bảng này rất nhỏ
        (vài chục dòng), snapshot toàn bộ an toàn hơn và rẻ.
        """
        dimensions = frappe.get_all(
            "AL Pricing Dimension",
            fields=[
                "dimension_code",
                "dimension_type",
                "custom_fieldname",
                "pricing_mode",  # exact_match | multiplier_chain, nếu field này ở đây
            ],
        )
        mappings = frappe.get_all(
            "AL Variable Dimension Mapping",
            fields=[
                "variable_name",
                "pricing_dimension",
                "custom_fieldname",
                "price_multiplier",
            ],
        )

        self.pricing_dimension_snapshot = json.dumps(
            {
                "captured_at": frappe.utils.now_datetime().isoformat(),
                "dimensions": dimensions,
                "mappings": mappings,
            },
            default=str,
        )

    # ------------------------------------------------------------------
    # MỞ RỘNG guard hiện có — thêm field mới vào danh sách bị khoá
    # ------------------------------------------------------------------
    def _guard_published_immutability(self):
        if self.get("workflow_state") != "Published" or self.is_new():
            return

        old = frappe.db.get_value(
            "AL BOM Version",
            self.name,
            [
                "bom_set_snapshot",
                "cost_template_snapshot",
                "pricing_dimension_snapshot",  # <-- thêm dòng này
            ],
            as_dict=True,
        )
        if not old:
            return

        guarded_fields = [
            "bom_set_snapshot",
            "cost_template_snapshot",
            "pricing_dimension_snapshot",
        ]
        for f in guarded_fields:
            if (self.get(f) or "") != (old.get(f) or ""):
                frappe.throw(
                    frappe._(
                        "AL BOM Version '{0}' đã Published — không thể sửa "
                        "'{1}'. Snapshot phải bất biến để đảm bảo báo giá "
                        "tái lập được."
                    ).format(self.name, f)
                )
```

> Lưu ý: nếu bạn hiện đang snapshot ở event khác (`on_submit`, hoặc 1 hàm
> `publish()` whitelist riêng thay vì `before_submit`) — chỉ cần thêm lời gọi
> `self._snapshot_pricing_dimensions()` ngay cạnh lời gọi `_take_snapshots()`
> hiện có, cùng chỗ.

---

## 3. `engine/bom_orchestrator.py` — dùng snapshot thay vì query live

Đây là phần quan trọng nhất. Hiện tại `_get_dim_fieldnames()` (thêm ở I1,
v28.8) đang query trực tiếp `AL Variable Dimension Mapping` +
`AL Pricing Dimension` mỗi lần tính BOM. Sửa để **ưu tiên đọc từ snapshot**,
fallback về query live nếu BOM Version chưa có snapshot (BOM Version cũ,
trước khi patch này chạy).

```python
# engine/bom_orchestrator.py

import json


class BomOrchestrator:

    # ... __init__, B0-B1 giữ nguyên ...

    def _get_dim_fieldnames(self):
        """
        Trả về (dimensions_list, mappings_list) cho composite pricing.
        Ưu tiên: snapshot trên BOM Version (immutable) > query live (fallback).
        """
        if self._dim_fieldname_cache is not None:
            return self._dim_fieldname_cache

        snapshot_raw = getattr(self.bom_version_doc, "pricing_dimension_snapshot", None)

        if snapshot_raw:
            try:
                data = json.loads(snapshot_raw)
                result = (data.get("dimensions", []), data.get("mappings", []))
                self._dim_fieldname_cache = result
                return result
            except (ValueError, TypeError):
                frappe.log_error(
                    title="AlumGlass: pricing_dimension_snapshot parse lỗi",
                    message=f"BOM Version: {self.bom_version_doc.name}",
                )
                # rơi xuống fallback bên dưới

        # FALLBACK — chỉ cho BOM Version cũ chưa được backfill (xem patch #4)
        frappe.logger("alumglass").warning(
            f"BOM Version {self.bom_version_doc.name} không có "
            "pricing_dimension_snapshot — dùng config Pricing Dimension "
            "LIVE (không immutable). Nên backfill hoặc re-publish."
        )
        dimensions = frappe.get_all(
            "AL Pricing Dimension",
            fields=["dimension_code", "dimension_type", "custom_fieldname", "pricing_mode"],
        )
        mappings = frappe.get_all(
            "AL Variable Dimension Mapping",
            fields=["variable_name", "pricing_dimension", "custom_fieldname", "price_multiplier"],
        )
        result = (dimensions, mappings)
        self._dim_fieldname_cache = result
        return result
```

Và trong `_fetch_composite_prices()` / `_match_composite_price()`, thay mọi
chỗ đang gọi `frappe.get_all("AL Pricing Dimension", ...)` hoặc
`frappe.get_all("AL Variable Dimension Mapping", ...)` trực tiếp bằng:

```python
dimensions, mappings = self._get_dim_fieldnames()
```

**Không đổi logic match** (`_match_composite_price()` giữ nguyên) — chỉ đổi
nguồn dữ liệu đầu vào.

---

## 4. Backfill cho BOM Version cũ (đã Published trước patch)

BOM Version cũ sẽ không có `pricing_dimension_snapshot` → engine dùng fallback
(query live, có warning log). Để đưa chúng về trạng thái immutable thật sự,
chạy patch 1 lần — **không sửa field khác, chỉ set thêm field mới** nên
không vi phạm guard (guard chỉ chặn nếu giá trị cũ khác giá trị mới của field
đã tồn tại; ở đây field đang `NULL` → set lần đầu là hợp lệ).

```python
# alumglass/patches/v28_9/backfill_pricing_dimension_snapshot.py

import json
import frappe


def execute():
    versions = frappe.get_all(
        "AL BOM Version",
        filters={
            "workflow_state": "Published",
            "pricing_dimension_snapshot": ["in", ["", None]],
        },
        pluck="name",
    )
    if not versions:
        return

    dimensions = frappe.get_all(
        "AL Pricing Dimension",
        fields=["dimension_code", "dimension_type", "custom_fieldname", "pricing_mode"],
    )
    mappings = frappe.get_all(
        "AL Variable Dimension Mapping",
        fields=["variable_name", "pricing_dimension", "custom_fieldname", "price_multiplier"],
    )
    snapshot = json.dumps(
        {
            "captured_at": frappe.utils.now_datetime().isoformat(),
            "dimensions": dimensions,
            "mappings": mappings,
            "backfilled": True,  # đánh dấu rõ đây là backfill, không phải snapshot gốc tại thời điểm publish
        },
        default=str,
    )

    for name in versions:
        frappe.db.set_value(
            "AL BOM Version", name, "pricing_dimension_snapshot", snapshot,
            update_modified=False,
        )

    frappe.db.commit()
    frappe.logger("alumglass").info(
        f"Backfilled pricing_dimension_snapshot cho {len(versions)} AL BOM Version."
    )
```

Đăng ký trong `patches.txt`:
```
alumglass.patches.v28_9.backfill_pricing_dimension_snapshot
```

> **Lưu ý quan trọng**: backfill dùng config **hiện tại** (không phải config
> tại đúng thời điểm publish gốc, vì dữ liệu đó không còn lưu ở đâu cả). Với
> các BOM Version cũ, nếu Pricing Dimension đã đổi kể từ lúc publish đến giờ,
> backfill không "sửa sai" được quá khứ — nó chỉ chặn *sai lệch từ giờ trở
> đi*. Nên ghi rõ điều này trong changelog nội bộ, tránh hiểu nhầm là dữ liệu
> cũ được "khôi phục đúng".

---

## 5. Test

```python
# tests/test_pricing_dimension_snapshot.py

import json
import frappe
from frappe.tests.utils import FrappeTestCase


class TestPricingDimensionSnapshot(FrappeTestCase):

    def test_snapshot_captured_on_publish(self):
        bv = frappe.get_doc("AL BOM Version", {"workflow_state": "Draft"})
        # ... setup/publish theo test fixture có sẵn của bạn ...
        bv.submit()  # hoặc bv.publish() tuỳ workflow action bạn dùng
        bv.reload()

        self.assertTrue(bv.pricing_dimension_snapshot)
        data = json.loads(bv.pricing_dimension_snapshot)
        self.assertIn("dimensions", data)
        self.assertIn("mappings", data)

    def test_cannot_edit_snapshot_after_publish(self):
        bv = frappe.get_last_doc(
            "AL BOM Version", filters={"workflow_state": "Published"}
        )
        bv.pricing_dimension_snapshot = json.dumps({"tampered": True})
        with self.assertRaises(frappe.ValidationError):
            bv.save()

    def test_orchestrator_uses_snapshot_not_live_config(self):
        """
        Đổi price_multiplier LIVE sau khi publish, verify BomOrchestrator
        vẫn dùng giá trị đã snapshot (không đổi kết quả tính).
        """
        # 1. Publish BOM Version với multiplier DARK=1.08 (như seed data)
        # 2. Tính BOM lần 1 → lưu kết quả A
        # 3. Đổi live: AL Color Standard DARK.price_multiplier = 1.50
        # 4. Tính BOM lần 2 (cùng BOM Version, chưa Submit Quotation)
        # 5. assertEqual(kết quả lần 2, kết quả lần 1)  # snapshot đã chặn live change
        pass  # điền theo fixture thực tế của bạn (giống test_composite_pricing.py hiện có)
```

---

## 6. Checklist áp dụng

- [ ] Thêm field `pricing_dimension_snapshot` vào JSON, `bench migrate`
- [ ] Sửa `al_bom_version.py`: thêm `_snapshot_pricing_dimensions()`, mở rộng guard
- [ ] Sửa `bom_orchestrator.py`: `_get_dim_fieldnames()` đọc snapshot trước, fallback sau
- [ ] Thêm patch backfill, chạy `bench migrate` trên site đã có data
- [ ] Thêm test, chạy `bench --site <site> run-tests --app alumglass --module alumglass.tests.test_pricing_dimension_snapshot`
- [ ] Cập nhật `CHANGELOG` (v28.9) theo đúng format bạn đang dùng — ghi rõ đây là "config-versioning fix", không phải "data migration"

---

## 7. Vì sao KHÔNG cần thêm guard chặn recalculate trên Quotation Submit

Bạn đã có workflow approval khoá Quotation sau khi chốt — đúng cơ chế
chuẩn của Frappe (`docstatus`/workflow_state) nên không cần thêm check thủ
công trong `calculate_bom()` như đề xuất trước. Patch này chỉ xử lý đúng
khoảng hở còn lại: **giữa lúc Publish BOM Version và lúc Quotation được
Submit**, đảm bảo mọi lần "Tính giá" trong khoảng đó đều dùng cùng 1 bộ
Pricing Dimension config — bất kể ai đó có sửa config đó ở nơi khác hay
không.
