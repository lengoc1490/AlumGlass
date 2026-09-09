# ĐÁNH GIÁ TOÀN DIỆN ALUMGLASS — Doctype, Field, Nghiệp vụ

> **Quan hệ với `BAN-FULL-A-Z.md`:** file đó đã xử lý rất kỹ 3 nhóm việc: (1) N+1 composite pricing, (2) 3 chỗ hardcode `"KINH"`/`"MAU_SAC"`/`"PHU_KIEN"`, (3) 3 năng lực mới cho `formula_builder` (`range_lookup`, `linked_doctype_field` mở rộng, `child_table_lookup`). Báo cáo này **không lặp lại** các việc đó — tôi đã đọc trực tiếp source code 2 repo (`AlumGlass` nhánh mặc định, `Formula-Builder` nhánh `develop`) để rà soát ở lớp khác: **kiến trúc doctype, field-level, và khoảng trống nghiệp vụ** trên toàn bộ 61 doctype của `alumglass` + custom field trên ERPNext core.
>
> Số liệu tham chiếu: 61 DocType (`bench` chuẩn) trải 12 module (`AL Master Data`, `AL Formula Rules`, `AL Bom Engine`, `AL Buying`, `AL Manufacturing`, `AL Construction`, `AL Account`, `AL Quality`, `AL Stock`, `AL AI Intelligence`, `AL Selling`, `AL HR` — 2 module cuối chưa có doctype riêng, chỉ custom field/override JS).

---

## MỤC LỤC

- **PHẦN A** — Phát hiện mức độ CAO (governance/rủi ro vận hành — chưa có trong BAN-FULL-A-Z)
- **PHẦN B** — Rà soát field theo module: thừa / nâng cấp / thiếu
- **PHẦN C** — Đề xuất doctype & nghiệp vụ còn thiếu để hoàn thiện end-to-end
- **PHẦN D** — Thứ tự triển khai đề xuất
- **PHẦN E** — Việc cần bạn xác nhận

---

# PHẦN A — Phát hiện mức độ CAO

### A.1 — Workflow đã viết đúng, nhưng **chưa từng được bật**

`alumglass/setup/install_workflows.py` định nghĩa đầy đủ 2 workflow thật (`AL BOM Version Workflow`, `AL Change Order Workflow`) với state/transition/role-gating rất chuẩn — đúng tinh thần "Workflow doctype thật thay vì `workflow_state` Select tự chế". Nhưng trong `hooks.py`, cả 2 nơi gọi đều bị comment:

```python
# install_workflows()
```

(dòng trong cả `_after_install` và `_after_migrate`). Hệ quả: 4 doctype đang dùng field `workflow_state` (`AL BOM Version`, `AL Change Order`, `AL Design Revision`, `AL Dynamic Item Rule Version`) **hiện tại `workflow_state` chỉ là 1 Select field bình thường** — bất kỳ ai có quyền write đều tự set thẳng `"Published"`/`"Approved"` mà không qua bước duyệt nào, kể cả nhảy cóc Draft → Published. Đây là khoảng trống kiểm soát nghiêm trọng vì `AL BOM Version.workflow_state == "Published"` là điều kiện kích hoạt *bất biến giá* (đã publish thì không sửa được snapshot giá nữa) — nhưng **ai được phép publish** lại không bị chặn.

**Đề xuất:** bỏ comment, gọi `install_workflows()` thật ở cả 2 hook. Test trước khi bật: xác nhận đủ role `AL BOM Manager` / `AL Technical Admin` / `AL Site Engineer` đã gán đúng người trên site thật (nếu chưa, bật lên sẽ khiến không ai bấm được nút chuyển trạng thái).

### A.2 — Toàn bộ `scheduler_events` bị tắt → cả cụm tính năng "cảnh báo/KPI" chết lâm sàng

```python
# scheduler_events = {
#     "daily": [...update_sales_kpi, check_price_change_alerts, check_low_stock_alerts, generate_daily_digest],
#     "weekly": [...deprecate_old_bom_versions],
#     "hourly": [...process_notification_queue],
# }
```

Toàn bộ khối này comment. Kết hợp với việc `AL Alert Config` (module `AL AI Intelligence`) có đầy đủ field `trigger_condition` (công thức FB), `cooldown_minutes`, `recipients`, `notification_channel` — nhưng **không có bất kỳ hàm nào trong code đọc và thực thi `AL Alert Config`** (tôi grep toàn repo, chỉ có `al_alert_config.py::validate()` kiểm tra cú pháp công thức lúc lưu, không có evaluator). Vậy toàn bộ doctype `AL Alert Config` hiện là **cấu hình cho một tính năng không tồn tại** — admin tạo alert, tưởng hệ thống sẽ cảnh báo, nhưng không có gì chạy.

**Đề xuất:**
- Nếu tính năng cảnh báo THỰC SỰ cần cho giai đoạn này → viết `alumglass/scheduled_tasks.py::evaluate_alert_configs` (đọc `AL Alert Config` active, resolve `trigger_condition` qua FB, so cooldown, gửi theo `notification_channel`) và bật `hourly`/`daily` tương ứng.
- Nếu CHƯA cần → **ẩn hẳn doctype `AL Alert Config` khỏi module list** (`hidden` trên doctype, hoặc bỏ khỏi fixtures) thay vì để nó "trông như đã xong" — tránh admin cấu hình nhầm vào tính năng chưa tồn tại. Đây là nguyên tắc chung nên áp dụng: **doctype nào chưa có code phía sau thì không nên hiển thị như đã hoàn thiện.**

### A.3 — `al_selling/doctype/custom_fields/custom_field_quotation.py` là dead code **xung đột** với custom field đang chạy thật

Đây là phát hiện quan trọng nhất ở lớp field-design. Có **2 nơi định nghĩa custom field cho `Quotation`**, mâu thuẫn nhau:

| | `alumglass/setup/custom_fields.py` (**ĐANG CHẠY** — được gọi từ `hooks.py::_after_install`/`_after_migrate`) | `al_selling/doctype/custom_fields/custom_field_quotation.py` (**KHÔNG được gọi ở đâu cả** — 0 kết quả grep tham chiếu ngoài chính nó) |
|---|---|---|
| Field trên **Quotation** (header) | `project`, `al_loss_reason` | `al_product_type`, `al_bom`, `al_bom_version`, `al_color`, `al_aluminum_origin`, `al_aluminum_thickness`, `al_aluminum_surface`, `al_loss_reason` |
| Field trên **Quotation Item** (dòng) | `al_bom`, `al_bom_version`, `al_bom_vars`, `al_config_snapshot`, `al_gia_ban`, `al_gia_vat`, `al_bom_result`, `al_calc_status`, `al_calc_job_id`, `al_calc_error` | *(không có)* |

Thiết kế **đang chạy** (item-level BOM/màu/nhôm) là đúng về nghiệp vụ — 1 báo giá thường có nhiều dòng sản phẩm khác `product_type`/màu/BOM nhau, nên các thuộc tính đó phải nằm ở **Quotation Item**, không phải header. File dead code làm ngược lại (đặt ở header), là thiết kế sai nếu từng được bật — may là chưa bao giờ chạy nên chưa gây hại, nhưng nó là "bẫy" cho người sau: ai đó thấy file, tưởng cần gọi `install_custom_fields()` của nó, sẽ tạo ra field trùng tên/khác nghĩa (`al_bom`, `al_bom_version`, `al_loss_reason` bị định nghĩa 2 lần ở 2 chỗ khác cấp).

**Đề xuất:** xoá hẳn `al_selling/doctype/custom_fields/custom_field_quotation.py` (và thư mục `custom_fields` rỗng còn lại nếu có) khỏi repo — không phải "chưa dùng tới", mà là **thiết kế đã bị thay thế + gây nhầm lẫn**, khác hẳn nhóm việc "chủ động không làm" ở PHẦN I của BAN-FULL-A-Z (những việc đó là code đang chạy, cân nhắc rồi giữ nguyên có chủ đích; đây là code chết, không ai cân nhắc giữ).

### A.4 — `AL Site Survey Item`: field tính toán không đánh dấu `read_only`

`width_deviation_mm`, `height_deviation_mm`, `within_tolerance`, `action_required` được `al_site_survey.py::_calculate_deviations()` tính lại **mỗi lần validate** (ghi đè giá trị cũ) — logic đúng. Nhưng trong JSON, các field này **không có `read_only=1`**, nên trên UI trông như ô nhập tay bình thường: người dùng gõ số vào, bấm Save, giá trị lại bị ghi đè âm thầm theo công thức thật — gây cảm giác "nhập không ăn"/sai lệch niềm tin vào form, dễ bị report nhầm là bug trong khi là do thiết kế field.

**Đề xuất:** set `read_only=1` cho 3 field trên (giữ `action_required` editable vì code chỉ auto-set khi rỗng, để kỹ sư có thể override thủ công — nên thêm `bold=1` hoặc mô tả rõ "Tự động, có thể sửa tay nếu cần" để phân biệt với 3 field kia).

Đồng thời, `_calculate_deviations()` đang lấy `survey_tolerance_mm` **luôn từ `AL Cutting Standard` có `applies_to="NHOM_PROFILE"`** (fallback cứng `10.0` nếu không có), bất kể dòng khảo sát đó là khung nhôm hay ô kính lắp cố định (structural glazing thường có dung sai khác). `AL Site Survey Item` không có field `category`/`applies_to` để engine chọn đúng bộ tiêu chuẩn. Nếu công ty chỉ khảo sát *lỗ mở tường* (luôn là kích thước khung nhôm) thì không sao — nhưng nên xác nhận, vì nếu sai sẽ âm thầm dùng sai dung sai cho mọi dòng.

### A.5 — `AL Change Order`: checkbox phê duyệt không bị giới hạn theo role

`al_change_order.py::validate()` chỉ chặn *set `workflow_state="Approved"` mà thiếu 1 trong 2 checkbox* — nhưng bản thân 2 checkbox `customer_approval`/`internal_approval` là field thường, **ai có quyền write `AL Change Order` cũng tự tick được cả hai** rồi tự chuyển trạng thái (nhất là khi A.1 chưa bật Workflow thật để giới hạn theo role). Về bản chất đây là kiểm soát tách biệt nhiệm vụ (segregation of duties) cho một tài liệu ảnh hưởng trực tiếp tới giá trị hợp đồng (`impact_cost`, tạo `revised_quotation`/`revised_sales_order`) — nên không thể chỉ dựa vào 1 checkbox tự khai.

**Đề xuất:** sau khi bật Workflow (A.1), thêm `permlevel` cho 2 field này (permlevel ≥ 1, chỉ role `AL Project Accountant`/`AL Technical Admin` mới có quyền ghi permlevel đó) — tách hẳn "người tạo change order" khỏi "người xác nhận đã được duyệt".

---

# PHẦN B — Rà soát field theo module

### B.1 — AL Master Data

**`AL Material Category`** — thiết kế tốt (đã được BAN-FULL-A-Z xác nhận là "chuẩn, nhất quán"), không cần sửa. Gợi ý bổ sung 1 field để dọn nốt phần còn lại của hardcode ngành: `default_uom_type` (Select: `LENGTH` / `AREA` / `PIECE` / `WEIGHT`) — hiện `has_weight`/`has_dimensions` chỉ là 2 cờ độc lập, không diễn tả được "kính tính theo m², nhôm tính theo mét dài, phụ kiện tính theo cái" một cách tường minh cho các module đọc sau này (cutting plan, material plan) đang tự đoán qua category code.

**`AL Variable Dimension Mapping`** — **thiếu field `is_active`**. Đây là bảng duy nhất trong `AL Master Data` không có cờ active/inactive (mọi bảng khác: `AL Color Standard`, `AL Glass Master`… không cần vì không "bật/tắt" theo thời gian, nhưng `AL Pricing Dimension`, `AL Product Type`, `AL Profile System`, `AL Cost Bucket`, `AL Cost Template`, `AL Warranty Policy` đều có `is_active`). Không có field này thì muốn ngừng dùng 1 mapping giá cũ phải **xoá hẳn record** — mất lịch sử, và nguy hiểm hơn: nếu mapping đó đã được `AL BOM Version` snapshot tham chiếu gián tiếp (qua tính giá tại thời điểm publish), xoá cứng sẽ không tái tạo lại được bối cảnh khi cần audit giá cũ.
→ **Đề xuất thêm:** `is_active` (Check, default 1) + sửa mọi query đọc mapping (đã liệt kê trong BAN-FULL-A-Z PHẦN B/D) thêm filter `is_active=1`.

**`AL Slug Library`** — cùng vấn đề: **thiếu `is_active`**. Slug là "từ điển dòng BOM" dùng lại nhiều nơi (`AL Bom Item.slug`, `AL Accessory Item.slug`) — khi 1 slug lỗi thời (đổi tên sản phẩm, gộp 2 slug thành 1), hiện tại chỉ có 2 lựa chọn xấu: sửa đè label (làm sai lịch sử BOM cũ đang tham chiếu) hoặc xoá (vỡ liên kết `Link` ở mọi BOM Item cũ). Thêm `is_active` cho phép "nghỉ hưu" 1 slug mà không phá dữ liệu lịch sử, và filter dropdown khi tạo `AL Bom Item` mới chỉ hiện slug active.

**`AL Variable Library`** — field `is_system` + `source_doctype`/`source_field` đang dùng `depends_on` đúng, nhưng hành vi runtime "parse số nếu được, giữ string nếu không" (nhắc tới trong PHẦN I của BAN-FULL-A-Z như một lý do trì hoãn migrate `system_variable_resolver.py`) **không có field nào mô tả tường minh** — hiện là hành vi ẩn trong code Python. Nếu sau này làm dự án migrate riêng đó (đúng như PHẦN I đã định), nên đưa hành vi này thành field khai báo: thêm `value_cast` (Select: `Auto` / `Force Number` / `Force String`, default `Auto`) trên `AL Variable Library` — biến 1 hành vi ngầm thành cấu hình tường minh, đúng tinh thần "data-driven, không đoán mò trong code" mà toàn bộ BAN-FULL-A-Z theo đuổi.

**`AL Color Standard`** — có cả `is_representative` và `is_default`, cả hai đều theo `applies_to` (Item Group), nhưng **không có ràng buộc "chỉ 1 màu `is_default=1` cho mỗi `applies_to`"** ở tầng code (`al_color_standard.py` hiện chỉ có `pass`, không override `validate()`). Nếu 2 màu cùng `applies_to="NHOM"` đều bật `is_default=1`, mọi nơi code đọc "màu mặc định của item group X" (`frappe.get_all(..., filters={"applies_to": X, "is_default": 1}, limit=1)` kiểu) sẽ **âm thầm lấy 1 trong 2** theo thứ tự DB — sai mà không ai biết.
→ **Đề xuất:** thêm `validate()` cho `AL Color Standard` chặn tạo/sửa thành `is_default=1` thứ 2 trong cùng `applies_to` (unique theo cặp field, Frappe không hỗ trợ unique composite qua JSON constraint nên phải code tay).

**`AL Glass Master`** — có `total_thick_mm`, hiệu năng nhiệt (`u_value`, `shgc`, `vlt`) — rất tốt cho báo giá kính cao cấp (Low-E, cách âm) nhưng **thiếu trọng lượng riêng** (`weight_kg_per_m2` — kính không tính theo kg/m như nhôm mà theo kg/m², field `Item.al_weight_per_m` hiện có trên `Item` là để dùng chung cho nhôm dạng thanh, không hợp với kính dạng tấm). Thiếu field này thì `AL Cutting Plan Glass`/vận chuyển/kết cấu (tải trọng lên hệ khung, giới hạn cẩu lắp) không có số liệu để tính — hiện đang là khoảng trống thật (tôi grep không thấy `weight` ở đâu trong luồng kính).
→ **Đề xuất thêm:** `weight_kg_per_m2` (Float), và cân nhắc `max_area_m2` (Float, giới hạn diện tích tấm an toàn theo tiêu chuẩn kính cường lực/dán an toàn — dùng để cảnh báo lúc nhập kích thước ô kính vượt ngưỡng, tránh thiết kế sai kỹ thuật lọt tới sản xuất).

**`AL Pricing Dimension`** — sau khi thêm `represents_color` (PHẦN D của BAN-FULL-A-Z), cấu trúc đã đủ tốt. Không cần sửa thêm.

### B.2 — AL Formula Rules

`AL Calculation Rule` (CONSTANT/THRESHOLD/LOOKUP) và `AL Dynamic Item Rule` (THRESHOLD/LOOKUP) là **2 doctype rất giống nhau về hình dạng** (cùng pattern threshold-rows/lookup-rows) nhưng tách riêng vì 1 cái trả về `Item` (chọn vật tư động) còn 1 cái trả về `Float`/giá trị số. Đây không phải "field thừa" mà là **trùng lặp kiến trúc ở mức doctype** — hợp lý về mặt dữ liệu (không thể chung 1 bảng vì kiểu kết quả khác nhau và `AL Dynamic Item Rule` có thêm cơ chế version/snapshot mà `AL Calculation Rule` không có), nhưng có 1 field đáng chú ý: **`AL Calculation Rule` không có version/snapshot** như `AL Dynamic Item Rule Version`, trong khi cả hai đều ảnh hưởng trực tiếp tới giá bán đã publish trong `AL BOM Version` (qua `cost_template_snapshot`). Nếu 1 `AL Calculation Rule` (vd rule tính phụ phí màu) bị sửa SAU khi 1 báo giá đã Published, giá trị cũ trong cost_template_snapshot vẫn đúng (đã snapshot), nhưng **không có cách nào audit "rule này lúc snapshot có nội dung gì"** như `AL Dynamic Item Rule Version.rule_snapshot_json` cho phép. Việc này không khẩn cấp (giá đã snapshot vào JSON của BOM Version rồi) nhưng nếu cần audit ngược ("tại sao lúc đó ra giá này") sẽ khó hơn.
→ **Đề xuất (mức thấp, cân nhắc theo nhu cầu audit thật):** nếu nghiệp vụ cần truy vết thay đổi rule tính giá theo thời gian, thêm `track_changes=1` (hiện `AL Calculation Rule` **đã có** `track_changes=1` — tốt, không cần version doctype riêng, Version log của Frappe đã đủ).

`AL Quantity Calc Method.calc_fn` (Python Lambda, Small Text) — đây là **field cho phép nhập code Python thực thi trực tiếp** vào công thức tính số lượng. Không thấy field nào giới hạn quyền sửa (không có `permlevel`) hay ghi log ai sửa lần cuối ngoài `track_changes` mặc định của Frappe. Vì đây tương đương "thực thi mã tuỳ ý" (RCE risk nếu role bị lộ/mở rộng nhầm), nên:
→ **Đề xuất:** giới hạn quyền sửa `AL Quantity Calc Method` chỉ cho `AL Technical Admin` (kiểm tra lại trong `install_roles_and_permissions()` xem đã giới hạn đúng chưa — nên xác nhận, vì đây là field rủi ro bảo mật thật chứ không chỉ là gợi ý thiết kế).

### B.3 — AL Bom Engine

**`AL Bom Item`** — doctype trung tâm, đã rất đầy đủ (30+ field chia 8 section). Có 1 field đáng cân nhắc bỏ/gộp: `ctx_inject_prefix` — tên field rất kỹ thuật ("CTX Inject Prefix") lộ thẳng chi tiết triển khai engine ra UI mà kỹ sư BOM (không phải dev) phải nhìn thấy và điền đúng mỗi khi `category.requires_ctx_inject_prefix=1`. Đây không phải field thừa về mặt dữ liệu, nhưng là **nợ UX** — nên thêm `description` giải thích bằng ngôn ngữ nghiệp vụ (vd "Tiền tố để engine tách biến ngữ cảnh khi 1 slug xuất hiện nhiều panel trong cùng 1 BOM — vd 'PANEL1_', 'PANEL2_'") thay vì để trống, tránh nhân sự nghiệp vụ điền sai vì không hiểu field dùng để làm gì.

**`AL Accessory Item`** (child table của `AL Accessory Set`) và **`AL Bom Item`** có field trùng gần như 1:1 ở phần "cơ bản": `slug`, `item_code`, `qty`/`qty_formula`, `calc_pattern`, `cost_bucket`, `unit_price`, `default_color`, `supplier_location`, `install_position`, `note`. Đây là **trùng lặp kiến trúc có chủ đích** (accessory không cần `item_selection_mode`/Rule/Formula phức tạp như BOM item chính) — hợp lý, không đề xuất gộp 2 doctype (sẽ làm phức tạp hoá phần đơn giản). Nhưng gợi ý nhỏ: `AL Accessory Item` có cả `qty` (Float, "Qty cố định") và `qty_formula` (Small Text) cùng lúc — 2 field cùng mục đích "số lượng" nhưng theo 2 cơ chế (cố định vs công thức), **không có field nào chỉ định đang dùng cơ chế nào** (khác `AL Bom Item` có hẳn `item_selection_mode` Select rõ ràng: Fixed/Rule/Formula). Hiện chắc engine đang tự đoán "có `qty_formula` thì ưu tiên formula, không thì dùng `qty`" — nếu đúng vậy thì nên **thêm 1 Select `qty_mode` (Fixed/Formula)** tường minh, tránh trường hợp cả 2 field cùng có giá trị (ai đó nhập nhầm) mà không rõ cái nào thắng.

**`AL Bom Set`** — có field `version` (Data, tự do nhập text) **song song** với cơ chế `AL BOM Version` (doctype riêng, có `workflow_state`, snapshot, immutability guard) ở tầng `AL BOM`. Hai khái niệm "version" tồn tại ở 2 tầng khác nhau (`AL Bom Set.version` là version của *cấu trúc set*, `AL BOM Version` là version của *toàn bộ báo giá đã snapshot*) — dễ gây nhầm lẫn tên gọi dù mục đích khác nhau. 
→ **Đề xuất:** đổi label `AL Bom Set.version` thành **"Structure Revision"** hoặc tương tự (không đổi fieldname, không breaking) để phân biệt rõ với `AL BOM Version`, tránh người dùng tưởng đây là nơi quản lý version báo giá.

**`AL Cost Bucket`** — `source_type` Select liệt kê 8 loại (`aggregate_from_items`, `formula`, `doctype_query`, `custom_function`, `constant`, `pipeline`, `conditional`, `fallback_chain`) khớp đúng các source type của `formula_builder` core — thiết kế tốt, không đổi. Ghi nhận: sau khi PHẦN F/G/H của BAN-FULL-A-Z thêm `range_lookup`/`child_table_lookup`, nên **cập nhật luôn Select options này** nếu `AL Cost Bucket` cũng cần dùng 2 source type mới đó trực tiếp (hiện Select là danh sách cứng, không tự động đồng bộ với core registry — mismatch tiềm ẩn giữa `formula_builder` cho phép và UI cho chọn).

**`ConfigSnapshot`** — trùng tên khá gần với `AL BOM Version` (cả 2 đều "chụp lại trạng thái tại 1 thời điểm") nhưng mục đích khác: `ConfigSnapshot` chụp **kết quả tính toán 1 lần gọi** (`inputs_json`/`result_json`, gắn `quotation_item_name`), còn `AL BOM Version` chụp **cấu hình BOM** dùng để tính. Tên doctype `ConfigSnapshot` không theo convention `AL ` prefix như 60 doctype còn lại — dễ gây nhầm khi tìm kiếm/báo cáo, và là 1 trong số rất ít doctype không có is_active/mô tả rõ vòng đời (bao lâu thì dọn dữ liệu cũ?).
→ **Đề xuất:** đổi tên doctype thành `AL Config Snapshot` (rename doctype trong Frappe có công cụ hỗ trợ, không mất dữ liệu) để nhất quán namespace; đồng thời cân nhắc thêm cơ chế dọn dẹp định kỳ (weekly scheduler — hiện đang tắt theo A.2) vì bảng này tăng trưởng theo mỗi lần tính giá, không có TTL/archive.

### B.4 — AL Buying

**`AL Material Plan`** — không có field `status`/`workflow_state` nào cả (so với hầu hết doctype khác đều có). Một kế hoạch vật tư (MRP run) không phân biệt được "đang nháp / đã duyệt / đã chuyển thành PO" — `AL Material Plan Item` có `purchase_order` (Link) để biết dòng nào đã lên PO, nhưng ở tầng *plan* tổng thể lại không có field tổng hợp trạng thái, phải suy ra bằng cách đếm dòng con.
→ **Đề xuất thêm trên `AL Material Plan`:** `status` (Select: `Draft` / `Reviewed` / `Partially Ordered` / `Fully Ordered` / `Cancelled`), có thể tính tự động (`on_update`, đếm dòng con có/không `purchase_order`) thay vì nhập tay.

**`AL Supplier Price List Item`** — có `fx_change_pct`/`base_price_change_pct` (read_only, chắc chắn tính tự động so với kỳ trước) nhưng **không có field `previous_price`** để hiển thị cạnh — người xem `%` thay đổi mà không thấy số cũ để đối chiếu là thiếu ngữ cảnh. 
→ **Đề xuất:** thêm `previous_unit_price` (Currency, read_only) hiển thị cạnh `unit_price` để so sánh trực quan, không phải tính nhẩm ngược từ %.

**`AL Cost Variance`** và **`AL Project Profitability Snapshot`** (module `AL Account`) — 2 doctype có field chồng lấn đáng kể: cả 2 đều có `project`, khoảng `estimated`/`actual`/`variance`. Khác biệt: `AL Cost Variance` theo `cost_bucket` + `period_from/to` (chi tiết theo hạng mục & kỳ), `AL Project Profitability Snapshot` là tổng theo `project` + `snapshot_date` (tổng quan toàn dự án). Về nguyên tắc, `AL Project Profitability Snapshot.total_actual_cost`/`total_estimated_cost` **có thể tính bằng cách SUM `AL Cost Variance` theo project** — nếu đúng vậy thì 2 field này ở Snapshot là **dữ liệu phái sinh nên là read-only tính tự động** (hiện JSON không thấy `read_only` — có thể đang cho nhập tay, dễ lệch với tổng thật của `AL Cost Variance`).
→ **Đề xuất:** xác nhận nguồn dữ liệu của `AL Project Profitability Snapshot` — nếu là tổng hợp từ `AL Cost Variance`, đặt `read_only=1` + viết job tính tự động (gộp cùng chỗ với scheduler ở A.2); nếu là 2 nguồn độc lập (vd Snapshot lấy thẳng từ GL, Cost Variance lấy từ Cost Bucket ước tính) thì giữ nguyên nhưng nên ghi rõ trong `description` field để người đọc report không tưởng nhầm 2 số phải luôn khớp nhau.

### B.5 — AL Manufacturing

`AL Cutting Standard` dùng `applies_to` Select (`NHOM_PROFILE`/`KINH`) để rẽ nhánh field hiển thị (`depends_on`) — đúng nguyên tắc data-driven của toàn hệ thống, tốt. Ghi nhận nhất quán với khuyến nghị ở A.4: cơ chế `applies_to` này đã tồn tại sẵn ở `AL Cutting Standard`, nên việc thêm `category`/`applies_to` cho `AL Site Survey Item` (A.4) hoàn toàn có thể tái dùng đúng pattern này, không phải nghĩ mới.

`AL Glass Cutting Item`/`AL Cutting Plan Item` — có `offcut_reusable` (Check) nhưng **không có ngưỡng tối thiểu để coi là "reusable"** ở cấp dòng — ngưỡng nằm ở header (`min_offcut_reusable_mm` trên `AL Cutting Plan Aluminum`/`Glass`), vậy `offcut_reusable` chắc là **field tính tự động theo ngưỡng header**, không phải nhập tay — nên set `read_only=1` cho field này (hiện JSON không có), cùng logic với A.4.

### B.6 — AL Construction

**`AL Punchlist Item`** — có `resolved_by`, `verified_by` (ai đã xử lý/xác nhận) nhưng **thiếu `assigned_to`** (ai *cần* xử lý, trước khi resolved) — với nghiệp vụ nghiệm thu công trình, punchlist luôn cần giao việc rõ ràng ngay khi phát sinh (severity `MAJOR`/`CRITICAL` cần biết ai đang chịu trách nhiệm), không thể đợi tới lúc `resolved_by` mới có tên người.
→ **Đề xuất thêm:** `assigned_to` (Link → Employee, hoặc User nếu muốn gán cho cả đối tác ngoài), đặt cạnh `due_date`.

**`AL Handover Acceptance`** — có `customer_signature` (Attach Image) nhưng không có `company_representative_signature` tương ứng dù có field `company_representative` (Link → Employee) song song với `customer_representative` (Data, không phải Link — bất nhất: khách hàng là Data tự do, đại diện công ty là Link chuẩn, hợp lý vì khách không có record Employee, nhưng có thể cân nhắc Link → Contact nếu khách hàng đã có trong CRM để tránh gõ tay tên lặp lại nhiều lần).
→ **Đề xuất:** thêm `company_representative_signature` (Attach Image) để biên bản bàn giao có đủ 2 chữ ký, khớp thông lệ pháp lý của biên bản nghiệm thu xây dựng.

**`AL Installation Team`** — có `capacity_m2_per_day` (Float, năng lực tĩnh) nhưng **không có gì thể hiện lịch làm việc/tải hiện tại** — khi tạo `AL Installation Order` mới, không có cách nào (ở tầng data) biết đội đã kín lịch tới ngày nào. Đây không phải "field thừa/thiếu" đơn giản mà là khoảng trống nghiệp vụ lớn hơn — xem đề xuất doctype mới ở PHẦN C.3.

### B.7 — AL Quality / AL Stock / AL AI Intelligence

**`AL Warranty Policy`** — chỉ có **1 field `warranty_months` duy nhất cho toàn bộ sản phẩm**. Đây là khoảng trống nghiệp vụ rõ ràng nhất trong toàn bộ audit: ngành nhôm kính trên thực tế **luôn bảo hành khác thời hạn theo cấu kiện** — khung nhôm/kết cấu thường 5-10 năm, kính (đặc biệt kính hộp/Low-E) 3-5 năm, phụ kiện (bản lề, khóa, ray trượt) 1-2 năm, keo silicone/gioăng cao su 1 năm. Field `Warranty Claim.al_defect_category` (custom field, Select: `GLASS_BREAK`/`SEAL_FAIL`/`HARDWARE`/`LEAK`/`COLOR_FADE`/`STRUCTURAL`) đã sẵn có 6 hạng mục lỗi khác nhau — nhưng **`AL Warranty Policy` không có cách nào khai báo thời hạn khác nhau cho từng hạng mục đó**, chỉ có 1 con số chung. Xem đề xuất chi tiết ở PHẦN C.2.

**`AL Project Warehouse Map`** — `is_temporary` + `activation_date`/`deactivation_date` — thiết kế gọn, đủ dùng. Không cần sửa.

**`AL AI Interaction Log`/`AL AI Suggestion Log`** — 2 doctype log tốt, nhưng như đã nói ở A.2, phụ thuộc vào 1 hệ thống AI suggestion chưa thấy code sinh ra suggestion nào (chỉ thấy doctype lưu log, không thấy nơi nào `frappe.get_doc("AL AI Suggestion Log").insert()` được gọi ngoài chính khai báo doctype) — cùng dạng "doctype cho tính năng chưa nối dây" như A.2, nên gộp chung vào cùng 1 lần rà soát "tính năng AI có thật đang chạy phần nào".

### B.8 — Custom field trên ERPNext core

Đã liệt kê nguyên khối `setup/custom_fields.py` ở PHẦN A.3. Bổ sung field-level trên phần đang chạy thật:

- **`Item`**: `al_is_color_variable` (Check) — tên field hơi mơ hồ (là "Item này ĐẠI DIỆN cho 1 biến thể màu" hay "Item này CÓ biến thể theo màu"?). Nên đổi `label` thành rõ nghĩa hơn, vd **"Represents a Color Variant?"**, và thêm `description` giải thích quan hệ với `AL Variable Dimension Mapping` (PHẦN D của BAN-FULL-A-Z) — 2 cơ chế này cùng nói về "màu" nhưng ở 2 tầng khác nhau (`Item.al_is_color_variable` = thuộc tính của 1 SKU cụ thể; `AL Pricing Dimension.represents_color` = thuộc tính của 1 dimension trong công thức giá) — nếu không ghi rõ, dev sau dễ nhầm 2 cơ chế là một.
- **`Quotation Item.al_bom_result`** (JSON, read_only) lưu **toàn bộ** kết quả BOM (buckets + cost template + lines) — đây là JSON rất lớn lưu trên every dòng báo giá, tăng trưởng nhanh theo số báo giá × số dòng. Không phải field thừa (cần cho việc hiển thị lại kết quả không phải tính lại), nhưng nên xác nhận đã có chiến lược archive/nén cho báo giá cũ (> 1-2 năm) chưa — nếu chưa, đây sẽ là bảng `tabQuotation Item` phình to nhanh nhất hệ thống.

---

# PHẦN C — Đề xuất doctype/nghiệp vụ còn thiếu

### C.1 — Chuỗi truy vết end-to-end (traceability) chưa khép kín

Đi hết toàn bộ 61 doctype, chuỗi nghiệp vụ chính là:

```
Quotation Item (al_bom_version) → Sales Order → Work Order (al_production_order_bridge)
   → AL Cutting Plan Aluminum/Glass → AL Production Order Bridge → Delivery Note
   → AL Installation Order → AL Handover Acceptance → Warranty Claim
```

Chuỗi này **đã nối được từng cặp liền kề** (mỗi doctype đều có Link tới doctype ngay trước/sau), nhưng **không có 1 field/report nào cho phép từ 1 `Quotation Item` truy ngay ra `AL Installation Order`/`AL Handover Acceptance` cuối chuỗi** mà không phải nhảy qua 4-5 bước Link thủ công — vì mỗi Link chỉ trỏ 1 chiều (vd `AL Handover Acceptance.installation_order` trỏ ngược lên, nhưng `Quotation Item` không có `al_installation_order` xuôi xuống). Với đặc thù dự án lắp đặt kéo dài nhiều tháng, đây là nhu cầu tra cứu rất thường xuyên ("báo giá này khách đã bàn giao chưa, bảo hành tới khi nào").

**Đề xuất:** không thêm Link 2 chiều thủ công ở mọi doctype (dễ lệch khi có nhiều Sales Order/Installation Order cho cùng Project), mà thêm 1 **Report/Dashboard doctype ảo** (`AL Project Timeline` — không lưu dữ liệu, chỉ là Script Report hoặc Query Report join `project` qua các bảng) hiển thị theo `project`: Quotation → Sales Order → Work Order → Installation Order → Handover → Warranty Claim, mỗi cột 1 trạng thái/ngày. Rẻ hơn nhiều so với thêm field Link ở khắp nơi, và đúng hướng vì `project` (Link chuẩn ERPNext) đã có mặt xuyên suốt ở gần như mọi doctype module `AL Construction`/`AL Account`/`AL Buying` rồi — chỉ thiếu 1 lớp tổng hợp nhìn theo `project`.

### C.2 — Bảo hành theo cấu kiện (mở rộng `AL Warranty Policy`)

Như đã nêu ở B.7, đề xuất thêm **child table mới** `AL Warranty Coverage Row` gắn vào `AL Warranty Policy`:

| Field | Kiểu | Ghi chú |
|---|---|---|
| `defect_category` | Select (đồng bộ options với `Warranty Claim.al_defect_category`: `GLASS_BREAK`/`SEAL_FAIL`/`HARDWARE`/`LEAK`/`COLOR_FADE`/`STRUCTURAL`) | Bắt buộc |
| `coverage_months` | Int | Bắt buộc — thời hạn riêng cho hạng mục này |
| `coverage_condition` | Small Text | Điều kiện loại trừ (vd "không áp dụng nếu do va đập ngoại lực") |

`AL Warranty Policy.warranty_months` (field hiện có) giữ nguyên làm **giá trị mặc định/tổng quát** khi 1 `defect_category` chưa được khai báo riêng trong bảng con — không breaking change, chỉ additive. Khi xử lý `Warranty Claim`, code tra `AL Warranty Coverage Row` theo `al_defect_category` trước, không có thì fallback `warranty_months` header — đúng pattern `fallback_chain` đã dùng nhất quán trong toàn hệ thống (PHẦN H.2 của BAN-FULL-A-Z).

### C.3 — Năng lực & lịch đội thi công

`AL Installation Team.capacity_m2_per_day` hiện là con số tĩnh, không phản ánh lịch thực tế. Đề xuất **không** làm 1 module lịch phức tạp (quá tốn cho quy mô hiện tại), mà thêm 1 doctype nhẹ:

**`AL Installation Team Booking`** (không phải child table — độc lập vì 1 đội có thể được đặt lịch từ nhiều `AL Installation Order` chồng lấn cần phát hiện xung đột):
- `installation_team` (Link, reqd)
- `installation_order` (Link, reqd)
- `booked_date` (Date, reqd)
- `estimated_m2` (Float) — dùng để cộng dồn so với `capacity_m2_per_day`
- `status` (Select: `Planned`/`Confirmed`/`Done`)

Logic: khi tạo/sửa `AL Installation Order` với `planned_start_date`/`planned_end_date`, sinh các dòng `AL Installation Team Booking` tương ứng; validate cảnh báo (không nhất thiết chặn cứng) nếu tổng `estimated_m2` trong ngày của 1 đội vượt `capacity_m2_per_day`. Đây là mức tối thiểu để trả lời câu hỏi rất thực tế "đội A có rảnh tuần sau không" mà hiện tại phải hỏi miệng/xem lịch giấy.

### C.4 — Phê duyệt cho `AL Material Plan`

Nối với B.4: sau khi thêm `status`, nên đi kèm 1 bước duyệt tối thiểu trước khi cho phép tạo Purchase Order từ `AL Material Plan Item` — hiện không có gì chặn 1 nhân viên mua hàng tự tạo PO thẳng từ material plan chưa ai duyệt. Không cần Workflow doctype riêng (dùng ngay field `status` + 1 field `approved_by`/`approved_on` đơn giản là đủ ở quy mô này, tránh over-engineering).

### C.5 — UOM/đơn vị đo nhất quán giữa nhôm và kính

Tổng hợp từ B.1 (Material Category) và B.1 (Glass Master weight): hệ thống hiện có 2 đơn vị trọng lượng khác nhau cho 2 vật liệu chính (`Item.al_weight_per_m` = kg/mét dài cho nhôm thanh, đề xuất `AL Glass Master.weight_kg_per_m2` = kg/m² cho kính) nhưng **không có field nào ở `AL Material Category` khai báo "category này dùng đơn vị trọng lượng nào"** để các báo cáo tổng hợp trọng lượng công trình (phục vụ tính tải kết cấu, chi phí vận chuyển) biết công thức nào áp dụng cho dòng nào. Đây chính là field `default_uom_type` đã đề xuất ở B.1 — nhắc lại ở đây vì nó là điều kiện tiên quyết để C.3 (ước lượng theo m² hay theo mét) và mọi báo cáo tổng trọng lượng sau này tính đúng.

---

# PHẦN D — Thứ tự triển khai đề xuất

```
Nhóm 0 — Không tốn code, chỉ bật/xoá (làm NGAY, rủi ro thấp nhất):
  1. A.3 — Xoá custom_field_quotation.py (dead code, xung đột)
  2. A.2 (nhánh ẩn) — Ẩn "AL Alert Config"/AI Suggestion nếu chưa định làm evaluator ngay
  3. A.4 — Thêm read_only=1 cho field tính toán (Site Survey, Glass Cutting Item)

Nhóm 1 — Governance, cần xác nhận role trước khi bật (A.1, A.5):
  4. A.1 — Bật install_workflows() — CẦN xác nhận role đã gán đúng người (mục E)
  5. A.5 — permlevel cho customer_approval/internal_approval

Nhóm 2 — Bổ sung field additive, an toàn (không đổi hành vi cũ):
  6. B.1 — is_active cho AL Variable Dimension Mapping + AL Slug Library
  7. B.1 — weight_kg_per_m2 (+ max_area_m2) cho AL Glass Master
  8. B.6 — assigned_to cho AL Punchlist Item; company_representative_signature cho AL Handover Acceptance
  9. B.4 — previous_unit_price cho AL Supplier Price List Item

Nhóm 3 — Nghiệp vụ mới (thiết kế + xác nhận nghiệp vụ thật trước khi code):
  10. C.2 — AL Warranty Coverage Row (bảo hành theo cấu kiện) — CẦN xác nhận thời hạn thật theo hạng mục
  11. C.4 — status/approval cho AL Material Plan
  12. C.3 — AL Installation Team Booking
  13. C.1 — AL Project Timeline (report tổng hợp)

Nhóm 4 — Cần quyết định trước (ảnh hưởng lớn hơn, nên bàn với đội vận hành thật):
  14. A.2 (nhánh xây dựng) — evaluator thật cho AL Alert Config + bật scheduler
  15. B.4 — làm rõ nguồn dữ liệu AL Project Profitability Snapshot vs AL Cost Variance
```

Nhóm 0-2 không phụ thuộc BAN-FULL-A-Z, làm song song được. Nhóm 3-4 nên làm SAU khi PHẦN B/C/D/E của BAN-FULL-A-Z đã merge (một số đụng chung file `bom_orchestrator.py`/`al_bom_item.py`).

---

# PHẦN E — Việc cần bạn xác nhận

- [ ] **A.1 (quan trọng nhất):** trước khi bật `install_workflows()`, xác nhận trên site thật đã gán đúng người vào role `AL BOM Manager` / `AL Technical Admin` / `AL Site Engineer` — nếu chưa gán ai, bật lên sẽ khiến không ai bấm được nút chuyển trạng thái (khoá cứng quy trình).
- [ ] **A.2:** quyết định hướng cho `AL Alert Config`/`AL AI Suggestion Log` — làm evaluator thật ngay, hay tạm ẩn khỏi UI tới khi làm.
- [ ] **A.3:** xác nhận không nơi nào (kể cả nhánh/branch khác) đang import `al_selling.doctype.custom_fields.custom_field_quotation` trước khi xoá hẳn file.
- [ ] **A.4:** xác nhận khảo sát công trình hiện tại chỉ đo lỗ mở khung nhôm (dùng chung 1 dung sai `NHOM_PROFILE`), hay cần tách dung sai riêng cho ô kính cố định.
- [ ] **C.2:** xác nhận thời hạn bảo hành thật theo từng hạng mục (khung/kính/phụ kiện/keo) để seed `AL Warranty Coverage Row` đúng ngay từ đầu, tránh 1 vòng sửa lại như trường hợp `"PK"` vs `"PHU_KIEN"` đã gặp ở PHẦN E của BAN-FULL-A-Z.
- [ ] **B.4:** xác nhận `AL Project Profitability Snapshot.total_actual_cost`/`total_estimated_cost` hiện đang nhập tay hay đã có job nào tính tự động mà tôi chưa tìm thấy (tôi grep không thấy nơi nào set giá trị 2 field này ngoài chính doctype form).
