# P2 — Async BOM Calculation (BOM lớn tính trong nền)

> **Trạng thái:** Implemented (C3, Nhóm I quotation production-ready) · 2026-08-21
> **Job:** `2026-08-16_alumglass-sprint1-quotation`
> **Design gốc:** `P2-async-bom-calculation.md` (repo root)

## Vấn đề

Báo giá công trình lớn (hàng trăm dòng BOM) tính qua `BomOrchestrator` **đồng
bộ trong request** — FormulaEngine DAG + FlexibleFormulaEngine dễ chạm timeout
server (nginx/uwsgi), user đứng chờ spinner rồi request chết. Cần tách: BOM
nhỏ/vừa giữ sync 100% (hành vi cũ), BOM lớn chạy background + đẩy kết quả về
client qua realtime.

## Giải pháp

### 1. Ngưỡng cấu hình được — không hardcode

`Formula Global Variable` mới: **`ASYNC_BOM_THRESHOLD`** (`Int`, default
`150`). Admin chỉnh trực tiếp trên UI Formula Global Variable, **0 dòng code**.
`_get_async_threshold()` đọc `constant_value`, fallback `150` khi thiếu/không
parse được.

### 2. Đếm dòng BOM từ snapshot (không load engine)

`_estimate_bom_line_count(qi)`:

- Lấy `al_bom_version` từ item (fallback `AL BOM.current_version`).
- Đọc `bom_set_snapshot` (cached) → `len(bom_items)`.
- Không có version / parse lỗi → `0` (chạy sync — an toàn).

**KHÔNG load BomOrchestrator chỉ để đếm** — tránh lãng phí; snapshot đã có sẵn
trên version pin.

### 3. Điểm quyết định sync/async

`alumglass.api.calculate_bom(quotation_item_name)`:

```
line_count ≤ ASYNC_BOM_THRESHOLD
  → BomOrchestrator.run() đồng bộ (GIỮ NGUYÊN hành vi cũ)
  → _normalize_bom_response() đảm bảo 3 key {buckets, cost_template, lines}
line_count > ngưỡng
  → _enqueue_bom_calculation(qi)
```

`_normalize_bom_response(result)` — C4: `setdefault` 3 key để client không gãy
khi engine trả thiếu field (không đổi số liệu, chỉ đảm bảo key tồn tại).

### 4. Enqueue (queue long)

```python
job_id = "albom-{qi.name}-{hash8}"
frappe.db.set_value("Quotation Item", qi.name,
    {"al_calc_status": "Queued", "al_calc_job_id": job_id, "al_calc_error": ""})
frappe.db.commit()
frappe.enqueue(
    method="alumglass.api._run_bom_calculation_job",
    queue="long", timeout=600, job_name=job_id,
    qi_name=qi.name, job_id=job_id, user=frappe.session.user,
)
```

Trả về `{async: True, job_id, status: "Queued", message}` — client nhận
`job_id` để lọc realtime event.

### 5. Worker job (KHÔNG whitelist)

`_run_bom_calculation_job(qi_name, job_id, user)`:

1. **Bắt buộc `frappe.set_user(user)`** — worker mặc định chạy quyền
   Administrator; nếu không set_user, toàn bộ role-based access bị bỏ qua.
2. Set `Running` + commit **TRƯỚC** khi chạy engine.
3. Chạy `BomOrchestrator(qi_name).run()`.
4. Set `Success` + commit → `frappe.publish_realtime("alumglass_bom_calc_done",
   {job_id, qi_name, status: "Success", result}, user=user)`.
5. `Exception` → set `Failed` + `al_calc_error` (traceback ≤1000 ký tự) +
   commit → `log_error` + publish `Failed`.

**Tại sao set status + commit trước publish:** client nhận realtime event sẽ
đọc lại `al_calc_status`/`al_bom_result` từ DB — nếu commit chưa xong, client
đọc trạng thái cũ. Trật tự: set DB → commit → publish.

### 6. Client JS

| File | Hành vi |
|---|---|
| `public/js/bom_dialog.js` | Response `async: true` → spinner + `frappe.realtime.on("alumglass_bom_calc_done", handler)` lọc theo `job_id`. Nhận Success → render result; Failed → error panel. **Cleanup listener khi dialog đóng** (`hidden.bs.modal` → `frappe.realtime.off`). Mở lại dialog → đọc `al_calc_status` + `al_bom_result` sẵn có, KHÔNG gọi lại API khi đang tính nền / đã xong. |
| `public/js/quotation_item_dialog.js` | Preview panel tương tự: `_run_preview()` handle async + `_listen_realtime(job_id, $container)` + `_cleanup_realtime()` khi dialog đóng. `_render_preview_panel()` mở lại đọc trạng thái đã lưu. |

### 7. Field mới trên Quotation Item

| Field | Type | Ý nghĩa |
|---|---|---|
| `al_calc_status` | Select (`\nQueued\nRunning\nSuccess\nFailed`) | Trạng thái tính BOM. Rỗng = chưa tính. read_only/no_copy/print_hide |
| `al_calc_job_id` | Data | Job ID background job — client lọc realtime event. hidden/read_only |
| `al_calc_error` | Small Text | Traceback ngắn khi job fail. read_only/no_copy/print_hide |

Khai báo trong `setup/custom_fields.py` (Quotation Item section).

## File thay đổi

| File | Thay đổi |
|---|---|
| `alumglass/api/__init__.py` | `calculate_bom` async + 5 helpers (`_normalize_bom_response`, `_estimate_bom_line_count`, `_get_async_threshold`, `_enqueue_bom_calculation`, `_run_bom_calculation_job`) |
| `alumglass/setup/custom_fields.py` | +3 field Quotation Item |
| `alumglass/setup/seed_demo_data.py` | `_seed_async_threshold()` (default 150) |
| `alumglass/public/js/bom_dialog.js` | Async/spinner/realtime/cleanup/reopen-state |
| `alumglass/public/js/quotation_item_dialog.js` | Async preview + reopen-state |
| `alumglass/tests/test_async_bom_calculation.py` | Test threshold/line count/enqueue/worker |

## Test

`test_async_bom_calculation.py` — verify:
1. Threshold đọc Global Variable, fallback 150.
2. Line count từ bom_set_snapshot (≥1 cho CDMQ-2C), 0 khi không có version.
3. Enqueue trả `{async, job_id}` + `frappe.enqueue(queue="long", timeout=600)`.
4. Worker success → set `Success` + publish realtime; failure → `Failed` +
   publish Failed.
5. `calculate_bom` sync khi ≤ ngưỡng (không gọi enqueue); async khi > ngưỡng.

> **Không đổi golden:** BOM ≤ ngưỡng (CDMQ-2C 16 dòng, CDMQ-4C 22 dòng — đều
> < 150) chạy sync 100%, cùng code path cũ → GIA_VAT không đổi.
