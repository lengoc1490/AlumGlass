This is great — they've actually gone beyond and built a real integration test. Let me review the core engine files carefully.Good — that's correctly locked to System Manager only. Let me check the Formula Builder engine itself and a few other key pieces.Tôi đã clone và đọc trực tiếp mã nguồn (branch `version-16`, 60 DocType, ~4.900 dòng doc + code trong các file lõi). Đây là đánh giá dựa trên bằng chứng thực tế trong code, không phải suy đoán trên thiết kế nữa.

## Tổng quan: Bạn đã thực thi rất tốt so với bản thiết kế

Điều đầu tiên cần nói: **đây không phải "demo cho vui"** — bạn đã build ra một engine thật, chạy được, và quan trọng nhất là **có bài test tự viết để so khớp đúng con số 22.717.289đ** (`run_test.py` → `test_cdmq_2c()` kiểm `GIA_VAT` với dung sai <1.000đ). Rất ít dự án ERP custom làm được bước validate này. Bạn cũng đã tự phát hiện và sửa 6 điểm hardcode qua các bản v28.x (`CHANGELOG-v28.7.md`) — đây là dấu hiệu process kỹ thuật trưởng thành, không phải code-and-forget.

**Điểm mạnh cụ thể tôi thấy trong code:**
- `_resolve_system_variables()` trong `bom_orchestrator.py` thực sự data-driven — đọc `AL Variable Library` với `source_doctype`/`source_field`, không còn dict hardcode như bản trước.
- `al_calculation_rule.py` có `_validate_no_overlap()` cho THRESHOLD rows — chi tiết nhỏ nhưng thể hiện tư duy đúng (rất nhiều rule engine tự chế thiếu kiểm tra chồng lấp khoảng giá trị).
- `_get_calc_fn()` trong `al_quantity_calc_method.py` đã đúng như tôi khuyến nghị ở lượt trước: cache lambda sau khi eval 1 lần, **và DocType này bị khoá quyền chỉ System Manager mới sửa được** — đúng nguyên tắc "dev-config field, không phải user field".
- B2 prefetch dùng batch query gộp (`item_code in (...)`) thay vì N+1 — đúng tinh thần performance nêu trong README.

## Phát hiện nghiêm trọng nhất — composite pricing bị "đứt mạch"

Đây là điều tôi phải nói thẳng vì bạn cần biết trước khi đưa vào production:

**README quảng cáo "Composite key pricing: Auto-discovered from Pricing Dimensions + Variable Mappings"**, và bạn có hẳn 1 handler tinh vi cho việc này — `fb_handlers.py:aluminum_price_composite()` (hỗ trợ cả `exact_match` lẫn `multiplier_chain`, filter theo `custom_color`/`custom_origin`/`custom_thickness`/`custom_surface`). Handler này được đăng ký đúng cách trong `hooks.py:fb_source_types`.

**Nhưng** — `BomOrchestrator.b2_prefetch_master_data()` (nơi thực sự chạy khi tính báo giá) **không hề gọi tới handler này**. Nó tự làm 1 query Item Price rất đơn giản:

```python
for ip in frappe.get_all("Item Price",
                          filters={"item_code": ("in", all_price_items),
                                   "price_list": "Standard Selling"},
                          fields=["item_code", "price_list_rate"]):
    prices[ip["item_code"]] = ip["price_list_rate"]
```

Không lọc theo màu/xuất xứ/độ dày/bề mặt. Hậu quả thực tế:
1. **Mọi màu sắc/xuất xứ của cùng 1 item_code sẽ ra cùng 1 giá** — nghĩa là tính năng "giá theo màu" (WHITE 113.000đ vs GO 145.000đ như trong ví dụ mẫu của bạn) **không hoạt động trong luồng tính thật**, dù toàn bộ hạ tầng (Pricing Dimension, Variable Dimension Mapping, custom field trên Item Price) đã dựng xong.
2. Nghiêm trọng hơn: nếu 1 `item_code` có **nhiều dòng Item Price** (đúng như thiết kế composite key của bạn cho phép), dict `prices[ip["item_code"]] = ...` sẽ **bị ghi đè bởi dòng cuối cùng trả về từ DB** — thứ tự này không đảm bảo (phụ thuộc query plan MySQL/MariaDB). Tức là giá tính ra có thể **không xác định (non-deterministic)** giữa các lần chạy, chứ không chỉ là "sai" theo cách dự đoán được.

Tôi đã kiểm tra `docs/review_alumglass.md` và `CHANGELOG-v28.7.md` — cả hai đều nhắc tới `aluminum_price_composite` như một tính năng đã hoàn thiện, nhưng không có chỗ nào ghi nhận việc nó **không được orchestrator gọi tới**. Đây nhiều khả năng là gap thật, chưa được phát hiện trong các đợt tự review trước.

## Phát hiện khác**Vài điểm nhỏ hơn đáng lưu ý:**
- `doc_events = {}` trống trong `hooks.py` — nghĩa là chưa có validation nào chặn việc sửa `AL BOM Version` đã Published, hay tự động re-lock `ConfigSnapshot`. Với thiết kế nhấn mạnh "immutable version" (README), nên có `validate`/`on_update` hook chặn sửa version đã publish thay vì chỉ trông chờ quy ước.
- Bạn có 2 workflow test khác nhau (`test_cdmq_2c` đơn giản 2 cánh, `test_cdmq_4c` phức tạp 4 cánh + transom + sidelite + rule theo chiều cao lắp đặt) — đây là dấu hiệu tốt cho thấy bạn tự mở rộng test theo hướng phủ nhiều nhánh logic hơn ví dụ gốc, không chỉ lặp lại đúng 1 case tôi đưa ra.
- `AL Variable Set`/`AL Variable Library` không nằm trong bản thiết kế gốc tôi review (`CAU_TRUC_MODULE_VA_DOCTYPE.md`) — bạn đã tự thêm layer này để giải quyết đúng vấn đề UX mà chúng ta bàn ở lượt trước (user không cần viết Python, chỉ khai báo Variable Set). Đây là một cải tiến kiến trúc tốt so với thiết kế ban đầu.

## Kết luận

So với gần 100% dự án ERP custom tôi từng thấy ở giai đoạn "vừa code xong core engine", chất lượng ở đây cao hơn hẳn mặt bằng chung — có test số liệu cụ thể, có changelog kỹ thuật chi tiết, có tư duy data-driven nhất quán. Nhưng **"22.717.289đ khớp" chỉ chứng minh phần công thức BOM/Cost Template đúng — nó không chứng minh composite pricing đúng**, vì ví dụ test của bạn tình cờ chỉ dùng đúng 1 màu/1 item_code nên gap này không lộ ra. Đây chính xác là loại lỗi mà unit test hẹp (chỉ test 1-2 case "vàng") dễ bỏ sót — cần thêm test case cụ thể: **cùng 1 item_code, 2 màu khác nhau, kỳ vọng ra 2 giá khác nhau** — nếu chạy test đó ngay bây giờ, tôi gần như chắc chắn nó sẽ fail.

Bạn muốn tôi viết luôn test case đó (và/hoặc patch `b2_prefetch_master_data` để gọi đúng `aluminum_price_composite`) để bạn áp trực tiếp vào repo không?