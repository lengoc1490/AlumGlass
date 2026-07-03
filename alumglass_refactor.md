# 🚀 MASTER PROMPT – ALUMGLASS v17 → v18 (ARCHITECT + IMPLEMENTATION MODE)

## 1. 🎯 ROLE
Bạn là:
- Senior ERP Architect (Frappe/ERPNext core-level)
- Formula Engine Designer (DAG, dependency graph)
- Low-code platform architect
- Manufacturing system expert (BOM, costing, PK logic)

👉 Bạn KHÔNG chỉ implement
👉 Bạn phải **review → phản biện → nâng cấp → thiết kế lại nếu cần**

## 2. 📥 INPUT
Tôi cung cấp:
- alumglass/AlumGlass_ERP_v17_FINAL.md
- alumglass/AlumGlass_ERP_v17_REVIEW.md

## 3. 🎯 MỤC TIÊU v18
### 3.1 Chuẩn hóa Formula
- TẤT CẢ formula fields → `Small Text`
- Không còn Code field, Hardcoded Python logic
- 100% chạy qua FormulaEngine

### 3.2 Dynamic Item Selection (QUAN TRỌNG)
Cho phép 2 chế độ:
1. Fixed Item
2. Dynamic Item (formula-based)

### 3.3 KIẾN TRÚC BẮT BUỘC
Hệ thống phải đạt:
- Zero Python in DB logic
- DAG-based execution
- Config-driven 100%
- Reusable Formula Engine
- AI-ready

## 4. 🚨 STEP 1 – ĐÁNH GIÁ v17 (BẮT BUỘC)
Trước khi nâng cấp, bạn phải trả lời:
- Kiến trúc v17 có vấn đề gì? (Có re-invent formula_builder? Duplicate engine? Hardcode logic?)
- Chấm điểm: Architecture, Scalability, Low-code readiness, AI readiness (/10)

## 5. 🔎 STEP 2 – IMPACT ANALYSIS
Nếu áp dụng Small Text migration và Dynamic Item Selection:
- Có phá vỡ DAG không?
- Có tạo circular dependency không?
- Có ảnh hưởng performance không?

## 6. 🧠 STEP 3 – THIẾT KẾ v18 (QUAN TRỌNG NHẤT)
### 6.1 FORMULA STANDARDIZATION
Liệt kê TẤT CẢ fields cần chuyển → Small Text, Mapping v17 → v18

### 6.2 DYNAMIC ITEM SELECTION – DESIGN CHUẨN
❌ KHÔNG được làm theo cách naive. Bạn PHẢI chọn 1 trong 2 kiến trúc:
- **OPTION A – Pre-Resolution Phase (RECOMMENDED)**: INPUT → DynamicItemResolver → Inject item_code → DAG → FormulaEngine
- **OPTION B – Inline DAG Resolution**: item_code là 1 node trong DAG

👉 Bạn phải: So sánh 2 approach, Chọn 1, Giải thích vì sao

### 6.3 SCHEMA DESIGN (FINAL)
Update `AL Profile Line` và `AL PK Line` với:
- `item_selection_mode` (Select: Fixed/Dynamic)
- `item_condition_formula` (Small Text)
- `item_fallback` (Link → Item)
👉 Phải include: Fieldtype, Default, Validation rule

### 6.4 DYNAMIC ITEM RESOLVER (CODE)
Viết Pseudocode + Python sample. Bao gồm: Evaluate formula, Resolve item_code, Inject vào context.

### 6.5 DAG INTEGRATION
Giải thích: item_condition_formula nằm ở đâu trong DAG? dependency resolve như thế nào? tránh circular ra sao?

### 6.6 BOM ORCHESTRATOR (UPDATED FLOW)
Phải redesign flow: 1. Input normalize → 2. Dynamic Item Resolve → 3. Profile Pass 1 → 4. Profile Pass 2 → 5. Formula DAG execute → 6. Cost aggregation → 7. Snapshot

### 6.7 COST + KG + PRICE INJECTION
Sau khi resolve item: lấy kg_per_m, price, inject lại vào context. Giải thích rõ timing.

## 7. 🧪 STEP 4 – IMPLEMENTATION
- Migration Script: alter field → Small Text, default mode = Fixed
- Backward Compatibility: v17 data vẫn chạy được, không phá BOM cũ
- UI Changes: show dynamic item, highlight resolved item, error handling
- Override Logic: Sales có thể override → override > dynamic formula

## 8. ⚠️ STEP 5 – RISK & EDGE CASE
Phải phân tích: Formula trả về item không tồn tại, Circular dependency, Performance khi 100+ formulas, Multi-tenant conflict

## 9. 🚀 STEP 6 – ADVANCED UPGRADE (BẮT BUỘC)
- Performance: caching formula, compile DAG, batch execution
- AI Integration: AI generate item_condition_formula, AI detect sai config, AI suggest PK
- Platform Direction: Sau v18 có thể trở thành Low-code ERP platform? Configurable manufacturing engine?

## 10. 📤 OUTPUT FORMAT
Bạn phải trả về # AlumGlass_v18_Upgrade_Spec.md bao gồm: 1. v17 Audit, 2. Impact analysis, 3. v18 Architecture, 4. Schema changes, 5. Code (resolver), 6. Data flow, 7. Migration, 8. Risk, 9. Advanced upgrade

## 🚨 RULES
- Không trả lời chung chung
- Không lặp lại input
- Phải có reasoning rõ
- Phải thực tế implement được trên Frappe
- Nếu v17 sai → PHẢI sửa

## 🎯 END GOAL
Sau khi đọc output của bạn, tôi có thể: Refactor hệ thống ngay, Implement ngay, Không cần suy nghĩ lại kiến trúc.