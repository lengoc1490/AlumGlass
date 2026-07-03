# BÁO CÁO HỢP NHẤT — AlumGlass ERP Canonical (v17 → v21)

## 1. Nguồn dữ liệu đầu vào (7 file)

| File | Vai trò thực tế phát hiện được | Dùng trong canonical? |
|---|---|---|
| `AlumGlass_ERP_v17_FINAL.md` (3048 dòng) | Đặc tả chi tiết field-level v17, nền tảng Tầng 1-2 | Gián tiếp — đã được v19_FULL kế thừa đầy đủ |
| `AlumGlass_ERP_v17_REVIEW.md` (811 dòng) | Review kiến trúc, đề xuất P0-P4 (chuyển sang Formula Variable Binding...) | Gián tiếp — các đề xuất đã thành Nguyên tắc #16-19, không cần chép lại văn bản review |
| `AlumGlass_v18_Upgrade_Spec.md` (2240 dòng) | Dynamic Item Rule, Formula Variable Binding | Gián tiếp — đã được v19_FULL kế thừa đầy đủ |
| `AlumGlass_ERP_v19_MASTER_DESIGN.md` (612 dòng) | Bản tóm tắt/con trỏ (pointer doc) — không tự thân | Không dùng trực tiếp — v19_FULL đã bao trùm |
| `AlumGlass_ERP_MASTER_v19_FULL.md` (1434 dòng) | **Bản đầy đủ, sạch, tự thân, không trùng lặp** — 59 DocType, field-level đầy đủ | **BACKBONE chính của canonical** |
| `AlumGlass_ERP_v20_MASTER_DESIGN.md` (497 dòng) | Delta thật sự trên v19_FULL: fix P0 tồn kho màu (§IV) + chiến lược AI-First (§XII) | Toàn bộ nội dung mới đã được ghép vào §4.23, §II, §XX, §XXV, §XXIX, §XXXII, §XXXIV, §XXXV, §XXXVI |
| `AlumGlass_ERP_v21_0.md` (12593 dòng, chứa 50% trùng lặp) | Chỉ 2 điểm mới thật sự: QĐ-21→25 và `AL AI Interaction Log` — phần còn lại là copy lỗi của 6 file trên | Phần mới (QĐ-21→25) đã ghép vào §I, §XIII, §XIV, §XVI, §4.17, §29.2a/b. Phần trùng lặp bị loại bỏ hoàn toàn |

## 2. Phát hiện quan trọng trong quá trình merge

1. **`v21_0.md` không phải là bản hợp nhất thật** — nó chứa 90% nội dung v17_FINAL và 82% v18_Upgrade_Spec (do copy-paste) nhưng chỉ 1-5% nội dung của v17_REVIEW, v19_MASTER_DESIGN, v20_MASTER_DESIGN. Nếu dùng v21_0 làm nguồn chính (như lần merge trước), toàn bộ fix P0 tồn kho màu (v20) và chiến lược AI-First mở rộng (v20) sẽ **bị mất hoàn toàn** dù chúng là những cải tiến quan trọng nhất.
2. **`AlumGlass_ERP_MASTER_v19_FULL.md` mới là bản chuẩn thật sự** ở thời điểm v19 — sạch, đầy đủ, không trùng lặp, tự thân. Đây là lý do được chọn làm backbone thay vì cố dedupe v21_0.
3. Phát hiện và sửa 1 lỗi tự mâu thuẫn còn sót trong bản gốc: §25.4 (AL Glass Cut Order) và luồng cắt kính vẫn nhắc `item_variant` dù §4.23 đã cấm dùng Item Variant cho tồn kho màu — đã sửa đồng bộ.

## 3. Nội dung đã lớp vào canonical

**Từ v20 (5 điểm):**
- Nguyên tắc #22, #23
- §4.23 — Sửa lỗi kiến trúc tồn kho màu (AL Color Standard, cơ chế Batch, AL Project Warehouse Map, migration) — đầy đủ 7 mục con
- §29 — Ma trận AI-First mở rộng (9 use case mới: Drawing-to-BOM, Pricing Advisor, Purchasing Forecast, Voice-to-Progress, Root Cause Clustering, RAG nội bộ...) + 3 nguyên tắc quản trị AI-G1/G2/G3
- Cập nhật MRP Lite (§XX), Cutting Plan (§XXV), Phân quyền (§XXXII), Lộ trình Phase 0-8 (§XXXIV)
- 2 DocType mới: `AL Color Standard`, `AL Project Warehouse Map`

**Từ v21 (6 điểm — QĐ-21 đến QĐ-25 + 1 DocType):**
- Nguyên tắc #24, #25
- QĐ-21: ConfigSnapshot Compressed (field `compressed_snapshot`)
- QĐ-22: Sales Override Kiểm Soát (field `allow_sales_override`, `override_item_group` trên Profile Line/PK Line)
- QĐ-23: AI Hooks Framework (3 hook point chuẩn hóa)
- QĐ-24: CostAccumulator v2 Fallback Logging (đã có sẵn tinh thần trong v19_FULL, chỉ gắn nhãn xác nhận)
- QĐ-25: DynamicItemResolver v2 (định dạng trả về chuẩn hóa)
- DocType mới: `AL AI Interaction Log`

## 4. Số liệu trước/sau

| | v19_FULL (backbone gốc) | Canonical (kết quả) |
|---|---|---|
| Số dòng | 1.434 | 1.601 |
| Số DocType | 59 | 62 |
| Số Nguyên tắc | 21 | 25 |
| Số Quyết định kiến trúc bổ sung (QĐ) | 0 (chưa có mục riêng) | 5 (QĐ-21→25) |
| Số rủi ro theo dõi | 22 | 26 |

## 5. Việc CHƯA làm (cần bạn xác nhận trước khi triển khai)

- **Không dùng nội dung nào từ `v17_REVIEW.md` dạng văn bản gốc** (chỉ dùng kết luận/quyết định đã được các bản sau adopt). Nếu bạn cần giữ lại lịch sử review đầy đủ (lý do kỹ thuật chi tiết so sánh AL vs formula_builder), nên lưu file này riêng như phụ lục tham khảo, không cần đưa vào spec triển khai.
- **Không dùng `v19_MASTER_DESIGN.md`** vì toàn bộ nội dung đã nằm trong `v19_FULL.md` ở dạng đầy đủ hơn.
- Phần code mẫu (Python) trong `v17_REVIEW.md` §8 không đưa vào theo đúng yêu cầu "chưa cần code triển khai".
