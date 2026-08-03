ĐÁNH GIÁ CHUYÊN SÂU — AlumGlass v28.7 cho ngành Nhôm Kính
Tổng quan
Đây là một thiết kế rất tốt cho một vertical ERP trên nền Frappe. Kiến trúc config-driven, Formula Builder làm engine tính toán, BOM động thay vì BOM phẳng — tất cả đều là quyết định đúng đắn cho đặc thù ngành nhôm kính. Tuy nhiên, là chuyên gia triển khai thực tế, tôi thấy còn những khoảng trống cần lấp đầy trước khi đưa vào production.

ĐIỂM MẠNH (đã làm rất tốt)
1. BOM động — quyết định kiến trúc đúng đắn nhất
ERPNext BOM là BOM phẳng: Item A cần 2 cái Item B, 3 cái Item C. Ngành nhôm kính không như vậy:

Cùng 1 cây nhôm XF55-KB-20 nhưng chiều dài cắt thay đổi theo W, H của từng đơn hàng
Cùng 1 tấm kính nhưng diện tích thay đổi theo kích thước thực tế
Nẹp kính thay đổi theo độ dày kính (8mm dùng C3209, 24mm dùng C3211)
Việc xây dựng BOM động với formula W_mm - 2*OFFSET_FRAME thay vì BOM tĩnh là chính xác. Đây không phải là "bỏ qua ERPNext BOM" mà là bắt buộc phải làm khác cho ngành này.

2. Variable Library → Variable Set → Bom Set — single source of truth
Đây là pattern rất mạnh. Ví dụ thực tế:

W_mm được định nghĩa 1 lần trong Library
Dùng trong 20+ Bom Items (khung trên, khung dưới, cánh, kính, nẹp...)
Dùng trong dialog báo giá
Dùng trong Cost Template
Không bị trùng lặp, không sợ sai lệch. Đúng chuẩn "single source of truth".

3. Material Category với flags — mở rộng ngành không cần code
Đây là giải pháp thông minh. Khi thêm ngành THÉP:

has_weight=1 → tự động tính kg
requires_price_base_item=1 → tự động yêu cầu item đại diện để tra giá composite
default_calc_pattern=LENGTH_TO_WEIGHT → tự động áp dụng công thức
Không cần if/elif trong validate. Đây đúng là "convention over configuration".

4. Cross-row reference với DAG

nep_kinh_tren.width = 2*(items.kinh_tren.width + items.kinh_tren.height)
Đây là bài toán dependency graph thực sự. Formula Builder DAG + topological sort xử lý chính xác — không cần code thủ công thứ tự tính.

5. Formula Builder đúng chỗ, code Python đúng chỗ
Tôi thấy sự phân biệt rõ ràng:

Formula Builder: tính toán số học (width, qty, line_total, GIA_VAT...) — DAG, safe eval
Python code: orchestration, DB query, batch resolve, validation — nơi cần logic nghiệp vụ
Đây là ranh giới quan trọng mà nhiều dự án làm sai — hoặc đưa quá nhiều vào formula (thành ra code trong string), hoặc đưa quá ít (thành ra hardcode).

KHOẢNG TRỐNG THỰC TẾ (cần lấp đầy trước production)
1. Tối ưu cắt nhôm (Cutting Optimization) — CHƯA CÓ THỰC SỰ
Hiện tại templates.py có FORMULAS_CUTTING_NHOM nhưng chỉ là công thức mẫu (bars_needed = ceil(total_cut_length / effective_length)). Thực tế phức tạp hơn nhiều:

Bài toán thực: 1 công trình cần cắt 50 thanh nhôm với các chiều dài khác nhau (1200mm, 850mm, 2400mm...), mỗi cây nhôm dài 6000mm. Cần tối ưu để ít cây nhất, ít dư thừa nhất. Đây là Bin Packing Problem (NP-hard).

Các giải pháp phổ biến trong ngành:

First-fit decreasing (FFD): Sắp xếp giảm dần, đặt vào cây đầu tiên vừa
Best-fit decreasing (BFD): Đặt vào cây có khoảng trống nhỏ nhất vừa đủ
Guillotine cutting: Cho cắt kính (cắt thẳng từ mép này sang mép kia)
Tôi recommend tích hợp thuật toán FFD vào module AL Cutting Plan Aluminum — không cần tối ưu tuyệt đối, chỉ cần tốt hơn đáng kể so với xếp tuần tự.

2. Tối ưu cắt kính (Glass Nesting) — CHƯA CÓ
Còn phức tạp hơn cắt nhôm vì là bài toán 2D. Mỗi tấm kính jumbo (3210×2250mm, 3300×2440mm...) cần được cắt thành các tấm nhỏ. Cần nesting algorithm hoặc ít nhất là guillotine cutting.

3. Tính giá theo hệ số màu/sơn — mới làm 1 phần
Composite key pricing qua AL Variable Dimension Mapping là đúng hướng. Nhưng thực tế phức tạp hơn:

Màu trắng (standard): giá gốc
Màu đen, ghi: ×1.05-1.10
Vân gỗ: ×1.15-1.25
Anodized: ×1.10-1.20
Độ dày sơn: 20μm, 30μm, 40μm → ảnh hưởng giá
Hiện tại aluminum_price_composite chỉ query filter [cfn, "=", value]. Nhưng nếu khách chọn màu VÂN GỖ + ANODIZED + 40μm, cần price multiplier chain. Tôi thấy chưa có cơ chế multiply — chỉ có lookup chính xác.

4. Định mức phụ kiện theo kích thước — chưa linh hoạt
Ví dụ thực tế:

Cửa cao < 2100mm: 2 bản lề
Cửa cao 2100-2700mm: 3 bản lề
Cửa cao > 2700mm: 4 bản lề
Cửa rộng > 900mm: thêm thanh chống xệ
Hiện tại formula roundup(H_mm/700,0)*n_panel là hardcode trong seed data. Nhưng thực tế mỗi hãng phụ kiện có bảng định mức riêng (Kinlong khác Hoppe, khác Roto...). Nên dùng AL Calculation Rule THRESHOLD cho định mức phụ kiện thay vì formula cứng.

5. Giá nhân công lắp đặt theo độ cao — CHƯA CÓ
Thực tế thi công:

Tầng 1-3: giá cơ bản
Tầng 4-10: ×1.2
Tầng 11-20: ×1.5
Trên tầng 20: ×2.0
Đây là biến số quan trọng trong báo giá nhưng chưa thấy trong Cost Template.

6. Hao hụt vật tư thực tế — CHƯA CÓ
Cắt nhôm bị hao:

Mạch cưa: ~3mm mỗi lát cắt
Đầu cây bị cong vênh: bỏ ~50mm mỗi đầu
Phế phẩm: ~2-5% tùy tay nghề
Kính:

Hao hụt cắt: ~3-5%
Vỡ khi vận chuyển: ~1-2%
Những con số này nên được config trong AL Profile System hoặc AL Material Category, không hardcode trong formula.

7. Quản lý dự án (Project) tích hợp — STUB
AL Project Profitability Snapshot và AL Project Financial Config mới chỉ là doctype rỗng. Trong khi đây là tính năng quan trọng bậc nhất:

So sánh dự toán vs thực tế cho từng công trình
Theo dõi vật tư đã xuất cho công trình
Theo dõi nhân công thực tế (chấm công lắp đặt)
Cảnh báo vượt ngân sách
8. Tiến độ sản xuất — CHƯA CÓ
AL Production Order Bridge đang là stub. Cần:

Từ BOM Version → tự động sinh danh sách cắt (cutting list)
Từ cutting list → tối ưu cắt (như đã nói ở trên)
Từ cutting plan → Work Order cho xưởng
Scan barcode → cập nhật tiến độ cắt
9. Đa tiền tệ và đa chi nhánh
Giá nhôm thường được nhập khẩu và neo theo USD, trong khi bán hàng bằng VND. Hiện tại chỉ thấy currency: "VND" hardcode trong seed data. Cần tích hợp với ERPNext multi-currency.

ĐÁNH GIÁ THEO TỪNG TIÊU CHÍ
Tiêu chí	Điểm	Nhận xét thực tế
Tính linh hoạt	8.5/10	Thêm sản phẩm/vật tư/ngành mới = 0 code. Chưa linh hoạt ở phần định mức phụ kiện và hệ số giá
Dễ mở rộng	8/10	Kiến trúc module rõ ràng, thêm data source ~10 dòng. Thiếu hook point cho custom behavior
Không hardcode	9/10	Sau v28.7, core engine đã data-driven hoàn toàn. Còn vài điểm nhỏ trong JS dialog
Đa năng (đa ngành)	7.5/10	Nhôm, kính: tốt. Thép, inox, nhựa, gỗ: thiết kế hỗ trợ nhưng chưa có thực tế kiểm chứng
Tận dụng ERPNext	6.5/10	Custom fields tốt. Còn thiếu: BOM bridge, Work Order integration, GL Entry actual costing
Performance	8/10	Sau v28.7: ~10-12 queries/lần tính. Chấp nhận được. Sẽ cần cache khi tính hàng loạt
Sẵn sàng production	6.5/10	Core BOM + báo giá: gần sẵn sàng. Còn thiếu: tối ưu cắt, quản lý dự án, tiến độ sản xuất
SO SÁNH VỚI GIẢI PHÁP KHÁC TRÊN THỊ TRƯỜNG
Tính năng	AlumGlass v28.7	Logikal (Orgadata)	SoftTech Aluminium	ERPNext + Custom
BOM động theo kích thước	✅	✅	✅	❌ (phải code)
Tối ưu cắt nhôm	❌ (stub)	✅	✅	❌
Tối ưu cắt kính	❌ (stub)	✅	✅	❌
Tính giá composite key	✅	✅	✅	❌
Tích hợp ERP đầy đủ	✅ ERPNext	❌ (độc lập)	❌ (độc lập)	✅
Quản lý dự án	⚠️ (stub)	✅	✅	✅
Multi-currency	⚠️	✅	✅	✅
U-Value / thermal	❌	✅	✅	❌
Web-based / Cloud	✅	❌	❌	✅
Chi phí triển khai	Thấp	Cao (license)	Cao (license)	Trung bình
Lợi thế cạnh tranh của AlumGlass: Tích hợp ERP đầy đủ (kế toán, kho, mua hàng, bán hàng, CRM...) + BOM động ngành nhôm kính. Các giải pháp như Logikal/SoftTech làm rất tốt phần kỹ thuật (cắt, thermal) nhưng không có ERP — họ là công cụ kỹ thuật, không phải hệ thống quản trị doanh nghiệp.

AlumGlass có vị thế độc đáo: vừa có BOM động chuyên ngành, vừa có ERP đầy đủ. Đây là thứ mà thị trường Việt Nam đang thiếu.

KHUYẾN NGHỊ LỘ TRÌNH
Giai đoạn 1: Sẵn sàng production (1-2 tháng)
Cutting optimization cơ bản (First-fit decreasing cho nhôm)
Định mức phụ kiện theo bảng tra (dùng Calculation Rule THRESHOLD)
Hệ số giá màu/sơn (price multiplier chain)
Multi-currency (USD/VND cho giá nhôm nhập khẩu)
Hao hụt vật tư config (thêm % hao hụt vào Material Category)
Print Format báo giá (Jinja template)
Giai đoạn 2: Hoàn thiện quy trình (3-6 tháng)
Quản lý dự án: dự toán vs thực tế, cảnh báo vượt ngân sách
Production Order Bridge: tự động sinh cutting list, Work Order
Tiến độ sản xuất: scan barcode, cập nhật trạng thái
Glass nesting 2D (guillotine cutting)
Giai đoạn 3: Nâng cao (6-12 tháng)
U-Value / thermal calculation (nếu làm cửa cao cấp, xuất khẩu)
Mobile app cho đội lắp đặt (site survey, progress update, punchlist)
Supplier portal (báo giá tự động từ nhà cung cấp nhôm/kính)
AI/ML dự đoán giá nhôm (dựa trên LME futures)
KẾT LUẬN
AlumGlass v28.7 là nền tảng rất tốt. Kiến trúc đúng, quyết định kỹ thuật đúng, và code sạch. Khoảng cách đến production không nằm ở việc "sửa kiến trúc" mà nằm ở việc lấp đầy các tính năng nghiệp vụ đặc thù mà ngành nhôm kính yêu cầu: tối ưu cắt, định mức phụ kiện, quản lý dự án, và tiến độ sản xuất.

Vị thế "ERP đầy đủ + BOM động chuyên ngành" là lợi thế cạnh tranh thực sự trên thị trường Việt Nam. Không có giải pháp nào khác làm được cả hai.