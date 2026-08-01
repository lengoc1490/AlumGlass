# ARCHITECTURE REVIEW — AlumGlass v28.6
## Đánh giá tính đa năng, linh hoạt, hiệu năng & khả năng tận dụng ERPNext/Frappe + Formula Builder

> **Reviewer:** Chuyên gia ERPNext/Frappe + triển khai ERP + ngành nhôm kính
> **Ngày:** 2026-07-27 (gốc) | 2026-08-01 (cập nhật v28.6: tái cấu trúc module, tận dụng ERPNext core)
> **Phạm vi:** Toàn bộ v28.md, v28.2-UPGRADE-ANALYSIS.md, CAU_TRUC_MODULE_VA_DOCTYPE.md, AlumGlass_Vi_Du_Full_Chi_Tiet.md, templates.py, hooks.py
> **Thang điểm:** 1-5 (5 = xuất sắc, đạt chuẩn enterprise)

---

## TỔNG QUAN ĐIỂM SỐ

| Tiêu chí | Điểm | Mức độ |
|---|---|---|
| **Đa năng (đa ngành)** | 4.0/5 | Tốt — đã có nền tảng nhưng cần bổ sung namespace slug |
| **Linh hoạt (config-driven)** | 4.5/5 | Rất tốt — đã loại bỏ hầu hết hardcode từ v28.1 |
| **Dễ mở rộng (extensibility)** | 4.5/5 | Rất tốt — v28.6 module rõ ràng, mỗi module có trách nhiệm đơn nhất |
| **Hiệu năng** | 3.5/5 | Khá — có cơ chế batch/cache nhưng thiếu profiling & N+1 guard |
| **Tận dụng ERPNext Core** | 4.0/5 | Tốt — v28.6: thêm Projects, CRM, Maintenance, Budget, Cost Center. Còn thiếu: Item Variant |
| **Tận dụng Formula Builder** | 4.5/5 | Rất tốt — thin layer đúng đắn, dùng đúng path |
| **Tính nhất quán kiến trúc** | 4.5/5 | Rất tốt — 25 nguyên tắc rõ ràng, module tách biệt, DocType đúng chỗ |
| **Tài liệu & khả năng triển khai** | 4.0/5 | Tốt — docs đầy đủ, ví dụ A-Z, plan chi tiết |
| **TỔNG HỢP** | **4.2/5** | **Thiết kế tốt, sẵn sàng triển khai. Cải thiện đáng kể từ v28.2** |

---

## PHẦN 1: ĐÁNH GIÁ TÍNH ĐA NĂNG (ĐA NGÀNH)

### 1.1 Điểm mạnh

| # | Điểm mạnh | Đánh giá |
|---|---|---|
| D1 | **AL Material Category** cho phép thêm ngành mới không cần code | ✅ Giải quyết triệt để vấn đề gốc |
| D2 | **AL Pricing Dimension** tách biệt đặc tính giá khỏi schema | ✅ Có thể áp dụng cho mọi ngành |
| D3 | **AL Slug Library** dùng slug làm định danh — bất kỳ ngành nào cũng có thể định nghĩa bộ slug riêng | ✅ |
| D4 | **Cost Bucket với source_type/source_config** — không giới hạn ngành | ✅ Kiến trúc data-source agnostic |
| D5 | **Dispatch table từ DB** (lookup_calc_pattern) — pattern VOLUME, SURFACE_AREA thêm dễ dàng | ✅ |

### 1.2 Điểm cần cải thiện

| # | Vấn đề | Mức độ | Đề xuất |
|---|---|---|---|
| D6 | **Slug namespace phẳng** — slug `khung_ngang_tren` gắn cứng với 1 category. Khi dùng cho ngành thép, không thể tái dùng slug này. Phải tạo `khung_ngang_tren_thep`. Điều này dẫn đến bùng nổ số lượng slug. | MEDIUM | Thêm field `namespace` hoặc `bom_context` vào AL Slug Library. Slug + namespace = unique. VD: namespace `ALUMINUM_DOOR` vs `STEEL_DOOR`. |
| D7 | **Cross-row reference giả định field name cố định** — `items.kinh_tren.width` giả định mọi dòng đều có field `width`. Với ngành gỗ, có thể cần `thickness` (độ dày gỗ) là input chính. | MEDIUM | Cho phép `items.<slug>.custom_field` trong cross-ref — engine đọc field từ Bom Item definition thay vì hardcode. |
| D8 | **Không có multi-currency gốc trong BOM** — Item Price hiện tại theo 1 currency. Khi nhập khẩu thép từ Trung Quốc (CNY) và bán tại VN (VND), cần multi-currency trong cùng 1 BOM. | LOW | Tận dụng ERPNext's `price_list_currency` + `Currency Exchange` — thêm field `currency` vào Bucket. |
| D9 | **Không có Unit of Measure (UOM) conversion** — design giả định NHOM=kg, KINH=m2, VTP=m. Nhưng thép có thể bán theo cây (thanh 6m), nhựa theo cuộn (roll). | MEDIUM | Tận dụng ERPNext's UOM Conversion. AL Bom Item thêm field `stock_uom` và `pricing_uom`. Công thức `lookup_calc_pattern` nhận thêm UOM factor. |

---

## PHẦN 2: ĐÁNH GIÁ TÍNH LINH HOẠT (CONFIG-DRIVEN)

### 2.1 Điểm mạnh

| # | Điểm mạnh | Đánh giá |
|---|---|---|
| L1 | **Validate data-driven** — `category.requires_*` thay `if line_type ==` | ✅ Xuất sắc |
| L2 | **Composite key giá động** — AL Pricing Dimension tự sinh custom field, validate, lookup | ✅ Giải pháp tương đương Accounting Dimension |
| L3 | **Cost Bucket config bằng JSON** — source_type + source_config | ✅ Đúng hướng |
| L4 | **AL Calculation Rule LOOKUP/THRESHOLD** — bảng giá, ngưỡng cấu hình qua UI | ✅ |
| L5 | **FB v31 Composite Types** — pipeline, conditional, fallback_chain không cần code | ✅ |

### 2.2 Điểm cần cải thiện

| # | Vấn đề | Mức độ | Đề xuất |
|---|---|---|---|
| L6 | **`_load_cost_bucket_definitions()` load TẤT CẢ buckets mỗi lần** — không filter theo BOM đang dùng. Nếu hệ thống có 50 bucket cho 5 ngành, mỗi lần tính BOM nhôm vẫn load 50 bucket definitions. | LOW | Thêm filter: chỉ load bucket có `applies_to_category` match hoặc bucket đang được Bom Item tham chiếu. |
| L7 | **Không có UI để test Cost Bucket config** — user nhập JSON vào source_config mà không biết đúng sai cho đến khi chạy BOM thật. | MEDIUM | Thêm nút "Test Data Source" trên form AL Cost Bucket — gọi `BatchBindingResolver` với sample inputs và hiển thị kết quả. |
| L8 | **Variable Set mapping với Pricing Dimension là convention-based, không validated** — nếu user đặt tên sai convention (`mau_nhom` thay vì `COLOR_NHOM`), hệ thống im lặng bỏ qua. | MEDIUM | Thêm validate khi lưu Variable Set: kiểm tra tên biến có map được với ít nhất 1 Pricing Dimension không. Cảnh báo nếu không. |
| L9 | **Rule version pinning (B0) chỉ pin BOM version, không pin Pricing Dimension version** — nếu user thay đổi Pricing Dimension (vd: thêm field bắt buộc), các báo giá cũ có thể bị ảnh hưởng. | HIGH | Pricing Dimension cũng cần version + snapshot như BOM. Khi tạo Quotation, pin toàn bộ config (BOM version + Rule version + Pricing Dimension version). |

---

## PHẦN 3: ĐÁNH GIÁ HIỆU NĂNG

### 3.1 Điểm mạnh

| # | Điểm mạnh | Đánh giá |
|---|---|---|
| H1 | **BatchBindingResolver** — gom query giảm 90% (34-50 → 4-5) | ✅ |
| H2 | **`@batchable` decorator** — FB tự gom các handler cùng batch_group | ✅ |
| H3 | **Cache TTL** — DataSourceResolver có cache_ttl=300s | ✅ |
| H4 | **`frappe.get_cached_doc`** — dùng cho AL Slug Library, AL Material Category | ✅ |
| H5 | **TraceLevel `cost_only`** — giảm 88% dung lượng snapshot (31KB → 4KB) | ✅ |

### 3.2 Điểm cần cải thiện

| # | Vấn đề | Mức độ | Đề xuất |
|---|---|---|---|
| H6 | **B1 load tất cả AL Calculation Rule CONSTANT mỗi lần** — `frappe.get_all("AL Calculation Rule", filters={"rule_type": "CONSTANT"})` không cache. Với 50+ rules, mỗi lần tính BOM đều query. | MEDIUM | Dùng `frappe.cache()` với TTL 1h. Hoặc load 1 lần trong `__init__` và cache ở module level. |
| H7 | **load_global_variables() dùng `frappe.get_all`** — không cache, gọi mỗi lần tính. | MEDIUM | Tương tự H6 — cache Global Variable với TTL dài hơn (24h) vì ít thay đổi. |
| H8 | **Không có cơ chế N+1 guard** — B3 loop qua bom_items gọi `frappe.get_cached_doc` cho Dynamic Item Rule. Nếu 50 dòng Bom Item dùng Rule, 50 lần get_cached_doc. | MEDIUM | Pre-load tất cả Rule vào dict trước khi loop. Dùng `frappe.db.get_all` + `as_dict` thay vì `frappe.get_doc` khi chỉ cần đọc. |
| H9 | **row_literals inject từng key một vào bom_inputs** — `for key in ("weight_per_unit", "unit_price", ...)`. Với 100 dòng BOM, 100*5 = 500 lần gán dict. Không đáng kể nhưng có thể tối ưu. | LOW | Dùng `bom_inputs.update({f"{slug}__{k}": v for k, v in literals.items()})`. |
| H10 | **Không có cơ chế warm-up cache** — lần đầu tính BOM sau khi restart server, tất cả cache miss. | LOW | Thêm `after_migrate` hook pre-load các bảng nhỏ (AL Slug Library, AL Material Category, AL Quantity Calc Method, AL Cost Bucket) vào Redis. |
| H11 | **Chưa có async/background job cho BOM lớn** — BomOrchestrator chạy đồng bộ trong request. Với BOM 200+ dòng (vách kính lớn), có thể timeout. | HIGH | Cho phép `calculate_bom` chạy qua `frappe.enqueue()` với BOM > N dòng. Trả về job_id, client poll kết quả. |
| H12 | **Snapshot dùng JSON_EXTRACT nhưng không có index** — query snapshot theo GIA_VAT > X sẽ scan toàn bộ bảng. | MEDIUM | Tạo generated column hoặc virtual field trên DocType Formula Snapshot. Hoặc tận dụng MariaDB 10.3+ JSON virtual index. |

---

## PHẦN 4: ĐÁNH GIÁ TẬN DỤNG ERPNext/Frappe CORE

### 4.1 Điểm mạnh

| # | Điểm mạnh | Core feature đã dùng |
|---|---|---|
| E1 | **Item là nguồn sự thật** — không tạo DocType "AL Product" trung gian | ✅ Item + Item Price |
| E2 | **Workflow cho BOM Version** — dùng core Workflow engine | ✅ Workflow |
| E3 | **Batch cho quản lý màu** — tận dụng Batch + Batch Wise Valuation | ✅ Batch |
| E4 | **GL Entry cho chi phí thực tế** — Cost Variance đọc từ accounting | ✅ GL Entry |
| E5 | **Pricing Rule core** — chiết khấu | ✅ Pricing Rule |
| E6 | **Quality Inspection, Warranty Claim, Payment Schedule** — dùng core | ✅ |
| E7 | **`frappe.get_cached_doc`** — tận dụng framework cache | ✅ |
| E8 | **`frappe.custom_field.create_custom_field`** — cho Pricing Dimension | ✅ |

### 4.2 Cơ hội bị bỏ lỡ

| # | Cơ hội | Core feature | Mức độ | Đề xuất |
|---|---|---|---|---|
| E9 | **Item Variant cho profile** — thay vì tạo 50 Item riêng biệt cho Xingfa 55 (KB-20, KB-25, CANH-20...), dùng Item Variant với attributes: `system`, `profile_type`, `thickness` | Item Variant + Item Attribute | HIGH | Mỗi hệ profile (XINGFA_55) là 1 Item Template. Các variant là profile cụ thể. Giảm 80% số lượng Item. |
| E10 | **BOM core cho Production Order** — AL Bom Set đang là custom BOM, không bridge được với ERPNext Production Order. Cần AL Production Order Bridge thủ công. | BOM + Work Order | MEDIUM | Mapping AL Bom Set → ERPNext BOM khi publish BOM Version. Sinh ERPNext BOM tự động từ AL Bom Set. Dùng `frappe.copy_doc`. |
| E11 | **Serial No cho offcut tracking** — v28 có đề cập Serial No cho offcut nhưng chưa có thiết kế chi tiết. | Serial No | MEDIUM | Khi Cutting Plan cắt thanh 6m thành các đoạn, tạo Serial No cho từng đoạn. Đoạn còn lại > min_offcut → Serial No offcut về kho. |
| E12 | **Accounting Dimension cho P&L** — 🟢 ĐÃ CÓ THIẾT KẾ trong v28.6: Tạo Accounting Dimension `AL Product Type`. Map khi tạo Sales Invoice từ Quotation. Tận dụng Budget + Cost Center. | Accounting Dimension | MEDIUM | Đã giải quyết trong v28.6 — cần code thực tế. |
| E13 | **Auto Email / Notification** — không đề cập tự động gửi email khi BOM được approve, khi giá biến động... | Notification + Email Queue | LOW | Thêm AL Alert Config gửi qua `frappe.sendmail` hoặc `Notification` DocType. |
| E14 | **Print Format cho báo giá** — không có thiết kế print format chuyên biệt cho báo giá nhôm kính. | Print Format + Jinja | LOW | Tạo Print Format hiển thị BOM lines dạng bảng vật tư kèm đơn giá. Dùng Jinja template với BomOrchestrator data. |
| E15 | **Translation / Localization** — slug label đang là tiếng Việt cứng. Khi mở rộng ra thị trường quốc tế cần đa ngôn ngữ. | Frappe Translation | LOW | Thêm field `label_en` vào AL Slug Library. Dùng `frappe._()` cho UI strings. |
| E16 | **Dashboard / Number Card** — không đề cập tận dụng Frappe Dashboards. | Dashboard + Number Card | LOW | Tạo Dashboard "AlumGlass KPI" với Number Card: số báo giá/tháng, avg margin, top sản phẩm... Dùng Report + Chart của Frappe. |
| E17 | **Webhook / API cho bên thứ 3** — không có thiết kế API public cho dealer/customer portal. | Frappe REST API + Webhook | LOW | Whitelist `calculate_bom` API. Tạo Webhook khi BOM được publish → notify dealer portal. |

### 4.3 Đã giải quyết trong v28.6 (🟢)

| # | Vấn đề cũ | Cách giải quyết |
|---|---|---|
| **M1** | 10 DocType đặt sai module (Supplier Price List ở Master Data, Change Order/Handover ở Account...) | Chuyển về đúng module: Supplier Price List → AL Buying, Installation Team → AL Construction, Cutting Standard → AL Manufacturing, Warranty Policy → AL Quality, Accessory Set → AL BOM Engine, Change Order/Handover/Punchlist → AL Construction |
| **M2** | Module AL Account chứa DocType thi công (Change Order, Handover) | AL Account giờ chỉ còn 2 DocType thuần kế toán: P&L Snapshot + Project Financial Config |
| **M3** | Thiếu tận dụng ERPNext Projects | Thêm custom fields trên Project, Task, Timesheet. Link với AL Construction |
| **M4** | Thiếu tận dụng ERPNext CRM | Dùng Lead, Opportunity, Contract cho pipeline bán hàng. Custom fields `al_*` |
| **M5** | Thiếu tận dụng ERPNext Maintenance | Dùng Maintenance Visit, Maintenance Schedule cho bảo trì sau bàn giao |
| **M6** | Thiếu tận dụng HRMS (Employee) | Ghi nhận HRMS là app riêng, dùng Employee nguyên bản. Không tạo module AL HR |
| **M7** | Sơ đồ có AL HR nhưng không có module tương ứng | Đã sửa sơ đồ, thay bằng ERPNext Core + HRMS blocks |

---

## PHẦN 5: ĐÁNH GIÁ TẬN DỤNG FORMULA BUILDER

### 5.1 Điểm mạnh

| # | Điểm mạnh | FB component |
|---|---|---|
| F1 | **Dùng đúng 2 path của FB** — FormulaEngine cho Bom Items (Path B), FlexibleFormulaEngine cho Cost Template (Path A) | ✅ Quyết định kiến trúc đúng đắn |
| F2 | **Cross-row reference qua normalize `items.slug.field` → `slug__field`** | ✅ Tận dụng FB DAG |
| F3 | **BatchBindingResolver cho DataSource** — Thin layer ~80 dòng | ✅ |
| F4 | **SnapshotManager.submit()/load()** — persistence | ✅ |
| F5 | **SourceTypeRegistry + hooks.py** — đăng ký handler không monkey-patch | ✅ |
| F6 | **13 source types + Composite Types** — pipeline, conditional, fallback_chain | ✅ |
| F7 | **Transform layer** — post-processing không cần code Python | ✅ |

### 5.2 Điểm cần cải thiện

| # | Vấn đề | Mức độ | Đề xuất |
|---|---|---|---|
| F8 | **`_normalize_cross_ref()` dùng regex đơn giản** — `re.sub(r'items\.(\w[\w-]*)\.(\w+)', r'\1__\2', expr)`. Regex này không xử lý được nested reference như `items.kinh_tren.width + items[0].height`. | LOW | Dùng FB's built-in `DotToSubscriptTransformer` thay vì tự viết regex. |
| F9 | **lookup_calc_pattern nhận các tham số cố định (w, h, tlr, **kw)** — không linh hoạt nếu pattern mới cần tham số khác (vd: density cho tính khối lượng riêng). | LOW | Đã có `**extra_vars` để mở rộng. OK. |
| F10 | **Không dùng FB's `explain()` trong BomOrchestrator** — khi debug, dev phải tự trace DAG. FB đã có `engine.explain()` trả về trace. | MEDIUM | Thêm `b4_debug_mode` option trong BomOrchestrator. Khi bật, gọi `engine.explain()` và log vào `AL Debug Log`. |
| F11 | **EngineConfig cho Cost Template không có custom_functions** — nếu Cost Template cần gọi hàm custom (vd: `safe_div`, `round_to`), không có cách đăng ký. | LOW | Thêm `custom_functions` vào EngineConfig ở B6. Đăng ký ít nhất `safe_div` và `round_to`. |

---

## PHẦN 6: ĐÁNH GIÁ KIẾN TRÚC TỔNG THỂ

### 6.1 Điểm mạnh

| # | Điểm mạnh |
|---|---|
| A1 | **25 nguyên tắc thiết kế rõ ràng, có tính ràng buộc** |
| A2 | **5 tầng kiến trúc phân lớp đúng: Storage → Rule → Engine → Orchestration → Business Modules** |
| A3 | **7-phase BomOrchestrator mạch lạc, mỗi phase 1 trách nhiệm** |
| A4 | **Separation of concerns rõ: FB không biết nhôm kính, AlumGlass không tự tính toán** |
| A5 | **Version + Snapshot strategy tốt: immutable snapshots, workflow-managed** |
| A6 | **Migration path từ v28.1 → v28.2 được thiết kế (dual-run, backward compat)** |

### 6.2 Điểm cần cải thiện

| # | Vấn đề | Mức độ | Đề xuất |
|---|---|---|---|
| A7 | **AL Accessory Set là DocType "zombie"** — giữ lại cho backward compatible nhưng khuyến nghị dùng AL Bom Item thay thế. Nên có timeline deprecation rõ ràng. | LOW | Đánh dấu `@deprecated` trong code + docs. Timeline: v28.2 = warning, v29 = remove. |
| A8 | **AL Calculation Rule có 2 kiểu CONSTANT trùng với AL Profile System** — offset vừa có trong Calculation Rule (fallback) vừa có trong AL Profile System (primary). Dễ gây nhầm lẫn. | MEDIUM | Khi Bom Set có `profile_system`, ẩn/disable CONSTANT offset rules. Chỉ dùng làm fallback. Giai đoạn v29 loại bỏ hẳn CONSTANT type khỏi Calculation Rule. |
| A9 | **AL Variable Dimension Mapping là DocType riêng nhưng quá mỏng** — 3 field, có thể gộp vào AL Pricing Dimension hoặc AL Variable Set. | LOW | Gộp thành child table trong AL Pricing Dimension: `variable_mappings`. |
| A10 | **Không có Error Recovery Pattern** — nếu B4 fail ở dòng thứ 50/100, toàn bộ kết quả bị discard. Không có partial result. | MEDIUM | Wrap B4 calculation trong try/except per-phase. Nếu fail, trả về partial result với error flag trên các dòng lỗi. Dùng FB's `on_error="continue"` mode. |
| A11 | **Quotation Item có quá nhiều custom fields riêng lẻ (al_vl_nhom, al_vl_kinh, ...)** — khi thêm bucket mới, phải thêm custom field mới. | MEDIUM | Dùng 1 JSON field `al_bucket_results` thay vì 10+ fields riêng lẻ. Hoặc dùng child table `al_quotation_buckets`. |

---

## PHẦN 7: KHUYẾN NGHỊ ƯU TIÊN

### PRIORITY 1 — CRITICAL (nên làm trước khi go-live)

| # | Vấn đề | Impact | Effort |
|---|---|---|---|
| **P1** | Pricing Dimension versioning (L9) — pin version khi tạo Quotation để đảm bảo tính tái lập | Báo giá cũ có thể sai nếu dimension thay đổi | 2-3 ngày |
| **P2** | Async BOM calculation cho BOM lớn (H11) — tránh timeout với BOM > 200 dòng | Ảnh hưởng trực tiếp đến UX với công trình lớn | 1-2 ngày |
| **P3** | Item Variant cho profile (E9) — giảm 80% số Item cần tạo | Giảm đáng kể công sức setup master data | 3-5 ngày |

### PRIORITY 2 — HIGH (nên làm trong phase MVP)

| # | Vấn đề | Impact | Effort |
|---|---|---|---|
| **P4** | ERPNext BOM bridge (E10) — map AL Bom Set → ERPNext BOM | Cần cho Production Order, MRP | 3-5 ngày |
| **P5** | Accounting Dimension cho P&L (E12) — tự động lọc báo cáo theo Product Type | Cần cho kế toán, phân tích lợi nhuận | 1-2 ngày |
| **P6** | N+1 guard trong B2/B3 (H8) — pre-load thay vì get_doc trong loop | Hiệu năng với BOM nhiều dòng | 1 ngày |
| **P7** | Global Variable cache (H6, H7) — cache Calculation Rule + Global Variable | Giảm ~50ms mỗi lần tính BOM | 0.5 ngày |

### PRIORITY 3 — MEDIUM (nên làm trong phase 2)

| # | Vấn đề | Impact | Effort |
|---|---|---|---|
| **P8** | Slug namespace (D6) — tránh bùng nổ số slug khi mở rộng ngành | Quan trọng khi triển khai đa ngành | 2-3 ngày |
| **P9** | "Test Data Source" UI (L7) — nút test trên Cost Bucket form | Giảm thời gian debug config | 1-2 ngày |
| **P10** | UOM Conversion (D9) — hỗ trợ đơn vị tính linh hoạt | Cần cho thép (cây), nhựa (cuộn) | 2-3 ngày |
| **P11** | Quotation bucket results dùng JSON/child table (A11) — thay vì nhiều custom fields | Giảm số lượng custom fields phải maintain | 1 ngày |
| **P12** | Error Recovery cho B4 (A10) — partial result khi 1 dòng lỗi | UX tốt hơn khi debug BOM | 1-2 ngày |

### PRIORITY 4 — LOW (có thể làm sau)

| # | Vấn đề |
|---|---|
| **P13** | Multi-currency trong BOM (D8) |
| **P14** | Warm-up cache hook (H10) |
| **P15** | Snapshot JSON index (H12) |
| **P16** | Print Format cho báo giá (E14) |
| **P17** | Dashboard KPI (E16) |
| **P18** | Auto Notification/Email (E13) |
| **P19** | Webhook/API public (E17) |
| **P20** | Translation/i18n (E15) |
| **P21** | FB `explain()` debug mode (F10) |
| **P22** | Deprecate AL Accessory Set timeline (A7) |
| **P23** | Deprecate CONSTANT type trong Calculation Rule (A8) |
| **P24** | Gộp Variable Dimension Mapping vào Pricing Dimension (A9) |
| **P25** | Dùng FB DotToSubscriptTransformer (F8) |

---

## PHẦN 8: KẾT LUẬN

### Tổng quan

Thiết kế v28.2 đã đi đúng hướng. Đây là một kiến trúc **có chiều sâu** — không chỉ giải quyết bài toán nhôm kính mà còn đặt nền móng cho nền tảng tính giá đa ngành. Các quyết định kiến trúc lớn đều hợp lý:

1. **Chọn Formula Builder làm engine** — đúng, thay vì tự build DAG + resolver
2. **Thin layer pattern** — AlumGlass chỉ code phần domain-specific
3. **Vứt bỏ formula_expr, chọn build_cross_ref_engine** — sửa sai kiến trúc từ review
4. **Config-driven validation** — AL Material Category + Pricing Dimension
5. **DataSourceResolver ủy thác cho FB** — giảm 90% queries, 82% code B2

### So sánh với giải pháp thay thế

| Tiêu chí | Tự code toàn bộ | Dùng Frappe core + FB (v28.2) |
|---|---|---|
| DAG engine | ~500 dòng code DAG + resolver | 0 dòng — FB lo |
| Snapshot/audit | ~300 dòng code snapshot | ~50 dòng wrapper — FB lo |
| Batch query tối ưu | ~200 dòng code batch + cache | ~80 dòng thin layer — FB lo |
| Formula editor | ~1000 dòng UI Monaco | 0 dòng — FB lo |
| Version control | ~200 dòng workflow code | Dùng core Workflow |
| **Tổng code phải viết** | **~2500 dòng** | **~400 dòng** |
| **Tổng code phải test** | **~2500 dòng** | **~400 dòng** |
| **Thời gian phát triển** | **~4-6 tháng** | **~4-6 tuần** |

### Bottom line

**Sẵn sàng triển khai.** Với 3 critical items (P1-P3) được giải quyết trước go-live, đây là một thiết kế enterprise-grade cho ngành nhôm kính và có khả năng mở rộng sang các ngành sản xuất khác.

*Review hoàn thành — 2026-07-27*
