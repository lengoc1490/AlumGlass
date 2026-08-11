# P2 — Async BOM Calculation: Triển khai chi tiết

> Mục tiêu: BOM > ngưỡng dòng (mặc định 150-200 dòng, config được — không
> hardcode theo đúng nguyên tắc #1 của bạn) sẽ chạy qua `frappe.enqueue()`
> thay vì đồng bộ trong request, tránh timeout khi Sales User bấm "Tính giá"
> cho công trình lớn (vách kính mặt dựng nhiều tầng). Dùng
> `frappe.publish_realtime` (socketio có sẵn trong Frappe) để đẩy kết quả về
> client — **không cần client tự poll**, UX mượt hơn và ít tải server hơn.

---

## 0. Tóm tắt thay đổi

| File | Thay đổi |
|---|---|
| ERPNext core: `Quotation Item` custom fields | +3 field: `al_calc_status`, `al_calc_job_id`, `al_calc_error` |
| `api/__init__.py` | `calculate_bom()`: quyết định sync/async theo số dòng BOM |
| `engine/bom_orchestrator.py` | Không đổi logic tính — chỉ thêm hook publish progress (tuỳ chọn) |
| `setup/custom_fields.py` | Đăng ký 3 field mới |
| `setup/seed_demo_data.py` | Thêm Global Variable `ASYNC_BOM_THRESHOLD` |
| `public/js/quotation_item_dialog.js` | Xử lý response async: hiện spinner + lắng nghe realtime event |
| `hooks.py` | Không cần đổi — `frappe.enqueue` dùng queue mặc định, có thể khai báo `queue='long'` nếu bạn có RQ worker riêng cho long queue |
| `tests/test_async_bom_calculation.py` | Test mới |

---

## 1. Vì sao dùng `publish_realtime` thay vì polling

Bạn đã có sẵn `AL AI Intelligence` module dùng pattern log/interaction — nhưng
cho async job status, Frappe framework đã có cơ chế chuẩn:
`frappe.publish_realtime(event, message, user=frappe.session.user)` bắn qua
socketio, client `frappe.realtime.on(event, callback)` nhận ngay lập tức.
Không cần thêm bảng DB để track polling, không cần client setInterval. Đây
là lựa chọn đúng nguyên tắc "ERPNext Core First" (nguyên tắc #3) bạn đã đặt
ra — tận dụng hạ tầng realtime có sẵn thay vì tự chế.

---

## 2. Schema — custom fields trên `Quotation Item`

Thêm vào `setup/custom_fields.py`, cùng nhóm với các field `al_*` hiện có:

```python
# setup/custom_fields.py

QUOTATION_ITEM_ASYNC_FIELDS = [
    {
        "fieldname": "al_calc_status",
        "fieldtype": "Select",
        "label": "AL Calc Status",
        "options": "\nQueued\nRunning\nSuccess\nFailed",
        "read_only": 1,
        "no_copy": 1,
        "print_hide": 1,
        "insert_after": "al_bom_result",
    },
    {
        "fieldname": "al_calc_job_id",
        "fieldtype": "Data",
        "label": "AL Calc Job ID",
        "read_only": 1,
        "no_copy": 1,
        "hidden": 1,
        "insert_after": "al_calc_status",
    },
    {
        "fieldname": "al_calc_error",
        "fieldtype": "Small Text",
        "label": "AL Calc Error",
        "read_only": 1,
        "no_copy": 1,
        "print_hide": 1,
        "insert_after": "al_calc_job_id",
    },
]

# Merge vào dict CUSTOM_FIELDS["Quotation Item"] hiện có của bạn
```

---

## 3. Global Variable cho ngưỡng — không hardcode

Đúng pattern bạn đã dùng cho `VAT_RATE`, `OH_VC_PCT` (Formula Global
Variable). Thêm vào `setup/seed_demo_data.py`:

```python
# setup/seed_demo_data.py

def _seed_async_threshold():
    if frappe.db.exists("Formula Global Variable", "ASYNC_BOM_THRESHOLD"):
        return
    frappe.get_doc({
        "doctype": "Formula Global Variable",
        "variable_name": "ASYNC_BOM_THRESHOLD",
        "value": 150,  # số dòng BOM — vượt ngưỡng này sẽ chạy async
        "description": "BOM có nhiều hơn N dòng sẽ tính qua background job "
                        "thay vì đồng bộ trong request, tránh timeout.",
    }).insert(ignore_permissions=True)
```

Admin có thể chỉnh ngưỡng này trực tiếp trên UI Formula Global Variable,
0 dòng code — đúng nguyên tắc "Zero Hardcode" bạn đã đặt ra cho toàn hệ
thống.

---

## 4. `api/__init__.py` — điểm quyết định sync/async

```python
# api/__init__.py

import json
import frappe
from frappe import _


@frappe.whitelist()
def calculate_bom(qi_name):
    """
    Entry point hiện có. Thêm logic: đếm số dòng BOM trước khi chạy,
    quyết định sync (giữ nguyên hành vi cũ — trả kết quả ngay) hay
    async (enqueue, trả job_id ngay, client nhận kết quả qua realtime).
    """
    qi = frappe.get_doc("Quotation Item", qi_name)

    # Không cho tính lại nếu Quotation cha đã bị khoá bởi workflow
    # (giữ nguyên logic hiện có của bạn — không đổi)

    line_count = _estimate_bom_line_count(qi)
    threshold = _get_async_threshold()

    if line_count <= threshold:
        # HÀNH VI CŨ — giữ nguyên 100%, không ảnh hưởng BOM nhỏ/vừa
        from alumglass.engine.bom_orchestrator import BomOrchestrator
        orchestrator = BomOrchestrator(qi_name)
        return orchestrator.run()

    # HÀNH VI MỚI — BOM lớn, chạy async
    return _enqueue_bom_calculation(qi)


def _estimate_bom_line_count(qi):
    """
    Đếm nhanh số dòng BOM từ bom_set_snapshot của BOM Version đã pin,
    KHÔNG load toàn bộ BomOrchestrator chỉ để đếm — tránh lãng phí.
    """
    bom_version = qi.al_bom_version or frappe.db.get_value(
        "AL BOM", qi.al_bom, "current_version"
    )
    if not bom_version:
        return 0
    snapshot_raw = frappe.get_cached_value(
        "AL BOM Version", bom_version, "bom_set_snapshot"
    )
    if not snapshot_raw:
        return 0
    try:
        data = json.loads(snapshot_raw)
        return len(data.get("bom_items", data.get("items", [])))
    except (ValueError, TypeError):
        return 0


def _get_async_threshold():
    value = frappe.db.get_value(
        "Formula Global Variable", "ASYNC_BOM_THRESHOLD", "value"
    )
    try:
        return int(value)
    except (TypeError, ValueError):
        return 150  # fallback cứng CHỈ khi Global Variable chưa được seed


def _enqueue_bom_calculation(qi):
    job_id = f"albom-{qi.name}-{frappe.generate_hash(length=8)}"

    frappe.db.set_value(
        "Quotation Item", qi.name,
        {
            "al_calc_status": "Queued",
            "al_calc_job_id": job_id,
            "al_calc_error": "",
        },
        update_modified=False,
    )
    frappe.db.commit()

    frappe.enqueue(
        method="alumglass.api._run_bom_calculation_job",
        queue="long",
        timeout=600,          # 10 phút — đủ cho BOM rất lớn (điều chỉnh nếu cần)
        job_name=job_id,
        qi_name=qi.name,
        job_id=job_id,
        user=frappe.session.user,
    )

    return {
        "async": True,
        "job_id": job_id,
        "status": "Queued",
        "message": _("BOM có {0} dòng — đang tính trong nền, "
                      "kết quả sẽ hiện tự động khi xong.").format(
            _estimate_bom_line_count(qi)
        ),
    }


def _run_bom_calculation_job(qi_name, job_id, user):
    """
    Chạy trong RQ worker process — KHÔNG whitelist, chỉ gọi qua enqueue.
    """
    frappe.set_user(user)  # đảm bảo permission check trong Orchestrator đúng

    frappe.db.set_value(
        "Quotation Item", qi_name, "al_calc_status", "Running",
        update_modified=False,
    )
    frappe.db.commit()

    try:
        from alumglass.engine.bom_orchestrator import BomOrchestrator
        orchestrator = BomOrchestrator(qi_name)
        result = orchestrator.run()

        frappe.db.set_value(
            "Quotation Item", qi_name, "al_calc_status", "Success",
            update_modified=False,
        )
        frappe.db.commit()

        frappe.publish_realtime(
            event="alumglass_bom_calc_done",
            message={
                "job_id": job_id,
                "qi_name": qi_name,
                "status": "Success",
                "result": result,
            },
            user=user,
        )

    except Exception:
        error_trace = frappe.get_traceback()
        frappe.db.set_value(
            "Quotation Item", qi_name,
            {"al_calc_status": "Failed", "al_calc_error": error_trace[:1000]},
            update_modified=False,
        )
        frappe.db.commit()
        frappe.log_error(
            title=f"AlumGlass async BOM calc failed: {qi_name}",
            message=error_trace,
        )
        frappe.publish_realtime(
            event="alumglass_bom_calc_done",
            message={
                "job_id": job_id,
                "qi_name": qi_name,
                "status": "Failed",
                "error": str(error_trace)[-500:],  # phần cuối traceback dễ đọc nhất
            },
            user=user,
        )
```

### Vì sao không đổi `BomOrchestrator` (engine giữ nguyên)

Toàn bộ 7 phase B0-B7 chạy y hệt cho cả 2 luồng sync/async — điểm khác biệt
duy nhất là **nó chạy trong RQ worker thay vì trong request thread**. Điều
này tôn trọng đúng nguyên tắc phân lớp bạn đã đặt (Tầng 4 Orchestration
không nên biết gì về việc nó bị gọi sync hay async) — code B0-B7 không cần
sửa 1 dòng.

---

## 5. Client — `quotation_item_dialog.js`

```javascript
// public/js/quotation_item_dialog.js

function calculate_bom_for_item(qi_name, dialog) {
    frappe.call({
        method: "alumglass.api.calculate_bom",
        args: { qi_name: qi_name },
        freeze: true,
        freeze_message: __("Đang tính giá..."),
        callback: function(r) {
            if (!r.message) return;

            if (r.message.async) {
                // BOM lớn — job đã được enqueue, chờ realtime event
                dialog.set_message(r.message.message);
                show_async_progress_indicator(dialog, r.message.job_id);
                listen_for_bom_calc_result(qi_name, r.message.job_id, dialog);
            } else {
                // BOM nhỏ/vừa — kết quả trả về ngay như trước
                render_bom_result(r.message, dialog);
            }
        },
    });
}

function listen_for_bom_calc_result(qi_name, job_id, dialog) {
    frappe.realtime.on("alumglass_bom_calc_done", function(data) {
        if (data.job_id !== job_id) return;  // không phải job của dialog này

        hide_async_progress_indicator(dialog);

        if (data.status === "Success") {
            frappe.show_alert({
                message: __("Tính giá xong cho {0}", [qi_name]),
                indicator: "green",
            });
            render_bom_result(data.result, dialog);
        } else {
            frappe.show_alert({
                message: __("Tính giá lỗi: {0}", [data.error]),
                indicator: "red",
            });
            dialog.set_message(
                __("Tính giá thất bại. Xem chi tiết trong Error Log hoặc "
                   "trường AL Calc Error trên Quotation Item.")
            );
        }

        // Huỷ listener sau khi nhận kết quả, tránh leak
        frappe.realtime.off("alumglass_bom_calc_done");
    });
}

function show_async_progress_indicator(dialog, job_id) {
    dialog.$wrapper.find(".modal-body").prepend(
        `<div class="alert alert-info al-bom-progress" data-job="${job_id}">
            <i class="fa fa-spinner fa-spin"></i>
            ${__("Đang tính BOM lớn trong nền — có thể mất vài phút...")}
         </div>`
    );
}

function hide_async_progress_indicator(dialog) {
    dialog.$wrapper.find(".al-bom-progress").remove();
}
```

**Xử lý trường hợp user đóng dialog / rời trang trước khi job xong**:
`al_calc_status` đã lưu trên Quotation Item (DB), nên khi user mở lại
Quotation Item sau, JS có thể check `qi.al_calc_status`:
- `Running`/`Queued` → hiện lại progress indicator, tự động `frappe.realtime.on` lại (đăng ký lại listener trong `refresh` của form)
- `Success` → hiện `al_bom_result` đã lưu như bình thường
- `Failed` → hiện `al_calc_error`

---

## 6. Vận hành — RQ worker cho queue `long`

Nếu bench của bạn hiện chỉ chạy worker mặc định (`default`, `short`), cần
thêm 1 worker phục vụ queue `long` để job BOM lớn không cạnh tranh tài
nguyên với các job ngắn khác (email, notification...):

```bash
# Procfile / supervisor config — thêm dòng:
worker_long: bench worker --queue long

# hoặc với supervisor, thêm section riêng để scale độc lập nếu cần
```

Không có thay đổi nào trong `hooks.py` là bắt buộc — `frappe.enqueue(queue="long", ...)`
tự động dùng queue này miễn là có worker lắng nghe nó.

---

## 7. Test

```python
# tests/test_async_bom_calculation.py

import json
from unittest.mock import patch
import frappe
from frappe.tests.utils import FrappeTestCase


class TestAsyncBOMCalculation(FrappeTestCase):

    def test_small_bom_stays_sync(self):
        """BOM dưới ngưỡng → calculate_bom() trả kết quả ngay, không có job_id."""
        from alumglass.api import calculate_bom
        qi_name = self._make_quotation_item(line_count=20)  # dùng fixture nhỏ có sẵn
        result = calculate_bom(qi_name)
        self.assertNotIn("async", result)
        self.assertIn("cost_template", result)

    @patch("frappe.enqueue")
    def test_large_bom_goes_async(self, mock_enqueue):
        """BOM vượt ngưỡng → enqueue được gọi, trả job_id ngay, không block."""
        from alumglass.api import calculate_bom

        frappe.db.set_value(
            "Formula Global Variable", "ASYNC_BOM_THRESHOLD", "value", 5
        )
        qi_name = self._make_quotation_item(line_count=20)

        result = calculate_bom(qi_name)

        self.assertTrue(result.get("async"))
        self.assertIn("job_id", result)
        mock_enqueue.assert_called_once()

        qi_status = frappe.db.get_value("Quotation Item", qi_name, "al_calc_status")
        self.assertEqual(qi_status, "Queued")

    def test_failed_job_sets_error_status(self):
        """Job lỗi (VD: input sai) → al_calc_status=Failed, al_calc_error có nội dung."""
        from alumglass.api import _run_bom_calculation_job

        qi_name = self._make_quotation_item(line_count=5, corrupt_inputs=True)
        _run_bom_calculation_job(qi_name, job_id="test-job", user=frappe.session.user)

        qi = frappe.get_doc("Quotation Item", qi_name)
        self.assertEqual(qi.al_calc_status, "Failed")
        self.assertTrue(qi.al_calc_error)

    # ... helper _make_quotation_item() dùng chung fixture với
    #     test_bom_orchestrator.py hiện có ...
```

---

## 8. Checklist áp dụng

- [ ] Thêm 3 custom field vào `Quotation Item` (`setup/custom_fields.py`), `bench migrate`
- [ ] Seed `ASYNC_BOM_THRESHOLD` Global Variable (mặc định 150)
- [ ] Sửa `api/__init__.py`: `calculate_bom()` rẽ nhánh sync/async + `_run_bom_calculation_job()`
- [ ] Sửa `quotation_item_dialog.js`: xử lý response async, `frappe.realtime.on`
- [ ] Thêm worker cho queue `long` trong Procfile/supervisor
- [ ] Thêm test, chạy `bench --site <site> run-tests --app alumglass --module alumglass.tests.test_async_bom_calculation`
- [ ] Test thực tế với BOM giả lập > threshold (seed script tạo BOM 300 dòng) để đo thời gian thật trên môi trường staging trước khi đẩy production

---

## 9. Rủi ro cần lưu ý khi triển khai

- **Permission trong worker**: `frappe.set_user(user)` bắt buộc trước khi
  gọi `BomOrchestrator`, nếu không job chạy với quyền Administrator mặc
  định của worker → bỏ qua toàn bộ role-based access bạn vừa làm ở v28.8 (I4).
  Đã xử lý trong code mẫu trên — đừng bỏ dòng `frappe.set_user(user)`.
- **`freeze: true` trong JS chỉ áp dụng cho lần gọi `calculate_bom` ban đầu**
  (rất nhanh vì chỉ enqueue) — không block UI trong lúc job chạy nền, đúng
  mục đích. Đừng nhầm lẫn để `freeze: true` áp dụng suốt quá trình chờ.
- **`ConfigSnapshot`/audit trail (B7)** vẫn chạy y hệt trong worker — không
  mất tính năng audit khi chuyển sang async.
- **Timeout 600s** là điểm cần theo dõi thực tế: nếu BOM 300+ dòng vẫn
  tiệm cận ngưỡng này, nên xem xét thêm progress reporting theo phase
  (VD: `frappe.publish_realtime` sau mỗi phase B2/B4/B6) thay vì chỉ báo
  lúc xong — nhưng đây là cải tiến P3, chưa cần cho P2 go-live.
