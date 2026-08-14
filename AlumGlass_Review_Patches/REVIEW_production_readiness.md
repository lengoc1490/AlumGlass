# AlumGlass ERP (branch `version-16`) — Review chi tiết & Checklist Production

> Review dựa trên đọc trực tiếp mã nguồn tại
> https://github.com/lengoc1490/AlumGlass/tree/version-16 (60 DocType,
> `bom_orchestrator.py`, `fb_handlers.py`, `hooks.py`, toàn bộ file
> `permissions` trong 60 DocType JSON, `custom_fields.py`, `seed_demo_data.py`,
> `al_bom_version.py`, `al_pricing_dimension.py`, `pyproject.toml`, CI config).

## 1. Đánh giá tổng quan

Chất lượng kỹ thuật cao hơn hẳn mặt bằng chung dự án ERP custom ở giai đoạn
này: có test số liệu cụ thể (`run_test.py` khớp `GIA_VAT ≈ 22,717,289 VND`),
có changelog kỹ thuật chi tiết theo từng version, có tư duy data-driven nhất
quán (System Variables, Calc Pattern, Pricing Dimension đều tự sinh custom
field / tự resolve từ DB, đúng tinh thần "0 dòng code cho config mới").

Tuy nhiên, **"khớp số 22,717,289đ" chỉ chứng minh đúng phần công thức
BOM/Cost Template — không chứng minh composite pricing đúng**, vì ví dụ đó
chỉ dùng 1 màu duy nhất nên gap không lộ ra. Đây là bài học chung: cần thêm
test case "khác biệt" (khác màu, nhiều dòng giá cùng item) chứ không chỉ lặp
lại 1 "golden case".

## 2. Danh sách phát hiện (ưu tiên theo mức độ)

| # | Mức độ | Vị trí | Vấn đề | Đã có patch? |
|---|--------|--------|--------|:---:|
| 1 | 🔴 Cao | `bom_orchestrator.py::b2_prefetch_master_data` | Composite pricing (màu/xuất xứ/độ dày/bề mặt) không được áp dụng trong luồng tính thật; có thể ra giá non-deterministic nếu 1 item có nhiều dòng Item Price | ✅ `PATCH_composite_pricing.md` |
| 2 | 🔴 Cao | Toàn bộ 60 DocType | Chỉ có role `System Manager` — không có role riêng cho Sales/Site Engineer/Warehouse/Kế toán dự án. Muốn nhân viên bán hàng dùng Quotation Item thì phải cấp quyền System Manager (vi phạm least-privilege) | ⚠️ Xem mục 3 |
| 3 | 🟠 Trung bình-Cao | `.github/workflows/ci.yml` + không có thư mục `tests/` | CI chạy `bench run-tests` nhưng không có file `test_*.py` chuẩn `FrappeTestCase` nào trong `tests/` → CI có thể báo xanh dù 0 test thực sự chạy | ✅ File test đính kèm nên đặt vào `alumglass/tests/` |
| 4 | 🟠 Trung bình | `hooks.py` / `pyproject.toml` | Không khai báo `required_apps = ["formula_builder"]` → cài trên site thiếu formula_builder sẽ pass lúc install nhưng crash lúc runtime | ✅ `PATCH_deploy_and_immutability.md` §2.1 |
| 5 | 🟠 Trung bình | `al_bom_version.py` | Không có guard chặn sửa `bom_set_snapshot`/`cost_template_snapshot` sau khi `workflow_state = Published` → phá vỡ cam kết "immutable version" | ✅ `PATCH_deploy_and_immutability.md` §2.2 |
| 6 | 🟡 Thấp-Trung bình | `al_quantity_calc_method.py::_get_calc_fn` | Dùng `eval()` (dù đã restrict `__builtins__={}`) — về lý thuyết vẫn có kỹ thuật escape sandbox Python thuần túy. Rủi ro thấp vì đã khoá quyền System Manager | Khuyến nghị: cân nhắc `simpleeval`/`asteval` nếu muốn an toàn tuyệt đối, không bắt buộc ngay |
| 7 | 🟡 Thấp | Tất cả DocType | `track_changes` không được set tường minh (None) trên các DocType quan trọng (AL BOM Version, AL Calculation Rule, Item Price) — nên bật rõ ràng để có audit trail đầy đủ, khớp với mục tiêu "immutable + traceable" | Khuyến nghị bật `track_changes: 1` |
| 8 | 🟡 Thấp | `pyproject.toml` | `requires-python = ">=3.14"` — Python rất mới; cần xác nhận Frappe v16 + các thư viện phụ thuộc (đặc biệt `formula_builder`) đã test ổn định trên 3.14 trong môi trường hosting thực tế trước khi go-live | Khuyến nghị: pin `>=3.12,<3.15` trừ khi đã test kỹ 3.14 |
| 9 | 🟡 Thấp | `al_pricing_dimension.py::_sync_custom_field` | `custom_fieldname = f"custom_pd_{self.dimension_code}"` không lowercase `dimension_code`. Nếu người dùng nhập `dimension_code` có chữ hoa (như seed data `"MAU_SAC"`), field sinh ra tên có chữ hoa — nên kiểm tra kỹ hành vi thực tế của Frappe với fieldname không toàn thường | Khuyến nghị: `self.dimension_code.lower()` khi build fieldname |

## 3. Đề xuất cấu trúc Role cho Production (ứng với mục #2)

Hiện tại mọi thao tác nghiệp vụ hàng ngày đều yêu cầu `System Manager` —
không khả thi để giao cho nhân viên thật. Đề xuất tối thiểu 4 role nghiệp vụ,
map theo module:

| Role đề xuất | Áp dụng cho DocType | Quyền |
|---|---|---|
| **AL Sales User** | Quotation, Quotation Item (đã có sẵn field custom), AL BOM (read-only), AL Product Type (read-only) | Read AL Master Data, Create/Write Quotation |
| **AL BOM Manager** | AL BOM, AL BOM Set, AL BOM Version, AL Cost Template, AL Calculation Rule, AL Dynamic Item Rule | Full trên nhóm AL BOM Engine + AL Formula Rules — đây là nhóm "config sản phẩm", khác System Manager (không cần quyền quản trị user/hệ thống) |
| **AL Site Engineer** | AL Site Survey, AL Installation Order, AL Installation Progress, AL Handover Acceptance | Full trên AL Construction, read-only trên AL BOM Engine |
| **AL Project Accountant** | AL Project Financial Config, AL Cost Variance, AL Project Profitability Snapshot | Read/Write nhóm AL Account |

Việc này không phức tạp về mặt code (chỉ là thêm `permissions` block trong
JSON của từng DocType + tạo Role qua fixtures), nhưng **là điều kiện bắt
buộc trước khi có user thật ngoài đội dev dùng hệ thống** — nên ưu tiên làm
trước khi mở rộng thêm module mới.

## 4. Checklist trước khi go-live (tổng hợp)

- [ ] Áp patch #1 (composite pricing) + chạy `test_composite_pricing.py` PASS
- [ ] Chuyển `run_test.py` thành `alumglass/tests/test_bom_orchestrator.py`
      chuẩn `FrappeTestCase` để CI thực sự chặn regression
- [ ] Thêm `required_apps = ["formula_builder"]` vào `hooks.py`
- [ ] Áp guard immutability cho `AL BOM Version` (patch #2.2)
- [ ] Thiết kế + tạo tối thiểu 4 role nghiệp vụ (mục 3) thay vì chỉ có
      System Manager
- [ ] Bật `track_changes: 1` cho AL BOM Version, AL Calculation Rule,
      AL Dynamic Item Rule Version, Item Price
- [ ] Xác nhận tương thích Frappe v16 + Python 3.14 trên môi trường hosting
      thật (hoặc hạ xuống Python 3.12/3.13 nếu chưa test kỹ)
- [ ] Viết thêm 2-3 test case "khác biệt" tương tự composite pricing cho
      các phần data-driven khác (Dynamic Item Rule THRESHOLD/LOOKUP, Cost
      Bucket aggregate) — nguyên tắc chung: mỗi tính năng "tự động hoá theo
      config" cần ít nhất 1 test đổi config và kỳ vọng kết quả đổi theo,
      không chỉ test "chạy được"

## 5. Điểm cộng cần giữ nguyên (đừng refactor quá tay)

- Kiến trúc 7-phase của `BomOrchestrator` (B0-B7) rất rõ ràng, dễ debug —
  giữ nguyên khi vá lỗi, đừng gộp lại cho "gọn".
- Cách batch query (gộp N+1 thành batch `IN (...)`) đã đúng hướng — patch
  composite pricing ở trên cố tình giữ đúng pattern này thay vì gọi lại FB
  source type resolver cho từng dòng.
- `_validate_no_overlap()` trong `AL Calculation Rule` — giữ nguyên, đây là
  chi tiết chất lượng cao hiếm gặp.
