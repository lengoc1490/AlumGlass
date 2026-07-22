# KẾ HOẠCH TRIỂN KHAI CHI TIẾT — ALUMGLASS (THEO CHUẨN v27_FULL, GỘP v26 + v27)
## Sản phẩm mẫu tham chiếu: Cửa đi 2 cánh mở quay + ô kính cố định trên (CDMQ-2C-TRANSOM)

> Tài liệu này là **kế hoạch thực thi (execution plan)** — trả lời câu hỏi "làm gì trước, làm gì sau, ai làm, xong khi nào biết là đúng" — dựa trên tài liệu kỹ thuật gốc `AlumGlass_v27_FULL.md` (nguồn chân lý duy nhất về *thiết kế*). Mọi task dưới đây đều tham chiếu ngược lại đúng mục số của tài liệu đó — không lặp lại nội dung kỹ thuật ở đây, chỉ tổ chức thành **trình tự thi công + tiêu chí nghiệm thu (Definition of Done)** cho từng giai đoạn.
>
> **Nguyên tắc tổ chức:** DocType/dữ liệu nào bị tham chiếu (Link) bởi DocType khác thì phải tạo xong trước — đúng thứ tự ở mục 8.2 của `v27_FULL`. Kế hoạch dưới đây bám sát thứ tự đó, gộp thành 16 giai đoạn (G0→G15), nhóm theo tuần làm việc.

---

## MỤC LỤC

1. Tổng quan phạm vi & giả định
2. Sơ đồ tổng thể 16 giai đoạn (bảng theo tuần)
3. Ma trận phụ thuộc — DocType nào cần DocType nào
4. Chi tiết từng giai đoạn (G0 → G15): mục tiêu, việc phải làm, đầu ra, DoD, rủi ro
5. Kế hoạch kiểm thử tổng hợp (Test Plan)
6. Cổng nghiệm thu cuối (UAT) — tiêu chí "coi như xong"
7. Kế hoạch rủi ro & phương án dự phòng
8. Checklist tổng hợp một trang (in ra dùng khi thi công)

---

## 1. TỔNG QUAN PHẠM VI & GIẢ ĐỊNH

- **Phạm vi:** triển khai đầy đủ hệ thống tính BOM/giá bán cho 1 sản phẩm mẫu (CDMQ-2C-TRANSOM) trên nền Frappe/ERPNext + app Formula Builder (đã có sẵn) + app AlumGlass (xây mới). Kết quả cuối: chạy được `calculate_bom()` cho báo giá và ra đúng **GIA_VAT = 22,717,289đ** với input chuẩn ở mục 7.1 của `v27_FULL`.
- **Giả định về nguồn lực:** 1 backend dev (Frappe) làm chính, có thể cần thêm 1 người nghiệp vụ (kỹ thuật nhôm kính) để chốt số liệu master data thật (giá, trọng lượng, offset) và 1 người kiểm thử (QA) ở giai đoạn cuối. Ước lượng thời gian dưới đây tính cho **1 dev full-time**; có thể rút ngắn nếu làm song song.
- **Không nằm trong phạm vi kế hoạch này:** thiết kế UI/UX chi tiết cho Quotation, workflow duyệt giá, phân quyền — đây là các việc nghiệp vụ ERPNext chuẩn, làm sau khi lõi tính toán đã chạy đúng.
- **Điều kiện tiên quyết trước khi bắt đầu G0:** app `formula_builder` đã có sẵn (không tự viết), đã xác nhận được cơ chế đăng ký hàm custom (`extra_funcs`/`safe_funcs`) mà nó hỗ trợ — nếu chưa rõ, đây là việc đầu tiên cần làm rõ với đội phát triển Formula Builder trước khi qua G9.

---

## 2. SƠ ĐỒ TỔNG THỂ 16 GIAI ĐOẠN

| Giai đoạn | Tên | Thời gian ước tính | Tuần | Tham chiếu `v27_FULL` |
|---|---|---|---|---|
| G0 | Chuẩn bị môi trường & app | 0.5 ngày | Tuần 1 | mục 8.1 |
| G1 | Core ERPNext: Item Group, Brand | 0.5 ngày | Tuần 1 | mục 2.1–2.2 |
| G2 | DocType nền tảng: Color Standard, Calculation Rule, Formula Global Variable | 1 ngày | Tuần 1 | mục 2.3–2.5 |
| G3 | DocType cấp 2: Glass Master, Dynamic Item Rule (+Version), Slug Library, Quantity Calc Method | 1.5 ngày | Tuần 1 | mục 2.8–2.11 |
| G4 | Item + Item Price + Custom Fields + Server Script validate | 1.5 ngày | Tuần 1–2 | mục 2.6–2.7, 8.3, 8.4 |
| G5 | Cost Bucket & Cost Template | 1 ngày | Tuần 2 | mục 2.12, 2.14 |
| G6 | Formula Set `BOM_LINE` (cấu hình trong Formula Builder) | 0.5 ngày | Tuần 2 | mục 2.13 |
| G7 | Variable Set, Profile Line/Set, BOM, BOM Version | 2 ngày | Tuần 2 | mục 2.15, mục 3, mục 8.2 (9–13) |
| G8 | ConfigSnapshot DocType | 0.5 ngày | Tuần 2 | mục 8.2 (14) |
| G9 | Code: `formula_handlers.py` (`lookup_calc_pattern`, `price_lookup`, `glass_lookup`) + đăng ký `extra_funcs` | 1.5 ngày | Tuần 3 | mục 6, mục 8.7 |
| G10 | Code: `BomOrchestrator` (11 phase B0→B8) + API `calculate_bom` | 3.5 ngày | Tuần 3 | mục 5, mục 8.6 |
| G11 | Client Script gắn UI (nút "Tính giá" trên Quotation Item) | 0.5 ngày | Tuần 4 | mục 8.6 |
| G12 | Script seed demo data (`seed_demo_data.py`) | 1 ngày | Tuần 4 | mục 8.5 |
| G13 | Kiểm thử đơn vị & đối chiếu số liệu (GIA_VAT, sensitivity) | 2 ngày | Tuần 4 | mục 5–7, mục 9.3 |
| G14 | Kiểm thử hiệu năng (N+1, tải đồng thời) | 1 ngày | Tuần 4 | mục 9.3 (dòng cuối) |
| G15 | UAT nghiệp vụ + đào tạo + go-live | 2 ngày | Tuần 5 | mục 6, toàn tài liệu |

**Tổng ước tính: ~19.5 ngày làm việc (~4 tuần) cho 1 dev full-time**, chưa tính thời gian chờ phản hồi nghiệp vụ (giá thật, offset thật khác với số liệu mẫu trong tài liệu).

> Có thể rút gọn còn ~3 tuần nếu G2–G8 (thuần nhập master data, không cần code) được giao cho 1 người khác làm song song với G9–G10 (code) — vì 2 nhóm việc này độc lập nhau cho tới khi cần chạy thử ở G13.

---

## 3. MA TRẬN PHỤ THUỘC — DOCTYPE NÀO CẦN DOCTYPE NÀO

Đây là lý do thứ tự G0→G8 không được đảo — mỗi dòng bên dưới liệt kê DocType nào phải **có dữ liệu trước** thì DocType ở cột trái mới tạo/nhập được:

| DocType cần tạo | Phụ thuộc (phải có trước) |
|---|---|
| AL Color Standard | Item Group (`applies_to`) |
| Item (profile cụ thể) | Item Group, Brand |
| Item Price | Item, AL Color Standard (qua custom field) |
| AL Glass Master | – (độc lập) |
| AL Dynamic Item Rule | Item (result_item trỏ tới Item cụ thể) |
| AL Slug Library | – (độc lập) |
| AL Quantity Calc Method | – (độc lập) |
| AL Cost Bucket | – (độc lập, nhưng cây cha-con phải tạo LEAF trước AGGREGATE hoặc cho phép Link rỗng tạm) |
| AL Cost Template | AL Cost Bucket, Formula Global Variable (`$NC_SX_PCT`...) |
| Formula Set `BOM_LINE` | – (độc lập, chỉ cần Formula Builder đã cài) |
| AL Variable Set | AL Color Standard (Link cho `mau_nhom`) |
| AL Profile Line (child) | AL Slug Library, Item, AL Dynamic Item Rule, AL Cost Bucket, AL Quantity Calc Method |
| AL Profile Set | AL Profile Line |
| AL BOM | AL Profile Set, AL Variable Set, AL Cost Template |
| AL BOM Version | AL BOM |
| ConfigSnapshot | AL BOM Version (lưu `bom_version_id`) |

**Hệ quả cho kế hoạch:** nếu có 2 người làm song song, người A lo cột trái theo đúng thứ tự trên, người B chỉ nên bắt đầu code (`BomOrchestrator`) từ G9 trở đi, dùng mock data trong lúc chờ G0–G8 hoàn tất, rồi ráp nối thật ở G13.

---

## 4. CHI TIẾT TỪNG GIAI ĐOẠN

### G0 — Chuẩn bị môi trường & app *(0.5 ngày)*

**Việc phải làm:**
```bash
bench get-app formula_builder <path-or-git-url>
bench --site your-site install-app formula_builder
bench new-app alumglass
bench --site your-site install-app alumglass
```
- Xác nhận Formula Builder cài thành công, xem tài liệu của nó để biết chính xác tên tham số đăng ký hàm custom (`extra_funcs`/`custom_functions`/khác) — **ghi lại kết quả xác nhận này**, vì G9 phụ thuộc trực tiếp vào nó.

**Đầu ra:** site Frappe chạy được, cả 2 app đã cài, xác nhận cơ chế `extra_funcs` bằng văn bản (ví dụ ghi vào README nội bộ của app AlumGlass).

**DoD:** `bench --site your-site list-apps` hiện đủ `frappe`, `erpnext`, `formula_builder`, `alumglass`.

**Rủi ro:** nếu Formula Builder không hỗ trợ cơ chế đăng ký hàm custom như tài liệu giả định → toàn bộ thiết kế mục 6 của `v27_FULL` cần thiết kế lại cách khác (ví dụ pre-compute `so_luong_don_vi` bằng Python trước khi đưa vào engine, không để engine tự gọi hàm này) — **rủi ro cao nhất của cả dự án, cần xác nhận sớm nhất có thể, không để tới G9 mới phát hiện**.

---

### G1 — Core ERPNext: Item Group, Brand *(0.5 ngày)*

**Việc phải làm:** tạo 6 Item Group + 3 Brand theo đúng bảng mục 2.1–2.2 của `v27_FULL`, qua Desk UI hoặc fixture JSON.

**Đầu ra:** 6 Item Group (`NHOM_PROFILE` là group cha của `NHOM_XINGFA`/`NHOM_ALUMIL`), 3 Brand.

**DoD:** vào Desk → Item Group, thấy đúng cây phân cấp; Brand list đủ 3 dòng.

**Rủi ro:** thấp — bước thuần nhập liệu ERPNext chuẩn.

---

### G2 — DocType nền tảng: AL Color Standard, AL Calculation Rule, Formula Global Variable *(1 ngày)*

**Việc phải làm:**
1. Tạo DocType `AL Color Standard` (fields: `color_code`, `color_name`, `applies_to` Link→Item Group, `is_standard_stock` Check), nhập 4 dòng màu (mục 2.3).
2. Tạo DocType `AL Calculation Rule` (fields: `rule_code`, `rule_name`, `rule_type` Select, `constant_value` Float), nhập 4 hằng số offset (mục 2.4).
3. Nhập 6 dòng `Formula Global Variable` — DocType này thuộc app Formula Builder, chỉ nhập dữ liệu, không tạo DocType mới (mục 2.5).

**Đầu ra:** 3 DocType có dữ liệu như tài liệu, tổng 14 record.

**DoD:** truy vấn `frappe.get_all("AL Calculation Rule")` trả về đúng 4 dòng với `constant_value` khớp (48, 90, 50, 48).

**Rủi ro:** đặt sai `rule_type` (CONSTANT) làm hỏng logic đọc hằng số ở B1 — kiểm tra kỹ field `rule_type` phải đúng giá trị mà code B1 sẽ lọc theo.

---

### G3 — DocType cấp 2: Glass Master, Dynamic Item Rule, Slug Library, Quantity Calc Method *(1.5 ngày)*

**Việc phải làm:**
1. `AL Glass Master`: 2 dòng kính (mục 2.8) — chú ý `total_thick_mm` phải là kiểu số (Float/Int), không phải Text, vì B2b so sánh khoảng giá trị.
2. `AL Dynamic Item Rule` (+ `AL Dynamic Item Rule Version` nếu version hóa qua Workflow): 2 rule — `RULE-NEP-GLASSTHICK` (THRESHOLD, 3 khoảng) và `RULE-KEO-GLASSTYPE` (LOOKUP, 2 khóa) — mục 2.9. **Chú ý ranh giới khoảng threshold không được hở/chồng lấn** (0–10.38, 10.39–16, 16.01–999 — kiểm tra kỹ số 10.38/10.39/16/16.01, đây là nơi dễ lệch 1 đơn vị).
3. `AL Slug Library`: 17 slug (mục 2.10) — copy chính xác từng `slug` (chữ thường, không dấu, không khoảng trắng) vì đây là khóa tham chiếu cross-row.
4. `AL Quantity Calc Method`: 4 pattern (mục 2.11) — nhập `calc_formula` **chỉ để hiển thị**, ghi rõ trong mô tả field rằng không dùng để eval (tránh sau này có người sửa code để "tận dụng" field này rồi tái tạo lại lỗi mục 0.1).

**Đầu ra:** 4 DocType, tổng ~25 record.

**DoD:** test tra `RULE-NEP-GLASSTHICK` với input 24 → phải ra `C3211-20` (đúng biên 16.01–999); test tra `RULE-KEO-GLASSTYPE` với `LOWE` → `KEO-TT-01`.

**Rủi ro:** sai ranh giới threshold (ví dụ ghi 16 thay vì 16.01) → kính 16mm sẽ rơi vào rule sai, gây lệch cả chuỗi tính. Test riêng biên giới trước khi qua G4.

---

### G4 — Item + Item Price + Custom Fields + Server Script validate *(1.5 ngày)*

**Việc phải làm:**
1. Thêm 4 Custom Field vào `Item Price` (mục 8.3) và 2 field vào `Item` (`al_item_type`, `al_is_color_variable`).
2. Tạo 3 Item "đại diện" + 14 Item "profile cụ thể" (mục 2.6a, 2.6b) — chú ý `weight_per_unit` chỉ điền cho nhóm NHOM, để trống (không phải 0) cho KINH/VTP/PHU_KIEN vì các nhóm này không dùng `LENGTH_TO_WEIGHT`.
3. Nhập 15 dòng `Item Price` mẫu (mục 2.7).
4. Viết Server Script `validate_unique_price_combo` (mục 8.4), gắn Event=Before Save, DocType=Item Price.
5. **Test ngay:** thử tạo 1 dòng Item Price trùng tổ hợp `(NHOM-XINGFA, Standard Selling, WHITE, IMPORT, 20, POWDER_COATED)` → phải bị `frappe.throw()` chặn lại.

**Đầu ra:** 17 Item, 15 Item Price, 1 Server Script hoạt động.

**DoD:** test G4.5 ở trên phải fail đúng như mong đợi (báo lỗi rõ ràng, không lưu được). Ngoài ra tra thử composite key `NHOM-XINGFA|WHITE|IMPORT|20|POWDER_COATED` phải ra đúng 113,000.

**Rủi ro:** đây là giai đoạn dễ sai nhất về mặt dữ liệu (nhiều tổ hợp) — nên viết 1 script Python nhỏ đối chiếu số dòng Item Price với số tổ hợp kỳ vọng (15 dòng) trước khi qua G5, tránh thiếu/dư dòng giá âm thầm.

---

### G5 — Cost Bucket & Cost Template *(1 ngày)*

**Việc phải làm:**
1. Tạo DocType `AL Cost Bucket`, nhập 14 bucket (mục 2.12) — cây cha-con LEAF→AGGREGATE, chú ý các dòng AGGREGATE (`TONG_VL`, `TONG_NC`, `TONG_OH`, `GIA_THANH`, `GIA_BAN`, `GIA_VAT`) để `parent_bucket` trống.
2. Tạo DocType `AL Cost Template` (+ child table dòng công thức), nhập `CT-01-STANDARD` với 14 dòng công thức (mục 2.14) — **copy chính xác từng công thức**, đây là nơi công thức Cost Template phức tạp nhất (tham chiếu `$` cho global variable, tham chiếu chéo giữa các `line_code`).

**Đầu ra:** 14 Cost Bucket, 1 Cost Template với 14 dòng công thức.

**DoD:** đọc lại `CT-01-STANDARD` qua UI, đối chiếu từng dòng công thức với bảng mục 2.14 — không có dòng nào bị gõ thiếu dấu ngoặc hay sai tên biến (`$OH_QLY_PCT` vs `OH_QLY_PCT` — cú pháp `$` là bắt buộc cho global variable, thiếu dấu `$` sẽ làm engine hiểu nhầm là biến khác).

**Rủi ro:** gõ nhầm công thức `OH_QLY` (dễ nhầm `TONG_VL + TONG_NC` thành chỉ `TONG_VL`) — đây chính là loại lỗi mà `v27_FULL` mục 0.2 đã từng phát hiện ở ví dụ số; kiểm tra kỹ công thức bằng cách đối chiếu với bảng "Công thức thay số" ở mục 7.5 của `v27_FULL`.

---

### G6 — Formula Set `BOM_LINE` *(0.5 ngày)*

**Việc phải làm:** trong Formula Builder, tạo Formula Set mã `BOM_LINE`, nhập 3 dòng công thức (mục 2.13): `so_luong_don_vi`, `tong_so_luong`, `thanh_tien`.

**Đầu ra:** 1 Formula Set với 3 dòng.

**DoD:** công thức `so_luong_don_vi` phải gọi đúng tên hàm `lookup_calc_pattern(calc_pattern, width, height, trong_luong_rieng)` — tên hàm và thứ tự tham số phải khớp 100% với hàm Python sẽ viết ở G9 (nếu lệch tên/thứ tự tham số, G9 sẽ không chạy được dù code đúng).

**Rủi ro:** thấp, nhưng phụ thuộc chặt vào G9 — nên chốt tên hàm và chữ ký tham số (function signature) ngay ở bước này, ghi thành 1 "hợp đồng" (contract) chung cho cả người cấu hình Formula Set và người viết code G9.

---

### G7 — Variable Set, Profile Line/Set, BOM, BOM Version *(2 ngày)*

**Việc phải làm:**
1. Tạo DocType `AL Variable Set` (+ child `AL Variable Set Item`), tạo `VS-CDMQ` với 8 biến (mục 2.15).
2. Tạo DocType `AL Profile Line` (child table) + `AL Profile Set`, tạo `PS-CDMQ-2C` với **17 dòng đúng bảng mục 3.2** — đây là bảng cấu hình quan trọng nhất, cần nhập cẩn thận từng cột (`slug`, `width`, `height`, `qty`, `item_selection_mode`, `cost_bucket`, `calc_pattern`, `price_base_item`).
3. Tạo DocType `AL BOM`, liên kết `BOM-CDMQ-2C` → Profile Set + Variable Set + Cost Template.
4. Tạo DocType `AL BOM Version`, chốt version đầu tiên cho `BOM-CDMQ-2C`.

**Đầu ra:** 1 Variable Set, 1 Profile Set (17 dòng), 1 BOM, 1 BOM Version.

**DoD:** đối chiếu **từng dòng** trong 17 dòng đã nhập với bảng mục 3.2 của `v27_FULL` — đặc biệt 4 dòng dùng `item_selection_mode = Rule` (dòng 90, 100, 110, 120) phải trỏ đúng Rule và đúng cú pháp `items.<slug>.<field>` cho input.

**Rủi ro:** đây là giai đoạn **dễ sai nhất toàn bộ kế hoạch** vì thuần nhập tay 17 dòng công thức phức tạp. Khuyến nghị bắt buộc: sau khi nhập xong, **chưa vội qua G8** — làm ngay 1 bước kiểm tra thủ công bằng cách in ra toàn bộ 17 dòng và đối chiếu ký tự-từng-ký-tự với bảng mục 3.2, đặc biệt các công thức có phép trừ offset (`W_mm - 2*$OFFSET_DO_NGANG`) rất dễ gõ nhầm dấu `2*` thành `2×` hoặc thiếu dấu `$`.

---

### G8 — ConfigSnapshot DocType *(0.5 ngày)*

**Việc phải làm:** tạo DocType `ConfigSnapshot` với các field lưu `inputs` (JSON/Long Text), `formulas` (JSON), `result` (JSON), `bom_version_id` (Link), `rule_version_ids` (JSON), `trace` (JSON, optional).

**Đầu ra:** 1 DocType rỗng, sẵn sàng để G10 ghi dữ liệu vào.

**DoD:** tạo thử 1 record tay với dữ liệu giả, lưu và đọc lại thành công (test JSON field không bị lỗi encode).

---

### G9 — Code: `formula_handlers.py` + đăng ký `extra_funcs` *(1.5 ngày)*

**Việc phải làm:**
1. Viết `alumglass/formula_handlers.py` với hàm `lookup_calc_pattern` — **dispatch table Python thuần, tuyệt đối không gọi lại `FlexibleFormulaEngine.evaluate_single()` hay bất kỳ phương thức engine nào từ bên trong hàm này** (mục 6.1 của `v27_FULL` — đây là lỗi kiến trúc đã từng xảy ra 2 lần, phải test riêng để đảm bảo không tái diễn lần 3).
2. Viết (tùy chọn) `_handle_price_lookup`, `_handle_glass_lookup` (mục 6.2), đăng ký vào `data_source_registry` nếu app hỗ trợ.
3. Viết unit test riêng cho `lookup_calc_pattern` với 4 pattern, đối chiếu số học tay (ví dụ `LENGTH_TO_WEIGHT` với width=2400, trong_luong_rieng=1.257 phải ra 3.0168).
4. Đăng ký hàm vào engine qua đúng tham số đã xác nhận ở G0 (`extra_funcs=` hoặc tên tương ứng).

**Đầu ra:** 1 file Python có unit test kèm theo, engine khởi tạo được với hàm đã đăng ký.

**DoD:**
- [ ] Unit test 4 pattern pass với số liệu đối chiếu tay.
- [ ] Review code xác nhận **không có bất kỳ import/gọi nào tới `FlexibleFormulaEngine`** bên trong `formula_handlers.py` (grep `FlexibleFormulaEngine` trong file này phải ra kết quả rỗng).
- [ ] Test khởi tạo `FlexibleFormulaEngine(extra_funcs={...})` không lỗi.

**Rủi ro:** đây là nơi lỗi kiến trúc mục 0.1 dễ tái diễn nhất nếu người viết code không đọc kỹ tài liệu — **bắt buộc code review chéo bởi 1 người khác trước khi merge**, checklist review chỉ cần 1 câu hỏi: "hàm này có gọi ngược vào engine không?".

---

### G10 — Code: `BomOrchestrator` (11 phase) + API `calculate_bom` *(3.5 ngày)*

**Việc phải làm — chia nhỏ theo phase, code từng phase rồi test ngay, không viết hết 11 phase mới test 1 lần:**

| Phase | Việc code | Test riêng ngay sau khi viết |
|---|---|---|
| B0 | Version pinning — query `AL BOM Version` theo `valid_from` | Test với 1 version duy nhất → phải trả về đúng version đó |
| B1 | Gom input Quotation + hằng số + global var vào `inputs` | So `inputs` sinh ra với bảng kỳ vọng ở mục 5 (B1) của `v27_FULL` |
| B2a | Rule không cross-row (rỗng với BOM này) | Test chạy không lỗi, không làm gì |
| B2.5 | Batch query trọng lượng, giá, glass_thick/type — **đây là phase phức tạp nhất, cần test riêng từng phần con** (`resolve_price_attrs`, `_composite_key`, batch weight, batch price) | So `row_literals` sinh ra với bảng mục 5 (B2.5) — **17 dòng, đối chiếu từng ô** |
| B2b | Resolve 2 Rule cross-row | So kết quả với bảng B2b: `nep_kinh_tren→C3211-20`, `keo_tren→KEO-TT-01`... |
| B3 | Scan phụ thuộc cross-row | Test phát hiện đúng 5 quan hệ phụ thuộc (4 cross-row kính + 1 gioăng) |
| B4 | Build dictionary `formulas` | Đếm số key sinh ra, đối chiếu ~17×6 |
| B5 | Gọi `engine.calculate()` | So **toàn bộ bảng 17 dòng** với mục 7.3 của `v27_FULL` — đây là cổng kiểm thử quan trọng nhất |
| B6 | Gom cost bucket | So 4 số `VL_NHOM/VL_KINH/VL_VTP/VL_PK` với mục 7.4 |
| B7 | Cost Template | So 14 dòng với mục 7.5, đặc biệt `GIA_VAT = 22,717,289` |
| B8 | Lưu child table + ConfigSnapshot | Đọc lại record vừa lưu, xác nhận đủ dữ liệu |

Sau khi cả 11 phase pass test riêng, ráp thành API:
```python
@frappe.whitelist()
def calculate_bom(quotation_item_name):
    orchestrator = BomOrchestrator(quotation_item_name)
    return orchestrator.run_all_phases()
```

**Đầu ra:** class `BomOrchestrator` hoàn chỉnh, 1 API endpoint, bộ unit test cho từng phase.

**DoD:** chạy `calculate_bom()` với input chuẩn (mục 7.1) trên 1 Quotation Item thử → kết quả cuối **GIA_VAT phải bằng 22,717,289đ**, khớp chính xác tới đồng — đây là tiêu chí nghiệm thu cứng, không có "gần đúng".

**Rủi ro:** đây là giai đoạn tốn thời gian nhất và rủi ro cao nhất — nếu số liệu cuối lệch, phải soi lại từng phase theo đúng thứ tự B0→B8 (không đoán mò), so từng bảng trung gian (row_literals ở B2.5, bảng 17 dòng ở B5, 4 bucket ở B6) với đúng số liệu tài liệu đã cho — vì tài liệu đã cung cấp sẵn "đáp án" ở từng bước trung gian, không chỉ đáp án cuối cùng, mục đích chính là để debug được đúng phase nào sai khi có sai lệch.

---

### G11 — Client Script gắn UI *(0.5 ngày)*

**Việc phải làm:** thêm nút "Tính giá" trên form Quotation Item, gọi `calculate_bom()` qua `frappe.call()`, hiển thị kết quả (child table `al_bom_line_results` + các dòng Cost Template).

**Đầu ra:** 1 client script, nút bấm hoạt động trên UI.

**DoD:** bấm nút trên 1 Quotation Item thật, thấy đúng 17 dòng chi tiết + GIA_VAT hiển thị.

---

### G12 — Script seed demo data *(1 ngày)*

**Việc phải làm:** viết `alumglass/setup/seed_demo_data.py`, gom toàn bộ việc nhập tay ở G1–G7 thành 1 script chạy qua `bench execute alumglass.setup.seed_demo_data.run`, để tái lập môi trường test/demo mà không cần nhập tay lại.

**Đầu ra:** 1 script idempotent (chạy lại không tạo trùng dữ liệu).

**DoD:** xóa toàn bộ dữ liệu master (site test riêng), chạy script, chạy lại `calculate_bom()` → vẫn ra đúng `GIA_VAT = 22,717,289đ`.

**Rủi ro:** nếu G1–G7 làm thủ công có sai sót nhỏ đã "sửa tay" mà không cập nhật lại vào script → script seed sẽ tái tạo lại lỗi cũ. Đối chiếu script với dữ liệu thật trên UI trước khi coi là xong.

---

### G13 — Kiểm thử đơn vị & đối chiếu số liệu *(2 ngày)*

Chạy toàn bộ checklist mục 9.3 của `v27_FULL`:
- [ ] BOM chuẩn → GIA_VAT = 22,717,289đ
- [ ] `canh_ngang` = 702,950; `canh_dung` = 1,191,110 (2 con số từng bị sai ở bản gốc — test riêng để chắc chắn không tái diễn)
- [ ] Đổi `mau_nhom` → DARK → 8 dòng NHOM tự đổi giá sang 118,000
- [ ] Đổi `xuat_xu_nhom` → DOMESTIC → giá chuyển 98,000 (hoặc lỗi rõ ràng nếu tổ hợp không tồn tại — không được âm thầm trả 0)
- [ ] Đổi glass_thick khác 24mm → Rule chọn đúng nẹp khác
- [ ] Nhập sai giá trị Select cho `accessory_finish`/`accessory_material` → Frappe chặn ngay lúc nhập

**Đầu ra:** báo cáo kiểm thử (pass/fail từng dòng checklist).

**DoD:** toàn bộ checklist pass. Nếu có dòng fail, quay lại đúng phase liên quan ở G10 để sửa (không vá tạm ở lớp UI).

---

### G14 — Kiểm thử hiệu năng *(1 ngày)*

**Việc phải làm:** tạo 20 Quotation Item với BOM khác nhau, chạy `calculate_bom()` đồng thời (hoặc tuần tự đo tổng thời gian), dùng Frappe's query log / `frappe.db.sql` logging để xác nhận:
- Số lượng query tới `Item`, `Item Price`, `AL Glass Master` **không tăng tuyến tính theo số dòng BOM** (tức là batch query ở B2.5 hoạt động đúng, không phải N+1).

**Đầu ra:** báo cáo số query + thời gian chạy cho 1 BOM và cho 20 BOM.

**DoD:** thời gian chạy 20 BOM không lớn hơn ~20× thời gian chạy 1 BOM một cách bất thường (nếu có N+1, thời gian sẽ tăng phi tuyến rõ rệt) — đặt ngưỡng cụ thể theo hạ tầng thật (ví dụ: mỗi BOM < 1 giây, 20 BOM < 15 giây).

---

### G15 — UAT nghiệp vụ + đào tạo + go-live *(2 ngày)*

**Việc phải làm:**
1. Cho người nghiệp vụ (kinh doanh/kỹ thuật nhôm kính) chạy thử với số liệu **thật** của công ty (không phải số liệu mẫu trong tài liệu) — thay `Item Price`, trọng lượng, offset bằng số liệu thật, chạy lại toàn bộ G13 với số liệu mới, xác nhận kết quả **hợp lý về mặt nghiệp vụ** (không chỉ đúng về mặt kỹ thuật).
2. Đào tạo người dùng cách nhập Quotation, bấm "Tính giá", đọc kết quả child table.
3. Xác nhận go-live: chuyển từ site test sang site production, backup trước khi migrate.

**Đầu ra:** biên bản UAT ký xác nhận, site production sẵn sàng.

**DoD:** người nghiệp vụ xác nhận bằng văn bản/email rằng giá tính ra khớp với cách tính thủ công hiện tại của họ (trong sai số làm tròn chấp nhận được).

---

## 5. KẾ HOẠCH KIỂM THỬ TỔNG HỢP (TEST PLAN)

| Cấp độ | Khi nào chạy | Nội dung | Tiêu chí đạt |
|---|---|---|---|
| Unit test | Ngay sau mỗi phase ở G9–G10 | Test từng hàm (`lookup_calc_pattern`, `resolve_price_attrs`, từng phase B0–B8) độc lập, dùng input giả lập | Mỗi hàm/phase có ít nhất 1 test case đối chiếu số liệu tay |
| Integration test | G13 | Chạy full `calculate_bom()` end-to-end với input chuẩn mục 7.1 | GIA_VAT = 22,717,289đ, khớp tuyệt đối |
| Regression/sensitivity test | G13 | Đổi từng biến input (màu, xuất xứ, kích thước, số cánh) | Kết quả thay đổi đúng hướng và đúng công thức, không có giá trị "đứng yên" bất thường |
| Performance test | G14 | 20 BOM đồng thời | Không có N+1 query, thời gian trong ngưỡng chấp nhận |
| UAT | G15 | Số liệu thật của doanh nghiệp | Người nghiệp vụ xác nhận bằng văn bản |

---

## 6. CỔNG NGHIỆM THU CUỐI (UAT) — TIÊU CHÍ "COI NHƯ XONG"

Dự án được coi là **hoàn thành giai đoạn 1** (1 sản phẩm mẫu CDMQ-2C-TRANSOM) khi và chỉ khi **tất cả** các điều sau đều đúng:

1. [ ] `calculate_bom()` chạy với input chuẩn (mục 7.1 của `v27_FULL`) ra đúng `GIA_VAT = 22,717,289đ`, khớp tới đồng.
2. [ ] Toàn bộ checklist mục 9 (`v27_FULL`) — cả 9.1 Master Data, 9.2 Cấu hình kỹ thuật, 9.3 Kiểm thử số liệu — đều pass.
3. [ ] Code review xác nhận `lookup_calc_pattern` không gọi ngược vào engine (grep sạch).
4. [ ] Kiểm thử hiệu năng xác nhận không có N+1 query.
5. [ ] Script `seed_demo_data.py` chạy lại từ site trống vẫn ra đúng kết quả như trên.
6. [ ] Người nghiệp vụ đã UAT với số liệu thật và xác nhận bằng văn bản.
7. [ ] `ConfigSnapshot` lưu đủ dữ liệu để tái lập lại đúng kết quả cũ khi mở lại báo giá sau này (test bằng cách đổi giá trong Item Price rồi mở lại báo giá cũ — số liệu cũ phải không đổi).

---

## 7. KẾ HOẠCH RỦI RO & PHƯƠNG ÁN DỰ PHÒNG

| Rủi ro | Xác suất | Ảnh hưởng | Phương án dự phòng |
|---|---|---|---|
| Formula Builder không hỗ trợ `extra_funcs` như giả định (rủi ro G0) | Trung bình | Cao — phải thiết kế lại cách gọi `lookup_calc_pattern` | Xác nhận cơ chế đăng ký hàm **trước khi** bắt đầu G6/G9; nếu không hỗ trợ, chuyển sang phương án pre-compute `so_luong_don_vi` bằng Python ngay ở B4 (trước khi vào engine), chỉ đưa engine 1 field literal đã tính sẵn thay vì gọi hàm trong công thức |
| Nhập sai 1 trong 17 dòng Profile Line (rủi ro G7) | Cao (nhập tay, công thức phức tạp) | Cao — lan toàn bộ kết quả cuối | Đối chiếu ký tự-từng-ký-tự với mục 3.2 trước khi qua G8; ưu tiên import từ fixture JSON thay vì nhập tay qua UI để giảm lỗi gõ |
| Tái diễn lỗi kiến trúc gọi đệ quy vào engine (rủi ro G9) | Trung bình (đã xảy ra 2 lần trong lịch sử tài liệu) | Cao — sai cả kiến trúc, khó phát hiện qua test số liệu đơn thuần vì có thể vẫn ra đúng số nhưng chậm/không trace được | Code review bắt buộc, chỉ hỏi đúng 1 câu: "hàm có gọi ngược engine không?" |
| Sai ranh giới AL Dynamic Item Rule (rủi ro G3) | Trung bình | Trung bình — chọn sai nẹp/keo ở 1 vài tổ hợp độ dày biên | Test riêng các giá trị biên (10.38, 10.39, 16, 16.01) trước khi qua G4 |
| Thiếu/dư dòng Item Price (rủi ro G4) | Trung bình | Trung bình — 1 vài tổ hợp màu/xuất xứ không tra được giá | Viết script đối chiếu số dòng kỳ vọng vs số dòng thực tế trước khi qua G5 |
| Số liệu nghiệp vụ thật khác nhiều so với số liệu mẫu (rủi ro G15) | Cao (luôn xảy ra khi lên production thật) | Thấp — chỉ cần thay data, không đổi kiến trúc | Kiến trúc đã tách data khỏi code (mục 1.2 nguyên tắc 6), nên chỉ cần nhập lại Item Price/Calculation Rule thật, không cần sửa code |

---

## 8. CHECKLIST TỔNG HỢP MỘT TRANG (IN RA DÙNG KHI THI CÔNG)

```
[ ] G0  Cài formula_builder + alumglass, xác nhận cơ chế extra_funcs
[ ] G1  Item Group (6) + Brand (3)
[ ] G2  AL Color Standard (4) + AL Calculation Rule (4) + Formula Global Variable (6)
[ ] G3  AL Glass Master (2) + AL Dynamic Item Rule (2, test biên) + AL Slug Library (17) + AL Quantity Calc Method (4)
[ ] G4  Item (17) + Item Price (15) + Custom Fields + Server Script validate (test trùng)
[ ] G5  AL Cost Bucket (14) + AL Cost Template CT-01-STANDARD (14 dòng, đối chiếu công thức)
[ ] G6  Formula Set BOM_LINE (3 dòng, chốt chữ ký hàm lookup_calc_pattern)
[ ] G7  AL Variable Set VS-CDMQ (8 biến) + AL Profile Set PS-CDMQ-2C (17 dòng, đối chiếu ký tự) + AL BOM + AL BOM Version
[ ] G8  ConfigSnapshot DocType
[ ] G9  formula_handlers.py (dispatch table thuần, KHÔNG gọi ngược engine — grep kiểm tra) + unit test 4 pattern
[ ] G10 BomOrchestrator 11 phase (test từng phase riêng: B0→B8, đối chiếu số liệu trung gian ở mỗi bước)
[ ] G11 Client Script nút "Tính giá"
[ ] G12 seed_demo_data.py (idempotent, test chạy lại từ site trống)
[ ] G13 Test số liệu: GIA_VAT=22,717,289 + sensitivity (màu/xuất xứ/kính) + validate chặn trùng giá
[ ] G14 Test hiệu năng: 20 BOM đồng thời, không N+1
[ ] G15 UAT số liệu thật + đào tạo + go-live

CỔNG CUỐI: GIA_VAT = 22,717,289đ (input chuẩn mục 7.1 của v27_FULL) — KHÔNG ĐẠT THÌ CHƯA ĐƯỢC COI LÀ XONG.
```

---

*Kế hoạch này tổ chức lại thành trình tự thi công dựa trên nguồn kỹ thuật duy nhất `AlumGlass_v27_FULL.md` (gộp v26_new.md + cải tiến v27). Mọi số liệu, công thức, tên field tham chiếu trong kế hoạch này lấy nguyên văn từ tài liệu đó — nếu có mâu thuẫn giữa 2 tài liệu, `AlumGlass_v27_FULL.md` là nguồn đúng.*
