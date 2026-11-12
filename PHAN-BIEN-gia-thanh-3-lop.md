# PHẢN BIỆN THIẾT KẾ "GIÁ THÀNH 3 LỚP"

> Phản biện tài liệu `gia-ban-gia-dinh-muc-thuc-te.md` (1.426 dòng, bản 11/11/2026).
> Góc nhìn: kiến trúc ERPNext · quản trị doanh nghiệp · sản xuất nhôm kính.
> Mọi kết luận về code đều **đã kiểm chứng trong repo** — trích dẫn file/dòng kèm theo.
> ⚠ **Cảnh báo phiên bản:** mọi kiểm chứng dưới đây chạy trên **ERPNext v14.92.14 / Frappe v14.101.1**
> (bench cục bộ). Đích triển khai là **v16** — các kết luận gắn với hành vi lõi phải chạy lại trên v16
> trước khi chốt. Đây đúng là cái bẫy đã gây hạ nhầm 3 tệp xuống v14 trước đó.

---

## 0. KẾT LUẬN TRƯỚC KHI ĐỌC TIẾP

Tài liệu này **tốt hơn mức trung bình rất nhiều**: nó đọc code thật, nêu đúng 8 khoảng trống, và
kiến trúc "bucket là ngôn ngữ chung, account là ngôn ngữ kế toán, mapping là cầu nối" là đúng.

Nhưng có **hai lỗi gốc** làm hỏng chính mục đích của lớp S, và **năm lỗi miền nhôm kính** khiến
số liệu sẽ sai ngay từ bản đầu tiên. Nếu triển khai nguyên bản:

| Điều sẽ xảy ra | Vì sao |
|---|---|
| Báo cáo "chênh lệch giá mua" **luôn ≈ 0** | S tự chạy theo giá vốn hiện hành ⇒ không còn mốc để so |
| Báo cáo "kiểm tra đóng" **luôn ✔** dù số sai | phép kiểm là hằng đẳng thức, không kiểm gì |
| Lượng kính định mức **sai 20–40%** | kính mua theo tấm, không theo m² + 3,8% |
| Hao hụt nhôm **bị tính hai lần** ở cấp dự án | Cutting Plan đã gồm hao hụt, lại nhân thêm % |
| Chi phí làm lại (vỡ kính, cắt lại) **bị giấu** trong bucket vật tư | gộp vào `VL_KINH` thay vì bucket riêng |
| Nhân công thực tế **không lấy được từ sổ** | ERPNext không tạo bút toán nhân công từ Job Card |

Đề xuất của tôi ở §8 không phải là làm lại từ đầu — phần lớn giữ nguyên. Nó **đổi một thứ căn bản**
(S có hai bản: khoá và sống), **cắt bớt** (9 bucket thay 12, grain dự án thay dòng SO), và **dời**
(một số pha).

---

## 1. NHỮNG GÌ TÀI LIỆU LÀM ĐÚNG (giữ nguyên, đừng đụng)

| Điểm | Vì sao đúng |
|---|---|
| Q và S **dùng chung một engine BOM** | Chênh lệch Q–S quy được về 4 tham số. Nếu tách 2 engine, hai bên sẽ trôi khỏi nhau và không ai biết bản nào đúng |
| **Bucket là ngôn ngữ chung**, mapping là cầu nối | Đây là cách duy nhất để kế toán và sản xuất nhìn cùng một bộ số mà không phải ép một bên đổi cách làm |
| **A đọc từ sổ, không tạo sổ thứ hai** | Đúng nguyên tắc. Collector chỉ đọc, không ghi bút toán |
| **`UNMAPPED` là bucket bắt buộc** | Chống mất tiền im lặng — điểm rất tốt, ít tài liệu nào có |
| **Tách `compute` khỏi `persist`** (G6) | Đúng và cần làm sớm |
| **Vật liệu hoá BOM ERPNext lúc Release** | Đúng hướng: S là kế hoạch, BOM là thực thi, chỉ gặp nhau ở một điểm |
| Bảng "cầu nối lợi nhuận" Q → A (§9.8) | Đây là thứ BGĐ thực sự dùng. Giá trị cao nhất trong tài liệu |

---

## 2. LỖI GỐC #1 — "S realtime" phá huỷ chính mục đích của S

Tài liệu đặt S tự tính lại theo **giá vốn hiện hành (moving average)** mỗi khi nhập kho, và tự hào
về điều đó:

> §10.2 Bước 10: *"Nhôm: chênh lệch giá ≈ 0 vì S đã tự cập nhật theo giá nhập + cước ở Bước 3
> (đó là lợi ích của định mức realtime)."*

Đó **không phải lợi ích — đó là mất tín hiệu.**

Nếu S chạy theo đúng giá vốn mà A dùng, thì **A − S phần giá luôn bằng 0 theo định nghĩa**. Bạn
không còn trả lời được câu hỏi duy nhất mà bộ phận mua hàng cần: *"Đơn này mình mua đắt hơn kế
hoạch bao nhiêu?"* Câu trả lời sẽ luôn là "không đắt hơn", vì kế hoạch đã chạy theo giá mua.

Nặng hơn: §9.5 dùng **"lợi nhuận kế hoạch thực" = doanh thu báo giá − giá thành định mức** để nói
"biên lợi nhuận đang giấu trong báo giá". Con số đó **chỉ có nghĩa nếu S đứng yên tại một thời điểm**.
S trôi ⇒ con số trôi theo, và không tái lập được.

### Đề xuất: S phải là HAI bản, không phải một

| Bản | Khoá khi nào | Dùng cho | Ghi chú |
|---|---|---|---|
| **S₀ — định mức khoá** | Lúc xác nhận SO (hoặc đầu kỳ giá) | Đo chênh lệch, tính "lợi nhuận kế hoạch thực", đánh giá mua hàng | **Bất biến**. Chỉ đổi qua một hành động có tên: "Tái chuẩn hoá định mức" (có người duyệt, có lý do) |
| **S₁ — dự báo sống** | Tính lại mỗi khi giá đổi | Quyết định mua, cảnh báo "đơn này đang đắt lên", tái báo giá | Không dùng để tính chênh lệch. Không cần revision, chỉ cần số mới nhất |

Trong `AL Cost Plan`, đây là **2 cặp field** (`standard_amount` / `current_estimate_amount`) trên
cùng một bản ghi, **không phải hai DocType**. Revision chỉ sinh khi S₀ đổi.

Cách này cũng giải quyết luôn vấn đề "revision churn": tài liệu phải đặt ngưỡng 0,5% để chặn sinh
revision — nghĩa là chính tác giả cũng thấy nó sẽ nổ. Với S₀ khoá, mọi thay đổi giá **không sinh
revision nào cả**, chỉ cập nhật một cột.

> **Đây là điểm quyết định.** Nếu chỉ sửa một chỗ trong tài liệu, sửa chỗ này.

---

## 3. LỖI GỐC #2 — "Kiểm tra đóng" là hằng đẳng thức, không kiểm gì

§7.4 và §9.7 trình bày phép kiểm *"Σ theo bucket = Σ theo tài khoản = tổng nguồn"* như một bảo đảm.

Nhưng thuật toán §7.3 nhân mỗi khoản với `w_bucket × w_account`, rồi **bắt buộc** Σw = 100%.
Nhân một số với các trọng số cộng lại đúng 100% thì tổng **luôn bằng số gốc** — không phụ thuộc
dữ liệu, không phụ thuộc mapping đúng hay sai. Phép kiểm này xanh kể cả khi bạn map toàn bộ chi phí
vào nhầm bucket.

Tương tự §9.7: *"giá vốn (632) = 621+622+627 trừ phần còn trong kho"* — "phần còn trong kho" lại
được **suy ngược từ chính con số cần kiểm**. Đó là lập luận vòng.

### Phép kiểm thật sự phải làm

| Kiểm | Đối tượng đối chứng **độc lập** | Bắt được lỗi gì |
|---|---|---|
| **Đóng với sổ cái** | `SUM(debit-credit)` của GL Entry theo `(project, account, kỳ)` — **không** đi qua mapping | Collector bỏ sót / nhân đôi chứng từ |
| **Đóng với kho** | `SUM(stock_value_difference)` của Stock Ledger Entry theo project/kỳ | Giá trị xuất kho bị lệch khỏi GL |
| **Đối chứng dương** | Cố tình map sai một tài khoản → phép kiểm **phải đỏ** | Phép kiểm là tautology (đúng ca này) |
| **Không âm vô lý** | Bucket vật tư không được âm sau khi trừ phế liệu | Phế liệu bị trừ quá |
| **Phủ 100%** | Số dòng GL có project mà không thành Cost Fact = 0 | Mất tiền im lặng |

Không có "đối chứng dương" thì một bộ kiểm tra luôn xanh chỉ chứng minh rằng nó không kiểm gì.
(Đã có tiền lệ trong nhà: 153 test xanh vẫn bỏ lọt lỗi lệch đơn vị tiền.)

---

## 4. NĂM LỖI MIỀN NHÔM KÍNH

Đây là phần tài liệu yếu nhất: nó mô hình hoá nhôm kính **giống hệt** một nhà máy lắp ráp tổng quát
(vật tư × (1+hao hụt) × đơn giá). Ngành này không chạy như vậy.

### 4.1 Nhôm: mua theo **cây**, tính theo **kg**, và hao hụt đang bị tính hai lần

Tài liệu: `gross_qty = net_qty × (1 + waste_pct)`, với `waste_pct` **lấy từ Cutting Plan** (§5.4).

Cutting Plan đã là bài toán cắt: nó tính số cây cần, trừ đầu thừa, trừ lưỡi cưa, tận dụng đoạn dư.
Đầu ra của nó **đã là lượng phải mua**. Nhân thêm `(1 + waste_pct)` lên số tịnh là **cộng hao hụt
lần thứ hai** — trừ khi `waste_pct` được định nghĩa chính xác là `cần_mua/tịnh − 1`. Tài liệu không
định nghĩa, và §5.4 viết như thể nó là một tỷ lệ độc lập.

Cùng gốc rễ: Cutting Plan phải chạy ở **cấp dự án/lô cắt**, không phải cấp từng dòng SO. Cắt gộp
nhiều sản phẩm trong một đơn là chỗ tiết kiệm thật (đoạn dư của cửa này dùng cho vách kia). Chạy
plan theo từng sản phẩm rồi cộng lại sẽ **luôn** cho hao hụt cao hơn thực tế.

**Đề xuất:**
- `waste_pct` chỉ dùng khi **chưa có** Cutting Plan (fallback), và phải ghi rõ nó là ước lượng.
- Có Cutting Plan ⇒ dùng **thẳng số cây/số kg cần mua** của plan, không nhân thêm gì.
- Cutting Plan chạy ở cấp **lô cắt (dự án hoặc nhóm dòng SO)**, không phải từng dòng.
- Quy đổi **cây ↔ kg** phải là dữ liệu master (`kg/m` theo mã nhôm), không phải hằng số trong công thức.
  Nhà cung cấp VN bán theo cây nhưng xuất hoá đơn theo **kg cân thực**; chênh **1–3%** so với
  khối lượng lý thuyết. Không mô hình hoá chênh này thì cột "chênh lệch giá" sẽ luôn có một khoản ma.

### 4.2 Kính: "3,8% hao hụt" là số không có thật

Kính trong ngành này đi theo **một trong hai** đường, và cả hai đều không phải "m² × (1+3,8%)":

| Mô hình | Cách tính giá thật | Hao hụt |
|---|---|---|
| **A. Mua gia công cắt sẵn** (phổ biến nhất với kính cường lực / hộp / dán) | đ/m² theo **kích thước tấm đặt** + phí tối thiểu/tấm + xử lý cạnh (đ/m) + khoan lỗ (đ/lỗ) + phí cường lực | **bằng 0 phía bạn** — nhà gia công chịu |
| **B. Tự cắt từ tấm lớn** (2.140×3.300, 2.440×3.660…) | đ/tấm ÷ số m² dùng được | phụ thuộc **cách xếp tấm (nesting)**, có thể **20–40%**, không bao giờ là 3,8% |

Với mô hình A, đặt `waste_pct = 3,8%` là **bịa ra chi phí không tồn tại**. Với mô hình B, 3,8% là
**đánh giá thấp nghiêm trọng**. Cả hai đều làm S sai, chỉ khác chiều.

**Đề xuất:** thêm một field `glass_purchase_mode` ở `AL Cost Profile`:
`PROCESSOR_CUT_TO_SIZE` (không hao hụt, có phí tối thiểu + xử lý cạnh) hoặc `SHEET_NESTING`
(hao hụt do module xếp tấm trả về, không nhập tay).

### 4.3 Làm lại / phế phẩm phải là **bucket riêng**, không được giấu trong bucket vật tư

§9.4 ghi: *"SE-0460 (Material Consumption) | VL_KINH | L1: 24,7 m² × 705.000 (**có 2,1 m² cắt bù
kính vỡ**)"*, và §4 Bước 4 ghi phế liệu nhôm 4,0 kg vào `SCRAP_REC`.

Nghĩa là **tấm kính vỡ** bị hoà vào `VL_KINH`, còn **đoạn nhôm dư bán đi** lại được tách riêng.
Hai thứ cùng bản chất (mất mát ngoài định mức) đang được đối xử ngược nhau.

Hệ quả quản trị: báo cáo sẽ nói *"kính vượt định mức 10,2%"* thay vì *"vỡ 1 tấm = 2,1 m² = X đồng"*.
Với ngành này, **vỡ kính và làm lại là chỗ rò rỉ lợi nhuận số 1** — nó phải nhìn thấy được thành một
dòng riêng.

**Đề xuất:** thêm `LAM_LAI` (rework/breakage) là bucket riêng, **không có trong Q và S** ⇒ tự động
`unplanned_flag`. Và `SCRAP_REC` giữ nguyên nhưng đặt cạnh nó để đọc thành một cặp:
`LAM_LAI` (mất) − `SCRAP_REC` (thu hồi) = **hao hụt ròng**.

Lưu ý nghiệp vụ: kính cường lực **không cắt lại được**. Vỡ 1 tấm = đặt lại **nguyên tấm** + 7–15
ngày chờ. Định mức hao hụt dạng % không bao giờ bắt được sự kiện rời rạc này.

### 4.4 Nhân công: thiết kế đang phụ thuộc vào thứ công nhân sẽ không làm

§6.1 và §9.4 lấy chi phí nhân công thực tế từ **Job Card (time log)**.

Trong xưởng nhôm kính VN, công nhân **hầu như không bấm giờ vào/ra từng công đoạn**. Job Card trong
ERPNext đòi bấm `start`/`finish` trên từng operation — tỷ lệ tuân thủ thực tế gần bằng 0. Nếu lớp A
phụ thuộc Job Card, lớp A sẽ **rỗng hoặc sai**, và cả bảng so sánh sụp.

**Đề xuất — đổi nguồn nhân công thực tế:**
- **Mặc định:** phân bổ từ **bảng lương / bảng chấm công theo tổ, theo công trình** (số công × đơn giá
  công). Đây là dữ liệu kế toán **đã có** và **đã đáng tin**.
- **Tuỳ chọn nâng cao:** Job Card chỉ dùng cho **máy CNC / trung tâm gia công** — nơi có người vận
  hành bấm máy và giờ máy thực sự cần đo.
- Định mức S: dùng **định mức công/bộ** (giờ công hoặc công) × **đơn giá công**. Không cần Job Card.

Việc này cũng sửa luôn §6.4: nếu không có Job Card thì ERPNext hấp thụ theo
`BOM.planned_operating_cost` (xem §6 dưới), tức là **hấp thụ = định mức**, và mọi chênh lệch dồn vào
cuối kỳ. Phải quyết định rõ điều này thay vì mô tả một cơ chế không tồn tại ở nguồn dữ liệu.

### 4.5 Thiếu ba bucket mà ngành này luôn có

| Bucket thiếu | Vì sao chắc chắn phải có |
|---|---|
| **`LAM_LAI`** (làm lại, vỡ, sai kích thước) | Xem 4.3. Đây là khoản làm biên lợi nhuận bốc hơi |
| **`BAO_HANH`** (bảo hành) | Nhôm kính bảo hành 2–5 năm. Phải trích trước theo % doanh thu, nếu không thì đơn năm nay "lãi" bằng chi phí của 3 năm sau. Đã có `AL Warranty Claim` — đừng để nó nằm ngoài bộ số |
| **`MAY_THI_CONG`** (TK 623) | Xem §5.1 — thuê cẩu, giàn giáo, máy cắt là chi phí máy, không phải chi phí chung |

---

## 5. PHẢN BIỆN KẾ TOÁN

### 5.1 Thiếu TK 623 — và đây là lỗi hệ thống tài khoản, không phải chi tiết nhỏ

Tài liệu §7.2 map: vật liệu → 621, nhân công → 622, chung → 627, bán hàng → 641, quản lý → 642.

Hệ thống tài khoản VAS cho doanh nghiệp **xây lắp / lắp đặt** có **TK 623 — Chi phí sử dụng máy thi công**,
nằm giữa 622 và 627. Với một công ty vừa sản xuất vừa lắp đặt, chi phí **cẩu, giàn giáo, máy cắt,
máy nâng** thuộc 623 chứ không phải 627.

§9.4 đang đẩy "thuê cẩu 2.400.000" vào `KHAC → 627`. Nếu đơn vị hạch toán theo mô hình xây lắp thì
đây là **hạch toán sai tài khoản**, và báo cáo P&L sẽ không khớp với sổ kế toán hiện tại.

**Việc cần làm:** xác nhận mô hình hạch toán của đơn vị (sản xuất theo TT200 hay xây lắp), rồi chốt
có 623 hay không. Nếu có, thêm bucket `MAY_THI_CONG` và tách `KHAC` thành "phát sinh vật tư" /
"phát sinh máy" / "phát sinh khác" — nếu không thì không ai biết cẩu thuê là bất thường hay bình thường.

### 5.2 Hai con số giá thành khác nhau đang bị trộn: 154/155 và "theo công trình"

Tài liệu dùng 154 (SX dở dang) → 155 (thành phẩm) → 632 (giá vốn) — mô hình **sản xuất**.

Nhưng đơn hàng nhôm kính thực tế là **hợp đồng lắp đặt**: chi phí tích luỹ ở **154** và kết chuyển
thành **giá thành công trình** khi nghiệm thu, không đi qua 155. Tài liệu §9.7 lại ghi *"tồn kho
thành phẩm (TK 155) = 1 bộ L2 chưa giao"* — tức là mô hình sản xuất.

Cả hai đều hợp lý, nhưng **không thể cùng lúc** cho cùng một dòng hàng. Phải chọn:
- **Sản xuất bán hàng** (cửa là thành phẩm, lắp đặt là dịch vụ riêng) → 155 đúng.
- **Hợp đồng lắp đặt** (công trình là đơn vị giá thành) → 154 đúng, không có 155.

Điều này quyết định **grain của cả hệ thống** (xem §5.3).

### 5.3 Grain: tài liệu chọn "dòng Sales Order", nhưng ngành này chi phí phát sinh ở cấp **công trình**

Đây là điểm tài liệu tự nhận là rủi ro (§11.2) nhưng không giải quyết:
*"Phân bổ sản phẩm dùng chung nhiều dự án → A theo dòng SO kém chính xác"*.

Vấn đề thật sâu hơn: **có xung đột cấu trúc giữa "chi phí chính xác theo từng dòng SO" và "tối ưu
cắt"**. Muốn A theo từng dòng SO thì phải có Work Order riêng cho từng dòng — nhưng khi đó bạn
**mất chính lợi ích cắt gộp** (cắt chung nhiều sản phẩm để tận dụng đoạn dư), tức là hao hụt thực
tế tăng. Tối ưu cái này thì mất cái kia.

**Đề xuất:**
- **Grain chính = Project (công trình) + lô sản xuất.** Đây là nơi dữ liệu thực sự tồn tại.
- **Dòng SO = grain phân bổ**, chia theo **tỷ trọng định mức (S₀)**. Ghi rõ trên báo cáo:
  *"A theo dòng hàng là số phân bổ, không phải số đo"*.
- Đừng trình bày A theo dòng SO như số đo được — đó là nguồn của mọi cuộc tranh cãi "số này sai".

### 5.4 Ghi nhận doanh thu: §9.7 đang suy diễn, không phải ghi nhận

§9.7 tính *"doanh thu ghi nhận = doanh thu SO sau giảm 1,5% × tỷ trọng đã giao (90,8%)"*.

VAS không ghi nhận doanh thu theo tỷ trọng chi phí đã giao. Doanh thu ghi theo **hoá đơn / biên bản
nghiệm thu khối lượng**. Con số 90,8% là **giả định của mô hình**, không phải số của kế toán.

Ngoài ra: giảm giá 1,5% cho khách nên là **giảm giá hàng bán (TK 521)**, không net vào 511 — trừ khi
đơn vị đã chọn cách ghi net.

**Việc cần làm:** bỏ hẳn phần suy diễn doanh thu khỏi tài liệu thiết kế; doanh thu lấy thẳng từ
Sales Invoice. Nếu cần "doanh thu theo % hoàn thành" thì đó là **báo cáo quản trị**, tách khỏi P&L.

### 5.5 Giá thành đầy đủ vs lợi nhuận góp — phải chọn, không được trộn

Q có `OH_QLY` (quản lý) và `OH_VC` (bán hàng) trong giá thành báo giá. S có `OH_QLY 2,5%`. A phân bổ
642 về dự án. Như vậy **cùng một khoản quản lý doanh nghiệp** xuất hiện ở cả ba lớp, và tổng A của
tất cả dự án sẽ bằng toàn bộ chi phí công ty.

Điều này có nghĩa: **biên lợi nhuận trên báo cáo là biên sau khi gánh toàn bộ chi phí gián tiếp** —
không phải "lãi góp" mà kinh doanh dùng để quyết định nhận/không nhận đơn.

**Đề xuất:** hai chế độ nhìn, đừng trộn:

| Chế độ | Nội dung | Dùng cho |
|---|---|---|
| **Giá thành sản xuất** (621+622+623+627) | So với S. Đây là lưới so sánh chính | Sản xuất, mua hàng, kế toán giá thành |
| **Lợi nhuận góp** (doanh thu − biến phí) | Không phân bổ 641/642 | Kinh doanh, quyết định giá |
| **Toàn bộ chi phí** (memo) | + 641/642 phân bổ | BGĐ, xem có lãi ròng không — **đánh dấu rõ là số phân bổ** |

### 5.6 Làm tròn: hệ thống sẽ lệch 1–2 đồng và mất niềm tin

Chia một khoản theo trọng số 40/60 rồi làm tròn về đồng ⇒ tổng các phần **không bằng** tổng gốc.
Với VND (không thập phân), sai lệch này hiện ngay trên báo cáo và kế toán sẽ mất tin vào cả hệ thống.

**Đề xuất:** phân bổ bằng **largest remainder** (phần dư lớn nhất) — chia hết phần nguyên, dồn đồng
dư vào dòng lớn nhất. Viết một hàm dùng chung, dùng cho **mọi** chỗ chia (bucket, tài khoản, allocation run).

---

## 6. KIỂM CHỨNG CODE — tài liệu nói gì, code thực tế thế nào

Đây là phần tôi đọc trực tiếp repo để đối chiếu. Nhiều ⚠ trong tài liệu có thể **đóng lại ngay**.

| # | Tài liệu nói | Kiểm chứng | Kết luận & hệ quả |
|---|---|---|---|
| **G1** | SO Item thiếu `al_bom*` ⇒ mất khi map | ✅ Đúng. `setup/custom_fields.py` chỉ có `Quotation Item`; `frappe/model/mapper.py::map_fields()` copy **mọi field trùng tên** không `no_copy` | Sửa **rất nhỏ** (thêm 4 field vào `Sales Order Item`). Nhưng xem dòng dưới |
| **G2** | `aggregate_requirements` cộng qty thô | ✅ Đúng, và **nặng hơn**: `al_material_plan.py:34` SELECT `al_bom`, `al_bom_version` từ `Sales Order Item` — hai cột **chưa tồn tại** | Không phải "trả rỗng" mà **lỗi SQL 1054** khi gọi. Hàm này hiện đang là bom hẹn giờ |
| **G4** | Dimension `AL Cost Bucket` đưa bucket vào GL | ✅ **Khả thi và đúng**. `erpnext/hooks.py:513` có `Stock Entry Detail`, `Purchase Receipt Item`, `Sales Order Item`, `Landed Cost Item`…; `general_ledger.py::merge_similar_entries()` gộp theo **danh sách dimension**, nên bucket từng dòng **không bị trộn** | Yên tâm. Chỉ cần đặt `label = "AL Cost Bucket"` để `scrub()` sinh đúng `al_cost_bucket`; nếu đặt label khác sẽ **đẻ ra field thứ hai** và dữ liệu tách làm đôi |
| **G6** | B7 ghi thẳng Quotation Item, cần tách | ✅ Đúng, và **nặng hơn tài liệu mô tả**: `bom_orchestrator.py:2588` `b7_save_results()` gọi `frappe.db.commit()` ở cuối | Tái dùng cho `Sales Order.on_submit` ⇒ **commit giữa transaction submit** ⇒ mất tính nguyên tử. Phải bỏ commit khỏi engine **trước** khi tái dùng. Đây là việc của Pha 0 |
| **§5.1** | Thêm `template_type` vào `AL Cost Template` | `al_cost_template.json` chỉ có `template_code`, `template_name`, `product_type`, `is_active` | Thêm cờ loại ⇒ **mỗi Product Type phải có 2 template** và đồng bộ tay mãi mãi. **Đề xuất thay:** giữ 1 template, thêm cột `layer` (Q/S/CẢ HAI) trên từng dòng `AL Cost Template Item` |
| **§6.4** | Hấp thụ NC/CP chung vào thành phẩm theo bucket | ❌ **Không đúng.** `erpnext/manufacturing/doctype/bom/bom.py::add_operations_cost()` tạo **đúng 1 dòng** `additional_costs`, account = `Company.default_expense_account`, **không dimension, không tách công đoạn**. Nguồn số là `get_operating_cost_per_unit()`: ưu tiên Job Card `actual_operating_cost`, fallback `BOM.planned_operating_cost` | Không thể đọc `ABSORBED` theo bucket từ GL. Nếu cần tách NC_SX / OH_SX ở lớp A thì phải **tự tính từ WO/Job Card**, không đọc sổ. Tài liệu đang mô tả một cơ chế không tồn tại |
| **§5.4** | `Workstation.hour_rate` là nguồn đơn giá giờ | Đường hấp thụ của v14 **không dùng** `Workstation.hour_rate` trực tiếp; nó dùng `Operation` → `BOM Operation` → Job Card `actual_operating_cost` | Đơn giá giờ phải đi qua **Operation/BOM Operation**, hoặc qua biến Formula Builder. Ghi sai nguồn ⇒ người dùng sửa Workstation mà số không đổi |
| **§8.3** | Chưa chắc FB query được `Bin` | ✅ Query được. `formula_builder/api/data_source_registry.py` — `aggregate_from_items` hỗ trợ `rows_source: doctype_query` + `filters` (Frappe-style) | Đóng ⚠ này. Nhưng nhớ: **lỗi binding FB ⇒ 0 im lặng** — dùng `strict_errors` cho mọi profile S |
| **§11.4.1** | Map field Q Item → SO Item | ✅ Đã kiểm: `map_fields()` copy field trùng tên từ `target_doc.meta` | Đóng ⚠. Lưu ý `al_calc_status` có `no_copy: 1` nên sẽ **không** copy — đúng ý |
| **§2.2** | `BomOrchestrator` ~2.700 dòng | Thực tế **2.747 dòng**, phụ thuộc `Quotation Item` ở **9 chỗ** (`_qi_doc`) + constructor nhận `quotation_item_name` | Refactor **không phải "bọc interface"** như §5.2 mô tả — phải tổng quát hoá `_qi_doc` thành `source_doc`. Vẫn làm được, nhưng ước lượng công phải đúng |

### Một điểm tài liệu bỏ sót hoàn toàn: **"Chuẩn" không tồn tại trong ERPNext v14**

§2.1 xếp BOM vào "nên tận dụng core" như thể ERPNext có standard costing. **Không có.**
ERPNext v14 chỉ có:
- `BOM.total_cost` = raw material + operating cost — một phép cộng, không có mốc chuẩn;
- `rm_cost_as_per` = Valuation Rate / Last Purchase Rate / Price List;
- **không** có báo cáo chênh lệch giá chuẩn, **không** có tài khoản chênh lệch.

Nghĩa là: **lớp S là hệ thống tự xây, không phải cấu hình ERPNext.** Điều này đúng và vẫn nên làm —
nhưng phải nói rõ với Owner rằng đây là **phần mềm riêng phải nuôi**, không được ERPNext nâng cấp hộ.
Tài liệu đang trình bày nó như "tận dụng tối đa core", dễ gây kỳ vọng sai.

---

## 7. PHẢN BIỆN KIẾN TRÚC — ba lựa chọn, và tôi chọn cái nào

Câu hỏi gốc: **S nên là engine riêng, hay để ERPNext tính?**

| | **A. Engine riêng (tài liệu đang chọn)** | **B. Vật liệu hoá BOM ngay khi xác nhận SO** | **C. Lai (khuyến nghị)** |
|---|---|---|---|
| S lấy từ | `BomOrchestrator` + `AL Cost Plan` | `BOM.total_cost` của ERPNext | Engine riêng, nhưng **chỉ giữ phần ERPNext không làm được** |
| Ưu | Realtime, hao hụt động, nhân công theo giờ, không phình BOM | Một nguồn sự thật, báo cáo native, không phải nuôi thêm | Tránh cả hai nhược điểm |
| Nhược | Nguồn sự thật thứ hai; phải tự reconcile với BOM | 500 dòng SO/tháng = 6.000 BOM/năm; **BOM đã submit là bất biến** ⇒ không realtime được; hao hụt/nhân công phải nhét vào BOM items giả | Phức tạp hơn một chút ở ranh giới |
| Kết luận | Đúng hướng nhưng **đang ôm quá nhiều** | Không khả thi vì tính bất biến | ✅ |

**Ranh giới đề xuất cho C:**

```
  Q  ── engine BOM (giữ nguyên) ──►  al_bom_result + ConfigSnapshot
  S₀ ── engine BOM + profile STANDARD ──► AL Cost Plan (khoá)      ← phần tự xây
  S₁ ── cùng engine, tính lại ─────────► AL Cost Plan (cột sống)   ← phần tự xây
  ─────────────────────────────────────────────────────────────
  Thực thi ──► ERPNext BOM + Work Order (vật liệu hoá lúc Release)  ← core
  A  ──────► GL Entry + Stock Ledger + Payroll (dimension bucket)   ← core
  So sánh ──► AL Cost Comparison (đọc 3 nguồn trên)                 ← phần tự xây
```

Nguyên tắc: **cái gì ERPNext làm được thì không làm lại.** ERPNext làm tốt: tồn kho, giá vốn,
bút toán, Work Order, Job Card, dimension, P&L. ERPNext **không** làm được: BOM động theo kích thước,
hao hụt theo bài toán cắt, định mức nhân công theo sản phẩm. Chỉ phần thứ hai mới là hệ thống tự xây.

### Ba cảnh báo kiến trúc cụ thể

**7.1 "Hai nguồn sự thật" cho cùng một số lượng.**
`AL Cost Plan` và ERPNext `BOM` cùng nói "cần 76,98 kg nhôm". Tài liệu không định nghĩa **ai thắng**
khi lệch. Phải có quy tắc cứng: *sau Release, BOM là sự thật; mọi thay đổi phải qua Change Order,
không sửa Cost Plan*. Nếu không, sẽ có ngày hai báo cáo ra hai số và không ai truy được.

**7.2 Realtime là bẫy chi phí/độ phức tạp.**
Hook `Item Price.on_update` → quét mọi Cost Plan Active chứa item → enqueue tính lại → có thể sinh
revision. Với 200 đơn đang mở × 15 dòng, mỗi lần cập nhật bảng giá là một cơn bão job. Tài liệu có
debounce 60s và ngưỡng 0,5% — tức là tác giả đã thấy trước. Với S₀ khoá (§2), **cơn bão này biến mất**:
chỉ cần cập nhật một cột số, không revision, không thông báo.

**7.3 Formula Builder: đừng cấu hình phần cấu trúc.**
P6 nói mọi thứ là công thức FB, gồm cả công thức chênh lệch và tỷ trọng mapping. Tôi phản đối một phần.

| Nên ở FB | Nên ở code Python |
|---|---|
| Đơn giá giờ, % chi phí chung, % hao hụt, hệ số độ cao, tỷ lệ trích bảo hành | Công thức chênh lệch (4 dòng), chiều dấu, thứ tự tính, largest-remainder |
| Thứ người dùng **thật sự đổi** vài lần/năm | Thứ mà đổi sai thì **hỏng im lặng** |

Lý do: FB biến lỗi công thức thành **0** (đúng như G8 tài liệu đã nhận). Một công thức chênh lệch
trả 0 trông y hệt "không có chênh lệch". Bốn dòng Python thì test được, còn một binding sai thì im.

---

## 8. PHƯƠNG ÁN ĐỀ XUẤT

### 8.1 Mô hình — thay đổi so với tài liệu

| Hạng mục | Tài liệu | Đề xuất | Vì sao |
|---|---|---|---|
| Số bản S | 1 (realtime, revision) | **2** (S₀ khoá + S₁ sống) trên cùng 1 DocType | §2 |
| Grain A | Dòng Sales Order Item | **Project + lô sản xuất**; dòng SO = phân bổ theo S₀ | §5.3 |
| Số bucket | 12 | **9** (xem 8.2) | Ít bucket = ít gán sai = số liệu dùng được |
| Hao hụt nhôm | % từ Cutting Plan × qty tịnh | **Số cây/kg cần mua của Cutting Plan**, cấp lô | §4.1 |
| Kính | m² × (1+3,8%) | **`glass_purchase_mode`**: cắt sẵn (0 hao hụt) hoặc xếp tấm | §4.2 |
| Nhân công A | Job Card time log | **Bảng lương/chấm công phân bổ theo tổ-công trình**; Job Card chỉ cho CNC | §4.4 |
| Template theo lớp | 2 template / Product Type | **1 template + cột `layer`** trên dòng | §6 |
| Kiểm tra đóng | Σ bucket = Σ account | **Đối chiếu với GL/SLE độc lập + đối chứng dương** | §3 |
| Chi phí kỳ | Trộn vào lưới | **Tách 3 chế độ nhìn** (SX / lợi nhuận góp / toàn bộ) | §5.5 |

### 8.2 Bộ bucket khởi điểm — 9 cái, không hơn

| Bucket | Loại | Có ở Q | Có ở S | Có ở A | TK (xác nhận sau) |
|---|---|---|---|---|---|
| `VL_NHOM` | MATERIAL | ✓ | ✓ | ✓ | 621 |
| `VL_KINH` | MATERIAL | ✓ | ✓ | ✓ | 621 |
| `VL_PK` (gộp VTP + phụ kiện) | MATERIAL | ✓ | ✓ | ✓ | 621 |
| `NC_SX` | LABOR | ✓ | ✓ | ✓ | 622 |
| `NC_LD` | LABOR | ✓ | ✓ | ✓ | 622 |
| `MAY_THI_CONG` | MACHINE | — | ✓ | ✓ | **623** (nếu đơn vị theo mô hình xây lắp) |
| `CHUNG` (gộp SX/bán/quản — tách bằng mapping, không tách bucket) | OVERHEAD | ✓ | ✓ | ✓ | 627/641/642 |
| `LAM_LAI` | UNPLANNED | — | — | ✓ | 627 |
| `SCRAP_REC` (dấu âm) | RECOVERY | — | — | ✓ | 621 |
| `UNMAPPED` | CATCH-ALL | — | — | ✓ | — |

Ghi chú: `OH_SX` / `OH_VC` / `OH_QLY` **không tách thành bucket riêng** — chúng là ba tài khoản khác
nhau của cùng một khái niệm "chi phí chung". Tách bucket hay không là **quyết định của bảng mapping**,
không phải của mô hình dữ liệu. Gộp bucket giảm mạnh số dòng phải gán tay.

### 8.3 Lộ trình — cắt lại, đừng làm theo thứ tự của tài liệu

Tài liệu xếp Pha 1 đã gồm realtime + revision + Material Plan. Theo tôi, **realtime là thứ giá trị
thấp nhất và rủi ro cao nhất** — nó nên ở cuối, không phải đầu.

| Pha | Nội dung | Điều kiện vào | Nghiệm thu (đo được) |
|---|---|---|---|
| **0. Nền** | Thêm field SO Item (G1); sửa `aggregate_requirements` (G2); **bỏ `frappe.db.commit()` khỏi engine**; tách `compute`/`persist`; lưu `resolved_inputs` + mốc giá vào snapshot | — | Tạo SO từ báo giá **giữ nguyên** `al_bom*` (test tự động); submit SO không còn commit giữa transaction |
| **1. S₀ có ích ngay** | `AL Cost Profile` + `AL Cost Plan` **chỉ S₀**; nút "Tính lại" **bấm tay**; Material Plan đọc số cần mua từ Cost Plan. **Chưa có hook realtime.** | Pha 0 xong | Mở SO thấy giá thành định mức; kế hoạch mua đúng số lượng cần (có test đối chứng: cắt plan → số mua đổi) |
| **2. A đọc được** | Dimension `AL Cost Bucket`; hook tự gán bucket theo item/account; collector; báo cáo **theo tài khoản** (chưa cần mapping bucket) | **Cổng dữ liệu** (8.4) đạt | Σ Cost Fact = P&L theo project, lệch < 1.000 đ/tháng; `UNMAPPED` hiển thị được |
| **3. So sánh** | `AL Cost Mapping Set/Rule`; lưới Q·S₀·A; công thức chênh lệch; **đối chứng dương** trong test | Pha 2 ổn định 1 kỳ kế toán | Kế toán xác nhận số khớp sổ; cố tình map sai thì báo cáo **phải đỏ** |
| **4. S₁ (sống)** | Tính lại theo giá; cảnh báo "đơn đang đắt lên"; **không sinh revision** | Pha 3 xong | Không có job bão khi cập nhật bảng giá |
| **5. Nâng cao** | Allocation Run (JE), hấp thụ qua Work Order, báo cáo lãi góp, hiệu chỉnh báo giá từ dữ liệu thực | Có ≥ 3 kỳ dữ liệu sạch | Chênh lệch phân bổ đóng về 0 cuối kỳ |

**Việc tài liệu đặt ở Pha 4 nhưng tôi đề nghị bỏ hẳn khỏi phạm vi ban đầu:**
`AL Cost Allocation Run` sinh Journal Entry. Đây là chỗ **rủi ro kiểm toán** cao nhất — một engine
tự sinh bút toán phân bổ mà sai thì phải sửa sổ đã khoá. Nếu làm, phải có: duyệt, khoá kỳ, và khả
năng đảo (reversal) tự động. Cân nhắc dùng Journal Entry tay theo mẫu định kỳ thay vì tự sinh.

### 8.4 Cổng dữ liệu — điều kiện tiên quyết cho Pha 2

Tài liệu không có bước này, và đây là lý do các dự án giá thành thường thất bại: số liệu đúng về
mặt kỹ thuật nhưng **dữ liệu nguồn không đủ sạch để đúng về mặt nội dung**.

Trước khi làm lớp A, phải đo được **trên dữ liệu thật**:

| Chỉ số | Ngưỡng tối thiểu | Nếu không đạt |
|---|---|---|
| % chứng từ chi phí có `Project` | ≥ 95% | Collector sẽ bỏ sót — không được làm A |
| % vật tư có `AL Material Category` | ≥ 90% | Bucket tự gán sai — phải làm sạch master data trước |
| Số dòng `UNMAPPED` / tháng | < 2% tổng chi phí | Mapping chưa đủ — chưa được công bố báo cáo |
| Có bảng chấm công theo tổ/công trình | có, ≥ 3 tháng | Nhân công A sẽ là số bịa |
| Tồn kho nhôm/kính có đơn giá vốn đúng | ≥ 95% dòng | S₀ sai từ gốc |

Nếu không đạt, làm Pha 1 (S₀) vẫn có giá trị ngay, còn lớp A **dừng lại** cho tới khi sạch. Nói
thẳng với Owner điều này **trước** khi bắt đầu, đừng phát hiện giữa dự án.

---

## 9. NĂM CÂU CẦN OWNER CHỐT (thay cho 9 câu ở §11.3)

Tài liệu hỏi 9 câu, nhưng phần lớn là câu kỹ thuật tôi tự trả lời được. Chỉ 5 câu dưới đây **thật sự
cần Owner quyết**, vì chúng đổi phạm vi hoặc đổi cách hạch toán:

1. **Mô hình hạch toán: sản xuất (154→155→632) hay xây lắp (154→giá thành công trình)?**
   Quyết định grain, quyết định có TK 623, quyết định toàn bộ báo cáo. *Không thể trả lời bằng kỹ thuật.*

2. **S dùng để đo chênh lệch hay để dự báo?** Nếu để đo chênh lệch ⇒ phải có S₀ khoá và một quy trình
   "tái chuẩn hoá" có người duyệt. Nếu chỉ để dự báo ⇒ bỏ hẳn phần phân tích chênh lệch giá.

3. **Nhân công thực tế lấy từ bảng lương phân bổ hay từ Job Card?**
   Bảng lương = khả thi, kém chi tiết. Job Card = chi tiết, nhưng cần kỷ luật bấm giờ mà xưởng chưa có.

4. **Có chấp nhận "chi phí theo dòng hàng là số phân bổ, không phải số đo" không?**
   Nếu không chấp nhận ⇒ phải từ bỏ cắt gộp (tăng hao hụt thật) để có Work Order riêng từng dòng.

5. **Phạm vi: làm tới đâu thì dừng?**
   Đề nghị chốt trước: **dừng ở Pha 3** (Q·S₀·A so sánh được) là đã có sản phẩm dùng được. Pha 4–5
   chỉ mở khi Pha 3 chạy ổn định ≥ 2 kỳ. Đừng cam kết cả 6 pha ngay.

Riêng 4 câu kỹ thuật còn lại (giá định mức lấy từ đâu, có dùng Landed Cost, có vật liệu hoá BOM,
ngưỡng cảnh báo) — tôi đề nghị chốt mặc định: **giá vốn kho + có Landed Cost + vật liệu hoá lúc
Release + cảnh báo ±10%**, và điều chỉnh sau khi có dữ liệu thật.

---

## 10. TÓM TẮT MỘT TRANG

**Giữ:** kiến trúc 3 lớp · bucket làm ngôn ngữ chung · mapping nhiều–nhiều · `UNMAPPED` · đọc A từ sổ ·
một engine cho Q và S · cầu nối lợi nhuận Q→A.

**Sửa (quan trọng, theo thứ tự):**
1. **S thành S₀ (khoá) + S₁ (sống)** — nếu không thì chênh lệch giá luôn bằng 0.
2. **Phép kiểm đóng phải đối chứng với GL/SLE độc lập + có đối chứng dương** — hiện là tautology.
3. **Hao hụt nhôm lấy từ Cutting Plan cấp lô, không nhân thêm %** — đang tính hai lần.
4. **Kính theo `glass_purchase_mode`** — 3,8% là số không có thật.
5. **`LAM_LAI` là bucket riêng** — vỡ kính là khoản rò rỉ lớn nhất, không được giấu trong `VL_KINH`.
6. **Nhân công A từ bảng lương phân bổ**, Job Card chỉ cho CNC.
7. **Bỏ `frappe.db.commit()` khỏi engine** trước khi tái dùng cho SO.
8. **Grain chính là công trình**, dòng SO là phân bổ — và nói rõ điều đó trên báo cáo.
9. **Kiểm tra mô hình hạch toán để chốt TK 623 / 154-155**.
10. **9 bucket, không 12**; gộp `OH_*` thành `CHUNG`.

**Bỏ khỏi phạm vi ban đầu:** realtime tự động (để Pha 4) · `AL Cost Allocation Run` sinh JE (Pha 5,
và cân nhắc có làm hay không) · chia `OH_QLY` Q thành 40/60 (số bịa, gắn nhãn rõ nếu vẫn muốn xem).

**Ước lượng:** Pha 0–1 khoảng **2–3 tuần** (một DEV + test), Pha 2–3 khoảng **4–6 tuần** và **phụ
thuộc cổng dữ liệu**. Nếu cổng dữ liệu không đạt, Pha 2–3 có thể kéo dài vô hạn — đó là rủi ro lớn
nhất của dự án, không phải code.
