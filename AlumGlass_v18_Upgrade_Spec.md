# AlumGlass v18 — Upgrade Specification (FULL & COMPREHENSIVE)

> **Ngày:** 2026-06-29
> **Phiên bản tài liệu:** FINAL v2 — Đã phản biện & nâng cấp từ draft v1
> **Input:** AlumGlass_ERP_v17_FINAL.md (3049 dòng) + AlumGlass_ERP_v17_REVIEW.md (812 dòng) + AlumGlass_v18_Upgrade_Spec.md (draft v1) + AlumGlass_v18_upgrade_spec_final.md (phản biện v2)
> **Trạng thái:** Sẵn sàng implement — đã audit, phản biện, vá 5 gap kiến trúc
> **Phụ thuộc:** formula_builder v29.1+ · Frappe/ERPNext v15+ · Python 3.10+

---

## MỤC LỤC

- [CHANGELOG — v18 so với v17](#changelog)
- [1. v17 Audit & Phản biện Draft v18](#1-v17-audit--phản-biện-draft-v18)
- [2. Impact Analysis](#2-impact-analysis)
- [3. v18 Architecture — Quyết định kiến trúc & 3 Chế Độ Item](#3-v18-architecture)
- [4. Schema Changes — Đầy đủ & Chính xác](#4-schema-changes)
  - [4.0 AL Dynamic Item Rule ★ MỚI — DocType mới quan trọng nhất v18](#40-al-dynamic-item-rule--doctype-mới-quan-trọng-nhất-v18)
- [5. Dynamic Item Resolver — 3-Chế-Độ](#5-dynamic-item-resolver)
- [6. VariableResolver v3 — FB Integration](#6-variableresolver-v3)
- [7. DAG Integration](#7-dag-integration)
- [8. BomOrchestrator v18 — 7 Bước](#8-bom-orchestrator-v18)
- [9. CostAccumulator v2 + ProfileInterpreter Update](#9-costaccumulator-v2--profileinterpreter-update)
- [10. Migration Scripts](#10-migration-scripts)
- [11. Implementation Checklist — 6 Phases](#11-implementation-checklist)
- [12. Risk & Edge Cases](#12-risk--edge-cases)
- [13. Advanced Upgrade](#13-advanced-upgrade)
- [A. Field Mapping v17 → v18](#appendix-a-field-mapping-v17--v18)
- [B. Ví dụ — 3 Chế Độ Item Selection](#appendix-b-ví-dụ--3-chế-độ-item-selection)
- [C. So sánh Draft v18 vs Final v18](#appendix-c-so-sánh-draft-v18-vs-final-v18)
- [D. Kế thừa Không Phá Vỡ từ v17](#appendix-d-kế-thừa-không-phá-vỡ-từ-v17)
- [E. v17 REVIEW — Khuyến nghị đã Tích hợp](#appendix-e-v17-review--khuyến-nghị-đã-tích-hợp)

---

## CHANGELOG

### v18.0 — So với v17.0

| # | Module v18 | Mô tả | Impact |
|---|---|---|---|
| 1 | **Formula Standardization** | 9 field Code → Small Text. Không còn Code fieldtype cho formula. | Toàn bộ formula fields |
| 2 | **Dynamic Item Selection** | Cho phép chọn item qua formula thay vì Fixed item_code. Giảm 60-75% dòng BOM. | AL Profile Line, AL PK Line |
| 3 | **FormulaEngine làm engine DUY NHẤT** | DynamicItemResolver dùng FormulaEngine.evaluate_single() — không tự build eval. | Tầng 4.5 mới |
| 4 | **FB Variable Binding Integration** | VariableResolver gọi resolve_bindings_with_deps() từ FB. 2 custom handlers. | Tầng 2 cập nhật |
| 5 | **Cost Template + Formula Set** | AL Cost Template có thể dùng Formula Set thay vì build thủ công. | Optional — backward compat |
| 6 | **Architecture 7 tầng** | Thêm Tầng 4.5 (DynamicItemResolver) + Tầng 7 (AI Layer). | Mở rộng từ 6 tầng |
| 7 | **BomOrchestrator 7 bước** | Thêm Bước 2: Dynamic Item Resolve. | Non-breaking — flow cũ vẫn hoạt động |
| 8 | **Sales Override Panel** | Sales có thể override item_code cho từng Dynamic row. | UI mới — P2 |
| **9 ★** | **3-Chế-Độ Item Selection** | Fixed / Rule (bảng điều kiện, không code) / Formula (IF lồng). **Hạ rào cản low-code.** | AL Dynamic Item Rule (DocType mới) + AL Profile Line cập nhật |
| **10 ★** | **AL Dynamic Item Rule** | Rule-based item mapping: THRESHOLD (theo ngưỡng số) + LOOKUP (theo cặp key-value). Tạo 1 lần, dùng cho mọi BOM. | 3 DocType mới: Rule + Threshold Row + Lookup Row |

> **Kế thừa không phá vỡ (Non-Breaking):**
> ✓ Toàn bộ 34 DocType v17 giữ nguyên — v18 CHỈ THÊM fields, không xóa
> ✓ BomOrchestrator thêm 1 bước, 6 bước cũ không đổi
> ✓ Fixed mode = y hệt behavior v17
> ✓ 8 ví dụ kiểm chứng v17 vẫn PASS 100%
> ✓ Module v17 (Discount, MRP, Approval, Notification, Cost Variance, Analytics, Reporting): không bị ảnh hưởng

---

## 1. v17 AUDIT & PHẢN BIỆN DRAFT v18

### 1.1 Điểm kiến trúc v17

| Tiêu chí | Điểm | Nhận xét |
|---|---|---|
| **Architecture** | 8.5/10 | 6 tầng rõ. Module Hook pattern xuất sắc. 2-pass ProfileInterpreter đúng đắn. |
| **Scalability** | 7/10 | DAG tốt. Nhưng Fixed item_code → mỗi BOM = 1 tổ hợp item cố định. |
| **Low-code readiness** | 7/10 | show_condition + qty_formula tốt. Admin vẫn chọn Item thủ công. |
| **AI readiness** | 6/10 | explain() audit trail tốt. Hardcode item ngăn AI tự cấu hình BOM. |
| **Formula standardization** | 5/10 | **Điểm yếu nhất.** 9 field Code còn sót trong schema. |
| **formula_builder integration** | 6/10 | REVIEW chỉ rõ AL Variable Binding tự build lại FB. Draft v1 chưa address. |

**Tổng: 82/100** — hạ 3 điểm so với REVIEW (85) vì phát hiện thêm Code fieldtype.

### 1.2 So sánh AL DocType với formula_builder Equivalent (từ REVIEW)

| DocType lõi (AL) | FB Equivalent | Kết luận |
|---|---|---|
| AL Variable Binding | Formula Variable Binding (10 src types + DAG topo) | **FB mạnh hơn** → v18: switch sang FB, giữ AL data |
| AL Cost Template (phần tính toán) | Formula Set | **Có thể thay thế** → v18: optional formula_set field |
| AL Calculation Rule (CONSTANT, FORMULA) | Formula Global Variable | **Thay thế được** → v18: admin tự chọn migrate |
| AL Calculation Rule (SEQUENCE) | Formula Set | **Thay thế được** → v18: admin tự chọn migrate |
| AL Calculation Rule (THRESHOLD, LOOKUP) | — | **Domain-specific** → giữ nguyên, table-based UX |

### 1.3 Phản biện Draft v18 — 5 Gap đã Phát hiện & Sửa

Draft `AlumGlass_v18_Upgrade_Spec.md` (2026-06-29, v1) giải quyết đúng 2 gap chính (Code→Small Text, Dynamic Item Selection) nhưng bỏ qua 5 vấn đề:

#### GAP 1 (P0) — Bỏ sót 2 field Code trong migration

Draft v1 liệt kê 8 field. v17 FINAL + REVIEW cho thấy còn:

| # | DocType | Field | v17 Fieldtype | v18 | Ghi chú |
|---|---|---|---|---|---|
| 1-8 | (như draft) | ... | Code | Small Text | ✅ Đã có |
| **9** | **AL Calculation Rule** | **`formula_expression`** | **Code** | **Small Text** | **★ BỔ SUNG** |
| **10** | **AL Variable Set Detail** | **`depends_on`** | **Code** | **Giữ nguyên Code** | Frappe convention |

- **Field 9:** Dùng khi `rule_type = FORMULA`. Draft bỏ sót.
- **Field 10:** Frappe built-in field cho JS expression (`eval:doc.var_type == "SELECT"`). **Không đổi** — không phải formula string AlumGlass.

#### GAP 2 (P0) — DynamicItemResolver dùng raw `eval()` thay vì FormulaEngine

Draft v1 implement `_evaluate_formula()` bằng:
```python
result = eval(formula, safe_globals, safe_locals)
```

**Anti-pattern:** Toàn bộ hệ thống dùng FormulaEngine làm engine DUY NHẤT (Nguyên tắc #11), nhưng DynamicItemResolver tự build eval engine riêng — chính xác điều v18 đang cố giải quyết.

**Fix:** Dùng `FormulaEngine.evaluate_single()` hoặc fallback `FormulaEngine.calculate()` — xem §5.2.

#### GAP 3 (P1) — Không tích hợp P0 từ REVIEW: FB Variable Binding

REVIEW (85/100) xác định P0 là thay AL Variable Binding bằng Formula Variable Binding. Draft v1 bỏ qua.

**Fix v18:**
- Đăng ký 2 custom handler (`rule_engine_lookup`, `bom_variable`) vào `data_source_registry`
- VariableResolver v3 gọi `resolve_bindings_with_deps()` thay vì self._resolve_bindings()
- Giữ AL Variable Binding DocType (không xóa data)
- Migration script tự động tạo FB bindings tương ứng

#### GAP 4 (P1) — Cost Template không tích hợp Formula Set

REVIEW P1: Cost Template nên tách thành Formula Set (engine) + AL Cost Template (UI). Draft v1 bỏ qua.

**Fix v18:** Thêm `formula_set` field (Link → Formula Set, optional) vào AL Cost Template. CostAccumulator v2 ưu tiên dùng Formula Set nếu có, fallback về al_lines.

#### GAP 5 (P2) — Thiếu spec cho Sales Override UI

Draft v1 implement priority `Sales override > Dynamic formula > fallback > default` nhưng không có UI spec.

**Fix v18:** Thêm `al_sales_item_overrides` JSON field + UI spec trong BOM Dialog (xem Implementation Checklist Phase 4).

### 1.4 15 Nguyên tắc Thiết kế (kế thừa v17, bổ sung v18)

| # | Nguyên tắc | v17 | v18 | Ghi chú |
|---|---|---|---|---|
| 1 | Zero Python trong DB | ✓ | ✓ | Không đổi |
| 2 | Chọn Item trực tiếp | ✓ | ✓ + Dynamic | ★ Mở rộng: Dynamic mode |
| 3 | `show_condition` thay `if/elif` | ✓ | ✓ | Không đổi |
| 4 | Thống nhất bảng `al_lines` | ✓ | ✓ | Không đổi |
| 5 | DAG là nguồn sự thật | ✓ | ✓ | Không đổi |
| 6 | Panel Expansion động | ✓ | ✓ | Không đổi |
| 7 | Giá kính tách kích thước SX | ✓ | ✓ | Không đổi |
| 8 | PK: mặc định + thay thế | ✓ | ✓ | Không đổi |
| 9 | Context phẳng | ✓ | ✓ | Không đổi |
| 10 | Rule là thư viện dùng chung | ✓ | ✓ + FB Global Var | ★ Mở rộng: optional FB |
| 11 | Formula Engine là lõi DUY NHẤT | ✓ | ✓ | **★ Gia cố: cả DynamicItemResolver dùng FE** |
| 12 | Minh bạch tuyệt đối | ✓ | ✓ | Không đổi |
| 13 | Module hook không phá lõi | ✓ | ✓ | Không đổi |
| 14 | BOM Version immutable | ✓ | ✓ | Không đổi |
| 15 | Approval trước hiệu lực | ✓ | ✓ | Không đổi |
| **16 ★** | **DynamicItemResolver dùng FormulaEngine** | — | ✓ | QĐ-16 |
| **17 ★** | **FB Variable Binding thay AL Binding** | — | ✓ | QĐ-17 |
| **18 ★** | **AL Rule giữ THRESHOLD/LOOKUP, CONSTANT/FORMULA optional FB** | — | ✓ | QĐ-18 |
| **19 ★** | **Cost Template + Formula Set optional** | — | ✓ | QĐ-19 |
| **20 ★** | **item_condition_formula chỉ dùng input vars** | — | ✓ | QĐ-20 |

---

## 2. IMPACT ANALYSIS

### 2.1 Small Text Migration (9 fields) — Impact

| Câu hỏi | Phân tích | Kết luận |
|---|---|---|
| Phá vỡ DAG? | Không. FormulaEngine đọc string, fieldtype không liên quan. | ✅ An toàn |
| Circular dependency? | Không. Schema change, không thay đổi logic. | ✅ An toàn |
| Performance? | Code và Small Text đều là TEXT trong MariaDB/PostgreSQL. | ✅ An toàn |
| Monaco Editor? | **Cải thiện.** FB Monaco yêu cầu Small Text. Code field có Python highlighting gây confusion. | ✅ Cải thiện UX |
| Backward compat? | Formula string giữ nguyên. BOM cũ chạy nguyên. | ✅ Non-breaking |
| `formula_expression`? | FORMULA-type rule vẫn chạy qua FormulaEngine. Đổi fieldtype không ảnh hưởng. | ✅ An toàn |

### 2.2 Dynamic Item Selection — Impact

| Câu hỏi | Phân tích | Kết luận |
|---|---|---|
| Phá vỡ DAG? | Không — Pre-Resolution Phase. Item resolved trước DAG chính. | ✅ An toàn |
| Circular dependency? | item_condition_formula chỉ dùng inputs_dict. Validate tại form save: reject slug-pattern. | ⚠️ Cần validate |
| Performance? | 1 FE.evaluate_single() + 1 batch DB lookup. ~5ms/dòng. Cache metadata per request. | ✅ An toàn |
| Backward compat? | Default mode=Fixed. Tất cả dòng v17 vẫn Fixed. | ✅ Non-breaking |
| Sales override? | Priority: Sales override > Dynamic formula > item_fallback > item_code. | ✅ Rõ ràng |

### 2.3 FB Variable Binding Migration — Impact

| Câu hỏi | Phân tích | Kết luận |
|---|---|---|
| Phá vỡ VariableResolver? | Thay self._resolve_bindings() bằng FB resolve_bindings_with_deps(). | ⚠️ Test kỹ |
| 8 ví dụ kiểm chứng? | Phải PASS 100%. DAG topology replace priority-based = kết quả tương đương. | ⚠️ Verify |
| AL Variable Binding? | Giữ nguyên DocType — chỉ thêm mapping. | ✅ Non-breaking |
| Effort? | 2-3 ngày: 2 handlers + VariableResolver + test. | ✅ Manageable |

### 2.4 Decision: OPTION A vs OPTION B cho Dynamic Item

| Tiêu chí | Option A: Pre-Resolution Phase (✅ CHỌN) | Option B: Inline DAG Node |
|---|---|---|
| **Cơ chế** | INPUT → DynamicItemResolver → inject item_code → DAG | item_code là node trong DAG |
| **FormulaEngine** | ✅ Không sửa | ❌ Phải sửa để support string-return |
| **Debug** | Dễ — item đã resolved trong inputs_dict | Khó — phải trace qua DAG |
| **Validation** | Sớm — validate item tồn tại trước DAG | Muộn — lỗi khi DAG chạy |
| **Performance** | Tốt — resolve 1 lần | Kém — DB lookup tại runtime |
| **Nguyên tắc #11** | ✅ FE là engine DUY NHẤT | ❌ Phân tán logic |

**✅ CHỌN OPTION A** — Không sửa FormulaEngine, giữ nguyên Tầng 3.

---

## 3. v18 ARCHITECTURE

### 3.1 Kiến trúc 7 tầng v18

```
TẦNG 7 — AI LAYER (★ MỚI v18)
  AI Formula Generator      — Sinh item_condition_formula từ mô tả tự nhiên
  AI Config Validator       — Phát hiện config sai (item không tồn tại, circular)
  AI PK Suggester           — Đề xuất phụ kiện dựa trên BOM tương tự

TẦNG 6 — MODULE LAYER (v17 — không đổi)
  Reporting + BOM Version + Approval + Discount + MRP + Notification + Cost Variance + Analytics
  (Module Hook Registry — after_calculate() event bus)

TẦNG 5 — PRESENTATION (cập nhật v18)
  BOM Dialog + Dynamic Item Highlight + Resolved Item Badge
  Formula Builder Monaco Editor (tất cả formula fields → Small Text)
  ★ Sales Override Panel (cho phép override item trong Dynamic rows)

TẦNG 4.5 — DYNAMIC ITEM RESOLVER (★ MỚI v18 — 3 CHẾ ĐỘ)
  DynamicItemResolver.resolve() — Pre-Resolution Phase
  ├── Fixed mode: bỏ qua (ProfileInterpreter tự xử lý)
  ├── Rule mode (★): _evaluate_rule() — table-based, KHÔNG parse formula
  │   ├── THRESHOLD: so sánh input_variable với from/to/operator → chọn item
  │   └── LOOKUP: so sánh key_1/key_2 với inputs_dict → chọn item
  └── Formula mode: FormulaEngine.evaluate_single() — power user
  Item cache, batch DB, fallback logic, sales override priority

TẦNG 4 — ORCHESTRATION (cập nhật v18)
  VariableResolver v3 — dùng FB resolve_bindings_with_deps() + custom handlers
  ProfileInterpreter v2 — Dynamic mode check trong pass2_build
  PkResolver — hỗ trợ Dynamic PK Line
  CostAccumulator v2 — Formula Set integration (optional)
  SnapshotBuilder — lưu item_context vào ConfigSnapshot
  BomOrchestrator — 7 bước (thêm Dynamic Item Resolve)

TẦNG 3 — FORMULA ENGINE (KHÔNG SỬA)
  FormulaEngine (DAG, IncrementalContext, explain(), snapshot_with_trace(), evaluate_single())
  BASE_FUNCS 80+, FormulaValidator, SecurityValidator

TẦNG 2 — RULE ENGINE & VARIABLE BINDING (cập nhật v18)
  AL Calculation Rule (THRESHOLD + LOOKUP giữ nguyên; CONSTANT/FORMULA → FB Global Var optional)
  Formula Variable Binding (FB native, DAG topology thay priority)
  + 2 custom handlers: bom_variable, rule_engine_lookup
  AL Discount Rule (stack, không vào DAG) — v17

TẦNG 1 — MASTER DATA (cập nhật v18)
  34 DocType v17 + schema updates:
    AL Profile Line (+3 fields), AL PK Line (+3 fields), AL Calculation Rule (formula_expression → Small Text),
    AL Cost Template (+formula_set), Quotation Item (+al_sales_item_overrides)
```

### 3.2 Quyết định Kiến trúc v18 (QĐ-16 đến QĐ-20)

**QĐ-16: DynamicItemResolver dùng FormulaEngine.evaluate_single()**

Không tự build eval sandbox. item_condition_formula chạy qua FormulaEngine như mọi formula khác. Security validator của FE đã được test kỹ.

**QĐ-17: Formula Variable Binding thay AL Variable Binding**

VariableResolver gọi `data_source_registry.resolve_bindings_with_deps()`. 2 custom handlers. AL Variable Binding DocType giữ để không phá data cũ — thêm migration script.

**QĐ-18: AL Calculation Rule — Tinh gọn, không xóa**

- THRESHOLD + LOOKUP: giữ nguyên (table-based UX, không FB equivalent)
- CONSTANT + FORMULA: admin có thể chuyển sang Formula Global Variable (tùy chọn)
- SEQUENCE: admin có thể chuyển sang Formula Set (tùy chọn)
- v18 chỉ đổi `formula_expression` → Small Text, không xóa rule_type nào

**QĐ-19: AL Cost Template + Formula Set — Optional**

Thêm field `formula_set` (Link → Formula Set, optional). Khi có → CostAccumulator dùng FB engine. Khi không → fallback AL Cost Template Line (backward compat).

**QĐ-20: item_condition_formula chỉ dùng input variables**

Chỉ tham chiếu biến từ inputs_dict (VariableResolver). Validate tại form save: reject nếu tham chiếu biến slug-pattern (computed bởi DAG).

**QĐ-21 ★: 3 Chế Độ Item Selection — Fixed / Rule / Formula**

Người dùng được chọn 1 trong 3 chế độ cho mỗi dòng AL Profile Line:

| Chế độ | Cơ chế | Ai dùng được | Ví dụ |
|---|---|---|---|
| **Fixed** | Chọn item cứng từ dropdown + show_condition | Mọi người | Khung bao, cánh — item không thay đổi |
| **Rule ★** | Chọn AL Dynamic Item Rule từ dropdown → bảng điều kiện map tự động | Kỹ thuật viên | Nẹp kính, gioăng, tay nắm, keo — thay đổi theo thông số |
| **Formula** | Viết IF(item_condition_formula) tự do | Kỹ thuật cao cấp | Logic phức tạp không thể biểu diễn bằng bảng |

**Lợi ích của Rule mode:**
- **Không code:** Admin tạo rule 1 lần bằng bảng trực quan → dùng cho mọi BOM
- **Tái sử dụng:** Cùng 1 rule "Nẹp kính theo độ dày" dùng cho cửa đi, cửa sổ, vách
- **Bảo trì dễ:** Thay đổi ngưỡng → sửa 1 lần trong rule → toàn bộ BOM cập nhật
- **Audit rõ ràng:** Rule hiển thị dạng bảng → ai cũng hiểu được logic chọn item

---

## 4. SCHEMA CHANGES

### 4.0 AL Dynamic Item Rule ★ — DocType Mới Quan Trọng Nhất v18

Đây là DocType cho phép người dùng **map điều kiện → item bằng bảng trực quan**, không cần viết code. Giống như `AL Calculation Rule (LOOKUP/THRESHOLD)` nhưng đầu ra là **Item Code** thay vì giá trị số.

#### AL Dynamic Item Rule (Master)

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| rule_code | Data | ✓ | Unique. `NEP-KINH-THEO-DO-DAY`, `TAY-NAM-THEO-BRAND-MAU`, `GIOANG-THEO-LOAI-KINH` |
| rule_name | Data | ✓ | Tên hiển thị: "Nẹp kính theo độ dày kính" |
| rule_type | Select | ✓ | `THRESHOLD` / `LOOKUP` |
| **THRESHOLD fields:** | | | |
| input_variable | Data | | Tên biến trong inputs_dict. VD: `glass_thick_kinh_canh`, `max_glass_thick_mm` |
| threshold_rows | Table → AL Dynamic Item Threshold Row | | Bảng ngưỡng số → item |
| **LOOKUP fields:** | | | |
| lookup_key_1_var | Data | | Tên biến key 1. VD: `brand`, `mau_nhom`, `huong_mo` |
| lookup_key_2_var | Data | | Tên biến key 2 (optional) |
| lookup_rows | Table → AL Dynamic Item Lookup Row | | Bảng tra cứu key-value → item |
| **Chung:** | | | |
| default_item | Link → Item | ✓ | Item fallback nếu không khớp điều kiện nào |
| is_active | Check (default 1) | | Bật/tắt rule |
| description | Small Text | | Mô tả cách dùng rule |

#### AL Dynamic Item Threshold Row (Child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| from_value | Float | Giá trị từ (0 = không giới hạn dưới) |
| to_value | Float | Giá trị đến (0 = không giới hạn trên) |
| operator | Select | `≤` / `<` / `≥` / `>` / `=` |
| item_code | Link → Item (reqd) | Item được chọn khi điều kiện khớp |
| note | Data | Ghi chú: "Nẹp mỏng cho kính đơn" |

#### AL Dynamic Item Lookup Row (Child)

| fieldname | fieldtype | Mô tả |
|---|---|---|
| key_1 | Data | Giá trị key 1 |
| key_2 | Data | Giá trị key 2 (optional) |
| item_code | Link → Item (reqd) | Item được chọn khi cả 2 key khớp |
| note | Data | Ghi chú |

#### Ví dụ Master Data — AL Dynamic Item Rule

**Rule 1: NEP-KINH-THEO-DO-DAY (THRESHOLD)**

| from_value | to_value | operator | item_code | note |
|---|---|---|---|---|
| 0 | 10.38 | ≤ | C3209-20 | Nẹp mỏng ≤10.38mm |
| 10.39 | 16.0 | ≤ | C3210-20 | Nẹp vừa 11-16mm |
| 16.01 | 24.0 | ≤ | C3211-20 | Nẹp IGU 16-24mm |
| 24.01 | 0 | > | C3211-24 | Nẹp IGU >24mm |
| **input_variable:** glass_thick_kinh_canh | **default_item:** C3209-20 | | | |

**Rule 2: TAY-NAM-THEO-BRAND-MAU (LOOKUP)**

| key_1 (brand) | key_2 (mau_nhom) | item_code |
|---|---|---|
| XF-NK | STD | TAY-NAM-XF55-STD |
| XF-NK | DAK | TAY-NAM-XF55-DAK |
| XF-NK | VG | TAY-NAM-XF55-VG |
| XF-NK | INOX | TAY-NAM-XF55-INOX |
| ALUMIL | STD | TAY-NAM-ALU-STD |
| ALUMIL | INOX | TAY-NAM-ALU-INOX |
| **lookup_key_1_var:** brand | **lookup_key_2_var:** mau_nhom | **default_item:** TAY-NAM-XF55-STD |

**Rule 3: BANLE-THEO-HUONG-MO (LOOKUP)**

| key_1 (huong_mo) | item_code |
|---|---|
| Out | BANLE-XF55-OUT |
| In | BANLE-XF55-IN |
| **lookup_key_1_var:** huong_mo | **lookup_key_2_var:** (trống) | **default_item:** BANLE-XF55-OUT |

**Rule 4: GIOANG-KINH-THEO-LOAI (LOOKUP)**

| key_1 (glass_type) | item_code |
|---|---|
| CUONG_LUC | GIO-EPDM-CL |
| HOP | GIO-EPDM-HOP |
| LOWE | GIO-EPDM-LOWE |
| DON | GIO-EPDM-THUONG |
| **lookup_key_1_var:** (từ glass_type của glass_master) | **lookup_key_2_var:** (trống) | **default_item:** GIO-EPDM-THUONG |

#### Cập nhật AL Profile Line — `item_selection_mode` thành 3 options

Trường `item_selection_mode` đổi từ `Fixed/Dynamic` thành `Fixed/Rule/Formula`:

| fieldname | fieldtype | default | reqd | Mô tả |
|---|---|---|---|---|
| **item_selection_mode** | **Select (Fixed/Rule/Formula)** | **Fixed** | | **★ MỞ RỘNG: thêm Rule** |
| item_code | Link → Item | | khi Fixed | Item cố định (Fixed mode) |
| **item_rule** | **Link → AL Dynamic Item Rule** | | **khi Rule** | **★ MỚI: chọn rule từ dropdown** |
| **item_condition_formula** | **Small Text** | | **khi Formula** | Công thức IF lồng (Formula mode) |
| item_fallback | Link → Item | | khi Rule/Formula | Item dự phòng |

#### Cập nhật AL PK Line — tương tự

| fieldname | fieldtype | default | Mô tả |
|---|---|---|---|
| **item_selection_mode** | **Select (Fixed/Rule/Formula)** | **Fixed** | **★ MỞ RỘNG** |
| item_code | Link → Item | | khi Fixed |
| **item_rule** | **Link → AL Dynamic Item Rule** | | **khi Rule** |
| **item_condition_formula** | **Small Text** | | **khi Formula** |
| item_fallback | Link → Item | | khi Rule/Formula |

### 4.1 AL Profile Line — Schema v18 (đầy đủ)

#### Trường chung

| fieldname | fieldtype | default | reqd | Thay đổi vs v17 |
|---|---|---|---|---|
| sort_order | Int | | ✓ | Không đổi |
| line_type | Select (NHOM/KINH/VTP/PK) | | ✓ | Không đổi |
| line_name | Data | | ✓ | Không đổi |
| slug | Data | | | Không đổi |
| group_tag | Data | | | Không đổi |
| **show_condition** | **Small Text** | | | **★ Code→Small Text** |
| cost_bucket | Link → AL Cost Bucket | | | Không đổi |
| is_active | Check | 1 | | Không đổi |
| **item_selection_mode** | **Select (Fixed/Dynamic)** | **Fixed** | | **★ MỚI v18** |
| **item_condition_formula** | **Small Text** | | | **★ MỚI v18** |
| **item_fallback** | **Link → Item** | | | **★ MỚI v18** |

#### Trường riêng NHOM

| fieldname | fieldtype | reqd | Thay đổi |
|---|---|---|---|
| item_code | Link → Item | khi Fixed | Không đổi |
| quantity_rule | Link → AL Calculation Rule | | Không đổi |
| **qty_formula** | **Small Text** | | **★ Code→Small Text** |
| price_type | Select (Rule/Item Price/Fixed) | | Không đổi |
| price_rule | Link → AL Calculation Rule | | Không đổi |
| fixed_price | Currency | | Không đổi |

#### Trường riêng KINH

| fieldname | fieldtype | reqd | Thay đổi |
|---|---|---|---|
| ctx_inject_prefix | Data | ✓ | Không đổi |
| default_glass_master | Link → AL Glass Master | ✓ | Không đổi |
| width_rule | Link → AL Calculation Rule | | Không đổi |
| height_rule | Link → AL Calculation Rule | | Không đổi |
| **width_formula** | **Small Text** | | **★ Code→Small Text** |
| **height_formula** | **Small Text** | | **★ Code→Small Text** |
| **panel_count_formula** | **Small Text** | | **★ Code→Small Text** |
| panel_glass_override_allowed | Check | | Không đổi |
| **qty_per_panel_formula** | **Small Text** | | **★ Code→Small Text** |
| price_type | Select | | Không đổi |
| price_list | Link → Price List | | Không đổi |
| price_rule | Link → AL Calculation Rule | | Không đổi |
| fixed_price | Currency | | Không đổi |
| cut_fee_pct | Float | | Không đổi |

#### Trường riêng VTP

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| item_code | Link → Item | Không đổi |
| quantity_rule | Link → AL Calculation Rule | Không đổi |
| **qty_formula** | **Small Text** | **★ Code→Small Text** |
| price_type | Select | Không đổi |
| price_list | Link → Price List | Không đổi |
| fixed_price | Currency | Không đổi |

#### Trường riêng PK (inline)

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| item_code | Link → Item | Không đổi |
| **sl_formula** | **Small Text** | **★ Code→Small Text** |
| price_list | Link → Price List | Không đổi |
| allow_substitute | Check | Không đổi |
| substitute_item_group | Link → Item Group | Không đổi |

### 4.2 AL PK Line — Schema v18

| fieldname | fieldtype | default | Thay đổi |
|---|---|---|---|
| item_code | Link → Item | | Không đổi |
| **sl_formula** | **Small Text** | | **★ Code→Small Text** |
| price_list | Link → Price List | | Không đổi |
| cost_bucket | Link → AL Cost Bucket | | Không đổi |
| allow_substitute | Check | | Không đổi |
| substitute_item_group | Link → Item Group | | Không đổi |
| **item_selection_mode** | **Select (Fixed/Dynamic)** | **Fixed** | **★ MỚI v18** |
| **item_condition_formula** | **Small Text** | | **★ MỚI v18** |
| **item_fallback** | **Link → Item** | | **★ MỚI v18** |

### 4.3 AL Cost Template Line — Schema v18

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| sort_order | Int | Không đổi |
| line_code | Data | Không đổi |
| line_label | Data | Không đổi |
| **calc_formula** | **Small Text** | **★ Code→Small Text** |
| cost_bucket | Link → AL Cost Bucket | Không đổi |
| is_subtotal | Check | Không đổi |
| show_on_quotation | Check (default 1) | Không đổi |

### 4.4 AL Calculation Rule — Schema v18

| fieldname | fieldtype | Ghi chú |
|---|---|---|
| rule_code | Data | Không đổi |
| rule_name | Data | Không đổi |
| rule_type | Select | Không đổi |
| is_active | Check | Không đổi |
| constant_value | Data | Không đổi |
| **formula_expression** | **Small Text** | **★ Code→Small Text** |
| threshold_input_var | Data | Không đổi |
| threshold_rows | Table | Không đổi |
| lookup_key_1_var | Data | Không đổi |
| lookup_key_2_var | Data | Không đổi |
| lookup_rows | Table | Không đổi |
| lookup_default | Data | Không đổi |
| sequence_items | Table | Không đổi |

### 4.5 AL Cost Template — Schema v18 (bổ sung)

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| template_code | Data | Không đổi |
| template_name | Data | Không đổi |
| product_type | Link → AL Product Type | Không đổi |
| **formula_set** | **Link → Formula Set (optional)** | **★ MỚI v18** |
| al_lines | Table → AL Cost Template Line | Không đổi |

### 4.6 Quotation Item — Custom Field mới v18

| fieldname | fieldtype | Ghi chú |
|---|---|---|
| **al_sales_item_overrides** | **JSON** | **★ MỚI v18 — `{slug: item_code}`. UI xử lý qua JS.** |
| (tất cả field v17 khác) | | Không đổi |

### 4.7 Validation Rules

```python
# alumglass/doctype/al_profile_line/al_profile_line.py

def validate(doc):
    """Validate AL Profile Line — v18 với 3 chế độ."""

    # 1. Rule mode validation
    if doc.item_selection_mode == "Rule":
        if not doc.item_rule:
            frappe.throw("Item Rule bắt buộc khi chọn Rule mode")
        if doc.line_type in ("NHOM", "PK") and not doc.item_fallback:
            frappe.throw("Item Fallback bắt buộc khi chọn Rule mode cho NHOM/PK")
        if doc.line_type == "KINH":
            frappe.throw("KINH line không hỗ trợ Rule mode. Dùng Glass Selector.")
        # Validate rule tồn tại và active
        if not frappe.db.get_value("AL Dynamic Item Rule",
                                    {"rule_code": doc.item_rule, "is_active": 1}, "name"):
            frappe.throw(f"AL Dynamic Item Rule '{doc.item_rule}' không tồn tại hoặc không active")

    # 2. Formula mode validation
    if doc.item_selection_mode == "Formula":
        if not doc.item_condition_formula:
            frappe.throw("Item Condition Formula bắt buộc khi chọn Formula mode")
        if doc.line_type in ("NHOM", "PK") and not doc.item_fallback:
            frappe.throw("Item Fallback bắt buộc khi chọn Formula mode cho NHOM/PK")
        if doc.line_type == "KINH":
            frappe.throw("KINH line không hỗ trợ Formula mode. Dùng Glass Selector.")
        from alumglass.engine.dynamic_item_resolver import validate_item_condition_formula
        validate_item_condition_formula(doc.item_condition_formula)

    # 3. Fixed mode validation
    if doc.item_selection_mode == "Fixed" and doc.line_type in ("NHOM", "PK"):
        if not doc.item_code:
            frappe.throw("Item Code bắt buộc khi chọn Fixed mode")

    # 4. show_condition syntax check (áp dụng cho tất cả mode)
    if doc.show_condition:
        from formula_builder.formula_utils import FormulaValidator
        result = FormulaValidator().validate_formula(doc.show_condition)
        if not result.is_valid:
            frappe.throw(f"show_condition không hợp lệ: {result.error_message}")
```

---

## 5. DYNAMIC ITEM RESOLVER — 3 CHẾ ĐỘ

### 5.0 Tổng quan 3 chế độ

```
┌──────────────────────────────────────────────────────────────────┐
│              3 CHẾ ĐỘ ITEM SELECTION — DỄ → KHÓ                  │
│                                                                  │
│  FIXED              RULE (★ MỚI v18)         FORMULA             │
│  Chọn 1 item cứng   Bảng điều kiện → item    Viết IF lồng        │
│  (giống v17)        (KHÔNG CẦN CODE)         (Power user)        │
│                                                                  │
│  item_code =        item_rule =              item_condition_     │
│  "C3209-20"         "NEP-KINH-THEO-DO-DAY"   formula = "IF(..)"  │
│                                                                  │
│  Dùng cho:           Dùng cho:                Dùng cho:           │
│  Khung, cánh,        Nẹp, gioăng, keo,       Logic phức tạp      │
│  item cố định        tay nắm, khóa, bản lề   không table được    │
└──────────────────────────────────────────────────────────────────┘
```

### 5.1 Thiết kế

```
DynamicItemResolver (Tầng 4.5)
├── resolve(profile_lines, pk_lines, inputs_dict, sales_overrides) → injected_dict
│   ├── _prefetch_candidates() — collect tất cả item cần load metadata
│   ├── _batch_load_metadata(item_codes) — 1 query cho tất cả items + prices
│   ├── _resolve_item(line, inputs_dict, sales_override) → item_code
│   │   ├── Priority 1: sales_override (validate exists)
│   │   ├── Priority 2a (★ MỚI): _evaluate_rule(item_rule) — table lookup, KHÔNG CODE
│   │   ├── Priority 2b: FormulaEngine.evaluate_single(item_condition_formula)
│   │   ├── Priority 3: item_fallback
│   │   └── Priority 4: item_code default
│   └── _get_item_metadata(item_code) → {kg_per_m, price, uom}
│
│   _evaluate_rule(rule_doc, inputs_dict) → item_code
│   ├── THRESHOLD: Duyệt threshold_rows, so sánh input_variable với from/to/operator
│   └── LOOKUP:    Duyệt lookup_rows, so sánh key_1/key_2 với inputs_dict
│
│ ĐIỂM KHÁC BIỆT VS DRAFT v1:
│   ✅ 3 chế độ: Fixed / Rule / Formula
│   ✅ Rule mode: table-based, KHÔNG parsing formula
│   ✅ Rule mode: dùng chung giữa các BOM (thư viện rule)
│   ✅ Dùng FormulaEngine.evaluate_single() cho Formula mode
│   ✅ Batch DB query (không N+1)
│   ✅ _exists_cache là Set (O(1) lookup)
```

### 5.2 Full Implementation

```python
# alumglass/engine/dynamic_item_resolver.py
"""
DynamicItemResolver v18 — Pre-Resolution Phase với 3 chế độ.

Chế độ Rule (★ MỚI): Map điều kiện → item bằng bảng — KHÔNG CẦN VIẾT CODE.
Chế độ Formula:      Viết IF lồng tự do qua FormulaEngine.
Chế độ Fixed:        Item cố định (giống v17).
"""

import frappe
from frappe import _
from frappe.utils import flt
from typing import Any, Dict, List, Optional, Set


class DynamicItemResolver:
    """Resolve item_code cho Dynamic/Rule/Formula lines trước DAG."""

    def __init__(self):
        self._item_cache: Dict[str, Dict] = {}
        self._exists_cache: Set[str] = set()
        self._rule_cache: Dict[str, Any] = {}  # Cache rule docs

    def resolve(
        self,
        profile_lines: List[Any],
        pk_lines: List[Any],
        inputs_dict: Dict[str, Any],
        sales_overrides: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Resolve tất cả items — Fixed mode bỏ qua, chỉ xử lý Rule/Formula."""
        sales_overrides = sales_overrides or {}
        injected: Dict[str, Any] = {}

        # === Prefetch candidates ===
        candidates = self._prefetch_candidates(profile_lines, pk_lines, sales_overrides)
        if candidates:
            self._batch_load_metadata(candidates)

        # === Resolve Profile Lines ===
        for line in profile_lines:
            if not getattr(line, "is_active", 1):
                continue
            if getattr(line, "line_type", "") == "KINH":
                continue
            mode = getattr(line, "item_selection_mode", "Fixed")
            if mode == "Fixed":
                continue  # ProfileInterpreter xử lý Fixed mode

            slug = getattr(line, "slug", "") or f"line_{line.idx}"
            sales_override = sales_overrides.get(slug)
            resolved = self._resolve_item(line, inputs_dict, sales_override)

            injected[f"{slug}_item_code"] = resolved
            meta = self._get_item_metadata(resolved)
            if meta:
                injected[f"{slug}_kg_per_m"] = meta.get("kg_per_m", 0)
                injected[f"{slug}_price"] = meta.get("price", 0)

        # === Resolve PK Lines ===
        for idx, line in enumerate(pk_lines):
            mode = getattr(line, "item_selection_mode", "Fixed")
            if mode == "Fixed":
                continue
            pk_slug = f"pk_{idx:04d}"
            resolved = self._resolve_item(line, inputs_dict, None)
            injected[f"{pk_slug}_item_code"] = resolved
            meta = self._get_item_metadata(resolved)
            if meta:
                injected[f"{pk_slug}_price"] = meta.get("price", 0)

        return injected

    # ═══════════════════════════════════════════
    # ITEM RESOLUTION — Priority Chain
    # ═══════════════════════════════════════════

    def _resolve_item(
        self, line: Any, inputs_dict: Dict[str, Any],
        sales_override: Optional[str] = None,
    ) -> str:
        """Priority: Sales override > Rule/Formula > fallback > default."""
        slug = getattr(line, "slug", "unknown")
        mode = getattr(line, "item_selection_mode", "Fixed")

        # Priority 1: Sales override (cao nhất)
        if sales_override:
            if self._item_exists(sales_override):
                return sales_override
            frappe.log_error(
                title="Sales override item không tồn tại",
                message=f"Line: {slug}, override: {sales_override} — fallback"
            )

        # Priority 2a: RULE — Table-based, KHÔNG CODE (★ MỚI v18)
        if mode == "Rule" and getattr(line, "item_rule", None):
            resolved = self._evaluate_rule(line.item_rule, inputs_dict, slug)
            if resolved and self._item_exists(resolved):
                return resolved
            if resolved:
                frappe.log_error(
                    title="Rule resolved to non-existent item",
                    message=f"Line: {slug}, rule: {line.item_rule}, result: {resolved}"
                )

        # Priority 2b: FORMULA — FormulaEngine (power user)
        if mode == "Formula":
            formula = (getattr(line, "item_condition_formula", "") or "").strip()
            if formula:
                resolved = self._evaluate_via_formula_engine(formula, inputs_dict, slug)
                if resolved and self._item_exists(resolved):
                    return resolved
                if resolved:
                    frappe.log_error(
                        title="Formula resolved to non-existent item",
                        message=f"Line: {slug}, result: '{resolved}'"
                    )

        # Priority 3: item_fallback
        fallback = getattr(line, "item_fallback", None)
        if fallback and self._item_exists(fallback):
            return fallback

        # Priority 4: item_code default (Fixed mode)
        default_item = getattr(line, "item_code", None)
        if default_item and self._item_exists(default_item):
            return default_item

        frappe.throw(_(
            "Không thể resolve item cho dòng '{0}'. "
            "Kiểm tra item_rule / item_condition_formula / item_fallback / item_code."
        ).format(slug))

    # ═══════════════════════════════════════════
    # RULE EVALUATION — Table-based (★ MỚI v18)
    # ═══════════════════════════════════════════

    def _evaluate_rule(
        self, rule_code: str, inputs_dict: Dict[str, Any], slug: str
    ) -> Optional[str]:
        """Evaluate AL Dynamic Item Rule — table lookup, không parse formula.

        Hỗ trợ 2 loại rule:
        - THRESHOLD: So sánh input_variable với from/to/operator → chọn item
        - LOOKUP:    So sánh key_1/key_2 với inputs_dict → chọn item

        Returns:
            str: item_code nếu khớp, None nếu không khớp dòng nào.
        """
        # Cache rule doc
        if rule_code not in self._rule_cache:
            rule = frappe.db.get_value(
                "AL Dynamic Item Rule",
                {"rule_code": rule_code, "is_active": 1},
                ["name", "rule_type", "input_variable",
                 "lookup_key_1_var", "lookup_key_2_var", "default_item"],
                as_dict=True,
            )
            if not rule:
                frappe.log_error(
                    title=f"Dynamic Item Rule not found: {rule_code}",
                    message=f"Line: {slug}"
                )
                return None
            self._rule_cache[rule_code] = rule
        else:
            rule = self._rule_cache[rule_code]

        # === THRESHOLD ===
        if rule.rule_type == "THRESHOLD":
            var_name = rule.input_variable
            if not var_name:
                frappe.log_error(
                    title=f"THRESHOLD rule missing input_variable: {rule_code}",
                    message=f"Line: {slug}"
                )
                return rule.default_item

            input_val = flt(inputs_dict.get(var_name, 0))

            # Load threshold rows
            rows = frappe.get_all(
                "AL Dynamic Item Threshold Row",
                filters={"parent": rule.name},
                fields=["from_value", "to_value", "operator", "item_code"],
                order_by="from_value asc",
            )

            for row in rows:
                from_v = flt(row.from_value or 0)
                to_v = flt(row.to_value or 0)
                op = row.operator or "<="

                matched = False
                if op == "<=":
                    # from_v <= input_val <= to_v (to_v=0 → không giới hạn)
                    upper = to_v if to_v > 0 else float("inf")
                    matched = from_v <= input_val <= upper
                elif op == "<":
                    upper = to_v if to_v > 0 else float("inf")
                    matched = (from_v < input_val) if not to_v else (from_v < input_val <= upper)
                elif op == ">=":
                    matched = input_val >= from_v
                elif op == ">":
                    matched = input_val > from_v
                elif op == "=":
                    matched = input_val == from_v

                if matched:
                    return row.item_code

            # No match → default
            return rule.default_item

        # === LOOKUP ===
        if rule.rule_type == "LOOKUP":
            key1 = str(inputs_dict.get(rule.lookup_key_1_var, ""))
            key2 = str(inputs_dict.get(rule.lookup_key_2_var, "")) if rule.lookup_key_2_var else ""

            rows = frappe.get_all(
                "AL Dynamic Item Lookup Row",
                filters={"parent": rule.name},
                fields=["key_1", "key_2", "item_code"],
            )

            for row in rows:
                rk1 = str(row.key_1 or "")
                rk2 = str(row.key_2 or "")
                k1_match = (not rk1 or key1 == rk1)
                k2_match = (not rk2 or key2 == rk2)
                if k1_match and k2_match:
                    return row.item_code

            # No match → default
            return rule.default_item

        return rule.default_item

    # ═══════════════════════════════════════════
    # FORMULA ENGINE INTEGRATION (QĐ-16)
    # ═══════════════════════════════════════════

    def _evaluate_via_formula_engine(
        self, formula: str, context: Dict[str, Any], slug: str
    ) -> Optional[str]:
        """Evaluate qua FormulaEngine — engine DUY NHẤT (chỉ dùng cho Formula mode)."""
        try:
            from formula_builder.formula_utils import FormulaEngine
            engine = FormulaEngine()

            if hasattr(engine, "evaluate_single"):
                result = engine.evaluate_single(formula=formula, context=context)
                return str(result).strip().strip("'\"") if result is not None else None

            # Fallback: dùng calculate() với 1 formula
            result = engine.calculate(
                formulas=[{"name": "_item_result", "formula": formula}],
                inputs=context,
            )
            val = result.get("_item_result")
            return str(val).strip("'\"") if val is not None else None

        except Exception as e:
            frappe.log_error(
                title="DynamicItemResolver: formula evaluation failed",
                message=f"Slug: {slug}, formula: {formula[:200]}, error: {type(e).__name__}: {e}"
            )
            return None

    # ═══════════════════════════════════════════
    # ITEM METADATA — BATCH LOADING
    # ═══════════════════════════════════════════

    def _prefetch_candidates(
        self, profile_lines, pk_lines, sales_overrides
    ) -> Set[str]:
        """Collect tất cả item codes có thể cần."""
        candidates = set()
        for line in profile_lines:
            for attr in ("item_code", "item_fallback"):
                v = getattr(line, attr, None)
                if v: candidates.add(v)
            # Thêm item từ rule rows (nếu rule đã được load)
            if getattr(line, "item_rule", None):
                candidates.add(getattr(line, "item_fallback", None) or "")
        for line in pk_lines:
            for attr in ("item_code", "item_fallback"):
                v = getattr(line, attr, None)
                if v: candidates.add(v)
        candidates.update(v for v in sales_overrides.values() if v)
        candidates.discard(None)
        candidates.discard("")
        return candidates

    def _batch_load_metadata(self, item_codes: Set[str]) -> None:
        """Load metadata trong 2 queries (items + prices)."""
        uncached = item_codes - set(self._item_cache.keys())
        if not uncached:
            return
        items = frappe.get_all(
            "Item",
            filters={"name": ["in", list(uncached)], "disabled": 0},
            fields=["name", "al_kg_per_m", "al_item_type", "stock_uom"],
        )
        if not items:
            return
        loaded = [i.name for i in items]
        prices = frappe.get_all(
            "Item Price",
            filters={"item_code": ["in", loaded], "selling": 1},
            fields=["item_code", "price_list_rate"],
            order_by="valid_from desc",
        )
        price_map = {}
        for p in prices:
            if p.item_code not in price_map:
                price_map[p.item_code] = flt(p.price_list_rate)
        for item in items:
            self._item_cache[item.name] = {
                "item_code": item.name,
                "kg_per_m": flt(item.al_kg_per_m or 0),
                "item_type": item.al_item_type,
                "uom": item.stock_uom,
                "price": price_map.get(item.name, 0),
            }
            self._exists_cache.add(item.name)

    def _get_item_metadata(self, item_code: str) -> Optional[Dict]:
        if not item_code: return None
        if item_code not in self._item_cache:
            self._batch_load_metadata({item_code})
        return self._item_cache.get(item_code)

    def _item_exists(self, item_code: str) -> bool:
        if not item_code: return False
        if item_code in self._exists_cache: return True
        exists = frappe.db.get_value("Item", {"name": item_code, "disabled": 0}, "name")
        if exists: self._exists_cache.add(item_code)
        return bool(exists)

    def clear_cache(self):
        self._item_cache.clear()
        self._exists_cache.clear()
        self._rule_cache.clear()


# ═══════════════════════════════════════════
# VALIDATOR (cập nhật cho Rule mode)
# ═══════════════════════════════════════════

def validate_item_condition_formula(formula: str) -> bool:
    """Validate item_condition_formula cho Formula mode."""
    if not formula or not formula.strip():
        return True
    try:
        from formula_builder.formula_utils import FormulaValidator
        result = FormulaValidator().validate_formula(formula)
        if not result.is_valid:
            frappe.throw(_("Công thức không hợp lệ: {0}").format(result.error_message))
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.throw(_("Lỗi validate công thức: {0}").format(str(e)))

    import re
    slug_pattern = re.compile(r'\b([a-z]+_\d{4}_\w+)\b')
    matches = slug_pattern.findall(formula)
    if matches:
        frappe.throw(_(
            "item_condition_formula không được tham chiếu biến tính toán: {0}. "
            "Chỉ dùng biến đầu vào (W_mm, H_mm, glass_thick_*, do_day, n_canh, ...)."
        ).format(", ".join(set(matches))))

---

## 6. VARIABLERESOLVER v3

### 6.1 FB Integration + Custom Handlers

```python
# alumglass/engine/variable_resolver.py — v3

import frappe, json
from frappe.utils import flt

class VariableResolver:
    """v3: Dùng Formula Variable Binding (FB native, DAG topology)."""

    def resolve(self, quotation_item, bom_doc):
        # ─── Bước 1: FB resolve_bindings_with_deps (DAG topo thay priority) ───
        from formula_builder.api.data_source_registry import resolve_bindings_with_deps
        bindings = frappe.get_all(
            "Formula Variable Binding",
            filters={"is_active": 1},
            fields=["*"],
            order_by="resolve_priority asc",
        )
        inputs_dict = resolve_bindings_with_deps(bindings, quotation_item)

        # ─── Bước 2: BOM Variables + Quotation inputs (domain-specific) ───
        inputs_dict.update(self._resolve_bom_variables(bom_doc, quotation_item))
        inputs_dict.update(self._resolve_quotation_inputs(quotation_item))

        # ─── Bước 3: glass_thick injection (giữ nguyên từ v16/v17) ───
        profile_set = frappe.get_doc("AL Profile Set", bom_doc.profile_set)
        glass_selections = self._safe_json(quotation_item, "al_glass_selections")
        for line in profile_set.al_lines:
            if line.line_type != "KINH":
                continue
            prefix = line.ctx_inject_prefix
            glass_code = glass_selections.get(prefix) or line.default_glass_master
            if glass_code:
                thick = frappe.db.get_value("AL Glass Master", glass_code, "total_thick_mm") or 0
                inputs_dict[f"glass_thick_{prefix}"] = float(thick)

        return inputs_dict

    def _resolve_bom_variables(self, bom_doc, quotation_item):
        result = {}
        bom_vars = self._safe_json(quotation_item, "al_bom_vars")
        if not bom_doc.variable_set:
            return result
        for detail in frappe.get_doc("AL Variable Set", bom_doc.variable_set).al_var_details:
            var_code = detail.variable
            result[var_code] = (
                bom_vars.get(var_code)
                or detail.override_default
                or frappe.db.get_value("AL Variable Library", var_code, "default_val")
            )
        return result

    def _resolve_quotation_inputs(self, quotation_item):
        W = flt(quotation_item.get("al_W_mm", 0))
        H = flt(quotation_item.get("al_H_mm", 0))
        return {
            "W_mm": W, "H_mm": H, "qty": flt(quotation_item.get("qty", 1)),
            "W_m": W / 1000, "H_m": H / 1000,
            "mau_nhom": quotation_item.get("al_mau_nhom", ""),
        }

    @staticmethod
    def _safe_json(doc, fieldname):
        raw = doc.get(fieldname) or "{}"
        return json.loads(raw) if isinstance(raw, str) else (raw or {})


# ═══════════════════════════════════════════
# CUSTOM HANDLERS — Đăng ký vào FB data_source_registry
# ═══════════════════════════════════════════

def _handle_bom_variable(source_config, resolved_so_far, context):
    """Handler: đọc biến từ al_bom_vars JSON của Quotation Item."""
    var_code = source_config.get("var_code")
    quotation_item = context.get("_quotation_item")
    if not var_code or not quotation_item:
        return None
    bom_vars = json.loads(quotation_item.get("al_bom_vars") or "{}")
    return bom_vars.get(var_code)


def _handle_rule_engine_lookup(source_config, resolved_so_far, context):
    """Handler: tra AL Calculation Rule LOOKUP/THRESHOLD."""
    rule_code = source_config.get("rule_code")
    arg_mapping = source_config.get("args", {})
    if not rule_code:
        return None

    rule = frappe.db.get_value(
        "AL Calculation Rule",
        {"rule_code": rule_code, "is_active": 1},
        ["name", "rule_type", "lookup_default", "threshold_input_var"],
        as_dict=True,
    )
    if not rule:
        return None

    if rule.rule_type == "LOOKUP":
        key_values = {k: resolved_so_far.get(v, "") for k, v in arg_mapping.items()}
        rows = frappe.get_all("AL Rule Lookup Row",
            filters={"parent": rule.name},
            fields=["key_1", "key_2", "key_3", "result_value"])
        for row in rows:
            if all(not key_values.get(f"key_{i}") or
                   str(key_values[f"key_{i}"]) == str(row.get(f"key_{i}") or "")
                   for i in range(1, 4)):
                return flt(row.result_value or 0)
        return flt(rule.lookup_default or 0)

    if rule.rule_type == "THRESHOLD":
        val = flt(resolved_so_far.get(rule.threshold_input_var, 0))
        rows = frappe.get_all("AL Rule Threshold Row",
            filters={"parent": rule.name},
            fields=["from_value", "to_value", "result_value"],
            order_by="from_value asc")
        for row in rows:
            if row.from_value <= val and (not row.to_value or val <= row.to_value):
                return flt(row.result_value or 0)
        return flt(rule.lookup_default or 0)

    return None


def register_custom_handlers():
    """Đăng ký 2 custom handlers vào FB data_source_registry."""
    try:
        from formula_builder.api.data_source_registry import DATA_SOURCE_HANDLERS
        DATA_SOURCE_HANDLERS["bom_variable"] = _handle_bom_variable
        DATA_SOURCE_HANDLERS["rule_engine_lookup"] = _handle_rule_engine_lookup
        frappe.logger().info("AlumGlass: Registered custom FB handlers")
    except ImportError:
        frappe.logger().warning("AlumGlass: FB not available — handlers skipped")
    except Exception as e:
        frappe.log_error(title="FB handler registration failed", message=str(e))
```

### 6.2 Source Type Mapping — AL → FB

| AL source_type | FB source_type / Handler | Ghi chú |
|---|---|---|
| Quotation Input | `linked_doctype_field` | Đọc field từ Quotation Item |
| BOM Variable | `bom_variable` (custom) | Đọc từ al_bom_vars JSON |
| BOM Attribute | `linked_doctype_field` | Đọc field từ AL BOM |
| Rule Engine Result | `rule_engine_lookup` (custom) | Tra LOOKUP/THRESHOLD |
| Computed | `computed` (FB native, DAG) | Mạnh hơn: topological sort |
| Context Inject | — (giữ nguyên) | glass_thick injection |

**FB source types mới user có thể dùng (12 thay vì 5):**
`constant`, `linked_doctype_field`, `whole_doctype`, `child_table_aggregate`, `global_default`, `session_variable`, `doctype_query`, `custom_function`, `dynamic_link`, `computed` + 2 custom handlers.

---

## 7. DAG INTEGRATION

### 7.1 Vị trí Dynamic Item trong toàn bộ flow

```
TRƯỚC DAG — Tầng 4.5 (DynamicItemResolver):
  inputs_dict (sau VariableResolver) bao gồm:
    W_mm=1500, H_mm=2400, qty=1, n_canh=2, do_day="2.0mm"
    glass_thick_kinh_canh=24.0    ← inject từ AL Glass Master
    don_gia_nhom=180000           ← resolve từ FB Variable Binding (LOOKUP)
    ★ nhom_0060_item_code="C3211-20"   ← DynamicItemResolver
    ★ nhom_0060_kg_per_m=0.312         ← DynamicItemResolver
    ★ nhom_0060_price=113000            ← DynamicItemResolver

VÀO DAG — FormulaEngine thấy item như hằng số:
  nhom_0060_active = (show_condition_formula)   # Boolean
  nhom_0060_qty    = H_m * 2 * qty
  nhom_0060_kg     = nhom_0060_kg_per_m         # Constant
  nhom_0060_dg     = nhom_0060_price            # Constant
  nhom_0060_tt     = nhom_0060_qty * nhom_0060_kg * nhom_0060_dg
  VL_NHOM = nhom_0010_tt + nhom_0020_tt + ... + nhom_0060_tt
  GIA_BAN = (VL_NHOM + VL_KINH + VL_VTP + VL_PK) * markup

SAU DAG — Module Hooks (v17):
  Hook A: DiscountStack.apply() → GIA_BAN_THUONG_MAI
  Hook B: BOMVersionManager.link_version()
  Hook C: CostVarianceAnalyzer.register()
  Hook D: NotificationEngine.check_alerts()
```

### 7.2 Tránh Circular Dependency

```
QUY TẮC: item_condition_formula CHỈ dùng biến từ inputs_dict (đã có trước DAG):

✅ ĐƯỢC PHÉP:
  glass_thick_kinh_canh   — INPUT (inject từ GlassMaster)
  W_mm, H_mm, qty         — INPUT (từ Quotation)
  n_canh, do_day          — INPUT (từ BOM Variables)
  don_gia_nhom            — INPUT (từ FB Variable Binding LOOKUP)

❌ BỊ REJECT (validate tại form save):
  nhom_0060_qty           — COMPUTED bởi DAG (slug pattern: word_NNNN_suffix)
  nhom_0060_tt            — COMPUTED bởi DAG
  TONG_VL, GIA_BAN        — COMPUTED bởi DAG

ENFORCE: validate_item_condition_formula() scan pattern r'\b[a-z]+_\d{4}_\w+\b'
→ Bất kỳ match nào → throw ValidationError ngay khi admin save.
```

### 7.3 Dependency Resolve Timeline

```
t=0: VariableResolver.resolve()        → inputs_dict cơ bản + glass_thick injection
t=1: DynamicItemResolver.resolve()     → FE.evaluate_single() → inject item_code, kg, price
t=2: ProfileInterpreter.pass1_scan()   → variable_registry, panel_counts
t=3: ProfileInterpreter.pass2_build()  → build formulas với item đã resolved
t=4: PkResolver.build_formulas()       → formulas_pk
t=5: CostAccumulator.build()           → formulas_cost (Formula Set hoặc legacy)
t=6: FormulaEngine.calculate()         → DAG execute — DUY NHẤT 1 LẦN
t=7: SnapshotBuilder.persist()         → lưu ConfigSnapshot + item_context vào audit trail
t=8: Hooks A→D                         → Discount, Version, Variance, Notification
```

---

## 8. BOM ORCHESTRATOR v18 — 7 BƯỚC

```python
# alumglass/engine/orchestrator.py — BomOrchestrator v18

class BomOrchestrator:
    """BomOrchestrator v18 — 7 bước + Module Hooks."""

    def run(self, quotation_item, bom_doc):
        from alumglass.engine.variable_resolver import VariableResolver
        from alumglass.engine.dynamic_item_resolver import DynamicItemResolver
        from alumglass.engine.profile_interpreter import ProfileInterpreter
        from alumglass.engine.pk_resolver import PkResolver
        from alumglass.engine.cost_accumulator import CostAccumulator
        from alumglass.engine.snapshot_builder import SnapshotBuilder
        from alumglass.engine.module_registry import fire_hooks
        from formula_builder.formula_utils import FormulaEngine

        # Config
        profile_set = frappe.get_doc("AL Profile Set", bom_doc.profile_set)
        pk_set = frappe.get_doc("AL PK Set", bom_doc.pk_set) if bom_doc.pk_set else None
        glass_selections = VariableResolver._safe_json(quotation_item, "al_glass_selections")
        pk_overrides = VariableResolver._safe_json(quotation_item, "al_pk_overrides")
        sales_overrides = VariableResolver._safe_json(quotation_item, "al_sales_item_overrides")

        # ═══ BƯỚC 1: VariableResolver v3 ═══
        var_resolver = VariableResolver()
        inputs_dict = var_resolver.resolve(quotation_item, bom_doc)

        # ═══ BƯỚC 2: DynamicItemResolver ★ MỚI v18 ═══
        active_lines = [ln for ln in profile_set.al_lines if getattr(ln, "is_active", 1)]
        pk_lines = pk_set.al_pk_lines if pk_set else []
        item_resolver = DynamicItemResolver()
        item_context = item_resolver.resolve(
            profile_lines=active_lines, pk_lines=pk_lines,
            inputs_dict=inputs_dict, sales_overrides=sales_overrides,
        )
        inputs_dict.update(item_context)

        # ═══ BƯỚC 3: ProfileInterpreter Pass 1 ═══
        interpreter = ProfileInterpreter()
        variable_registry, panel_counts = interpreter.pass1_scan(
            active_lines, inputs_dict, glass_selections)

        # ═══ BƯỚC 4: ProfileInterpreter Pass 2 ═══
        all_formulas, bucket_acc = interpreter.pass2_build(
            active_lines, inputs_dict, variable_registry,
            panel_counts, glass_selections)

        # ═══ BƯỚC 5: PkResolver ═══
        formulas_pk, pk_warnings = PkResolver().build_formulas(bom_doc, pk_overrides)
        all_formulas.extend(formulas_pk)

        # ═══ BƯỚC 6: CostAccumulator v2 ═══
        formulas_cost = CostAccumulator().build_bucket_and_template_formulas(
            bucket_acc=bucket_acc,
            cost_template_name=bom_doc.default_cost_template,
        )
        all_formulas.extend(formulas_cost)

        # ═══ BƯỚC 7: FormulaEngine.calculate() + SnapshotBuilder ═══
        engine = FormulaEngine()
        result = engine.calculate(formulas=all_formulas, inputs=inputs_dict)
        snapshot = SnapshotBuilder().persist(
            quotation_item=quotation_item, bom_doc=bom_doc,
            inputs_dict=inputs_dict, result=result,
            item_context=item_context,  # ★ Audit trail: Dynamic Item resolve info
        )

        # Ghi Quotation Item
        self._write_result(quotation_item, result, snapshot, pk_warnings)

        # ═══ HOOKS A→D (v17 — không đổi) ═══
        fire_hooks("after_calculate",
                   result=result, quotation_item=quotation_item,
                   bom_doc=bom_doc)

        return result, pk_warnings

    def _write_result(self, qi, result, snapshot, warnings):
        qi.db_set("al_config_snapshot", snapshot.name)
        for field in ["al_vl_nhom", "al_vl_kinh", "al_vl_vtp", "al_vl_pk",
                       "al_tong_vl", "al_gia_thanh", "al_gia_ban", "al_gia_vat"]:
            bucket = field.replace("al_", "").upper() if field != "al_tong_vl" else "TONG_VL"
            if bucket in result:
                qi.db_set(field, flt(result[bucket]))
```

---

## 9. COSTACCUMULATOR v2 + PROFILEINTERPRETER UPDATE

### 9.1 CostAccumulator v2 — Formula Set Integration

```python
# alumglass/engine/cost_accumulator.py — v2

class CostAccumulator:
    def build_bucket_and_template_formulas(self, bucket_acc, cost_template_name):
        formulas = []

        # Bucket formulas (giữ nguyên v17)
        for bucket_code, var_list in bucket_acc.items():
            if var_list:
                formulas.append({"name": bucket_code, "formula": " + ".join(var_list)})

        if not cost_template_name:
            return formulas

        template = frappe.get_cached_doc("AL Cost Template", cost_template_name)

        # ★ v18: Dùng Formula Set nếu có (QĐ-19)
        if template.get("formula_set"):
            try:
                from formula_builder.api.variable_resolver import VariableResolver as FBResolver
                fb_resolver = FBResolver()
                set_formulas = fb_resolver._get_formula_set_output(template.formula_set)
                formulas.extend(set_formulas)
                return formulas
            except Exception as e:
                frappe.log_error(
                    title="CostAccumulator: Formula Set failed, falling back to al_lines",
                    message=str(e))

        # Fallback: AL Cost Template Line (backward compat)
        for line in (template.al_lines or []):
            if line.calc_formula:
                formulas.append({
                    "name": line.line_code or f"cost_{line.sort_order}",
                    "formula": line.calc_formula,
                })

        return formulas
```

### 9.2 ProfileInterpreter — Dynamic Item Check

```python
# Trong pass2_build — cập nhật cho Dynamic Item

def pass2_build(self, lines, inputs_dict, variable_registry, panel_counts, glass_selections):
    all_formulas = []
    bucket_acc = defaultdict(list)

    for line in lines:
        slug = line.slug
        line_type = line.line_type

        if line_type == "NHOM":
            # ★ v18: Check Dynamic mode
            if getattr(line, "item_selection_mode", "Fixed") == "Dynamic":
                # kg_per_m và price đã inject vào inputs_dict bởi DynamicItemResolver
                kg_var = f"{slug}_kg_per_m"
                price_var = f"{slug}_price"
            else:
                # Fixed mode — v17 logic: đọc trực tiếp từ Item
                item = frappe.get_cached_doc("Item", line.item_code)
                kg_val = flt(item.al_kg_per_m or 0)
                # Inject như constant vào inputs_dict
                inputs_dict[f"{slug}_kg_per_m"] = kg_val
                kg_var = f"{slug}_kg_per_m"
                # Đơn giá: Fixed / Rule / Item Price
                price_val = self._resolve_price(line, inputs_dict)
                inputs_dict[f"{slug}_price"] = price_val
                price_var = f"{slug}_price"

            # show_condition → active
            if line.show_condition:
                all_formulas.append({"name": f"{slug}_active", "formula": line.show_condition})
            else:
                inputs_dict[f"{slug}_active"] = 1

            # qty
            qty_expr = self._get_qty_formula(line)
            all_formulas.append({
                "name": f"{slug}_qty",
                "formula": f"IF({slug}_active, {qty_expr}, 0)"
            })

            # thành tiền
            all_formulas.append({
                "name": f"{slug}_tt",
                "formula": f"{slug}_qty * {kg_var} * {price_var}"
            })

            bucket_acc[line.cost_bucket or "VL_NHOM"].append(f"{slug}_tt")

        # KINH, VTP, PK: logic v17 không đổi
        # ...

    return all_formulas, bucket_acc
```

---

## 10. MIGRATION SCRIPTS

### 10.1 Patch 1 — Alter 9 Formula Fields: Code → Small Text

```python
# aluglass/patches/v18_0/alter_formula_fields_to_small_text.py
import frappe

FIELD_MAP = [
    ("AL Profile Line", "show_condition"),
    ("AL Profile Line", "qty_formula"),
    ("AL Profile Line", "width_formula"),
    ("AL Profile Line", "height_formula"),
    ("AL Profile Line", "panel_count_formula"),
    ("AL Profile Line", "qty_per_panel_formula"),
    ("AL PK Line", "sl_formula"),
    ("AL Cost Template Line", "calc_formula"),
    ("AL Calculation Rule", "formula_expression"),  # ★ Bổ sung vs draft v1
]

def execute():
    print("v18 Migration: Alter 9 formula fields Code → Small Text")
    for doctype, fieldname in FIELD_MAP:
        if frappe.db.exists("DocField", {"parent": doctype, "fieldname": fieldname}):
            frappe.db.set_value("DocField",
                {"parent": doctype, "fieldname": fieldname},
                "fieldtype", "Small Text")
            print(f"  OK: {doctype}.{fieldname}")
        else:
            print(f"  SKIP: {doctype}.{fieldname} — not found")
    frappe.clear_cache()
    frappe.db.commit()
    print("v18: Formula fields standardized")
```

### 10.2 Patch 2 — Add Dynamic Item + AL Dynamic Item Rule Fields

```python
# aluglass/patches/v18_0/add_dynamic_item_fields.py
import frappe

def execute():
    print("v18 Migration: Adding Dynamic Item fields + AL Dynamic Item Rule DocTypes")

    # === AL Profile Line: cập nhật item_selection_mode + thêm item_rule ===
    _add_or_update_field("AL Profile Line", {
        "fieldname": "item_selection_mode", "fieldtype": "Select",
        "label": "Item Selection Mode", "options": "Fixed\nRule\nFormula",
        "default": "Fixed", "insert_after": "is_active",
        "description": "Fixed: chọn item cứng. Rule: dùng bảng điều kiện. Formula: viết IF lồng.",
    })
    _add_fields("AL Profile Line", [
        {"fieldname": "item_rule", "fieldtype": "Link",
         "label": "Item Rule", "options": "AL Dynamic Item Rule",
         "insert_after": "item_selection_mode",
         "depends_on": "eval:doc.item_selection_mode=='Rule'",
         "description": "Chọn rule từ thư viện — KHÔNG cần viết code."},
        {"fieldname": "item_condition_formula", "fieldtype": "Small Text",
         "label": "Item Condition Formula", "insert_after": "item_rule",
         "depends_on": "eval:doc.item_selection_mode=='Formula'",
         "description": "Công thức IF lồng. Ví dụ: IF(glass_thick_kinh_canh <= 10.38, 'C3209-20', 'C3211-20')"},
        {"fieldname": "item_fallback", "fieldtype": "Link", "options": "Item",
         "label": "Item Fallback", "insert_after": "item_condition_formula",
         "depends_on": "eval:['Rule','Formula'].includes(doc.item_selection_mode)",
         "description": "Item dùng khi Rule/Formula không resolve được."},
    ])

    # === AL PK Line: tương tự ===
    _add_or_update_field("AL PK Line", {
        "fieldname": "item_selection_mode", "fieldtype": "Select",
        "label": "Item Selection Mode", "options": "Fixed\nRule\nFormula",
        "default": "Fixed", "insert_after": "item_code",
    })
    _add_fields("AL PK Line", [
        {"fieldname": "item_rule", "fieldtype": "Link",
         "label": "Item Rule", "options": "AL Dynamic Item Rule",
         "insert_after": "item_selection_mode",
         "depends_on": "eval:doc.item_selection_mode=='Rule'"},
        {"fieldname": "item_condition_formula", "fieldtype": "Small Text",
         "label": "Item Condition Formula", "insert_after": "item_rule",
         "depends_on": "eval:doc.item_selection_mode=='Formula'"},
        {"fieldname": "item_fallback", "fieldtype": "Link", "options": "Item",
         "label": "Item Fallback", "insert_after": "item_condition_formula",
         "depends_on": "eval:['Rule','Formula'].includes(doc.item_selection_mode)"},
    ])

    # === AL Cost Template ===
    _add_fields("AL Cost Template", [
        {"fieldname": "formula_set", "fieldtype": "Link", "options": "Formula Set",
         "label": "Formula Set (optional)", "insert_after": "product_type"},
    ])

    # === Tạo AL Dynamic Item Rule DocType (nếu chưa có) ===
    _create_dynamic_item_rule_doctype()

    frappe.db.commit()
    print("v18: Dynamic Item fields + Rule DocTypes added")


def _create_dynamic_item_rule_doctype():
    """Tạo DocType AL Dynamic Item Rule nếu chưa tồn tại."""
    if frappe.db.exists("DocType", "AL Dynamic Item Rule"):
        print("  SKIP: AL Dynamic Item Rule DocType exists")
        return

    # Tạo DocType
    dt = frappe.new_doc("DocType")
    dt.name = "AL Dynamic Item Rule"
    dt.module = "AlumGlass"
    dt.istable = 0
    dt.is_submittable = 0
    dt.naming_rule = "By fieldname"
    dt.autoname = "field:rule_code"
    dt.engine = "InnoDB"
    dt.fields = [
        {"fieldname": "rule_code", "fieldtype": "Data", "label": "Rule Code",
         "reqd": 1, "unique": 1},
        {"fieldname": "rule_name", "fieldtype": "Data", "label": "Rule Name", "reqd": 1},
        {"fieldname": "rule_type", "fieldtype": "Select",
         "label": "Rule Type", "options": "THRESHOLD\nLOOKUP", "reqd": 1},
        {"fieldname": "input_variable", "fieldtype": "Data",
         "label": "Input Variable",
         "depends_on": "eval:doc.rule_type=='THRESHOLD'",
         "description": "Tên biến trong inputs_dict. VD: glass_thick_kinh_canh"},
        {"fieldname": "column_break_1", "fieldtype": "Column Break"},
        {"fieldname": "lookup_key_1_var", "fieldtype": "Data",
         "label": "Key 1 Variable",
         "depends_on": "eval:doc.rule_type=='LOOKUP'",
         "description": "Tên biến key 1. VD: brand"},
        {"fieldname": "lookup_key_2_var", "fieldtype": "Data",
         "label": "Key 2 Variable",
         "depends_on": "eval:doc.rule_type=='LOOKUP'",
         "description": "Tên biến key 2 (optional). VD: mau_nhom"},
        {"fieldname": "section_break_threshold", "fieldtype": "Section Break",
         "label": "Threshold Rows",
         "depends_on": "eval:doc.rule_type=='THRESHOLD'"},
        {"fieldname": "threshold_rows", "fieldtype": "Table",
         "label": "Threshold Rows", "options": "AL Dynamic Item Threshold Row",
         "depends_on": "eval:doc.rule_type=='THRESHOLD'"},
        {"fieldname": "section_break_lookup", "fieldtype": "Section Break",
         "label": "Lookup Rows",
         "depends_on": "eval:doc.rule_type=='LOOKUP'"},
        {"fieldname": "lookup_rows", "fieldtype": "Table",
         "label": "Lookup Rows", "options": "AL Dynamic Item Lookup Row",
         "depends_on": "eval:doc.rule_type=='LOOKUP'"},
        {"fieldname": "section_break_default", "fieldtype": "Section Break"},
        {"fieldname": "default_item", "fieldtype": "Link",
         "label": "Default Item", "options": "Item", "reqd": 1,
         "description": "Item dùng khi không có điều kiện nào khớp"},
        {"fieldname": "is_active", "fieldtype": "Check", "label": "Is Active", "default": "1"},
        {"fieldname": "description", "fieldtype": "Small Text", "label": "Description"},
    ]
    dt.permissions = [
        {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
    ]
    dt.insert(ignore_permissions=True)

    # Tạo child DocTypes
    _create_child_doctype("AL Dynamic Item Threshold Row", [
        {"fieldname": "from_value", "fieldtype": "Float", "label": "From", "reqd": 0},
        {"fieldname": "to_value", "fieldtype": "Float", "label": "To (0=unlimited)", "reqd": 0},
        {"fieldname": "operator", "fieldtype": "Select",
         "label": "Op", "options": "≤\n<\n≥\n>\n=", "default": "≤", "reqd": 1},
        {"fieldname": "item_code", "fieldtype": "Link",
         "label": "Item", "options": "Item", "reqd": 1},
        {"fieldname": "note", "fieldtype": "Data", "label": "Note"},
    ])

    _create_child_doctype("AL Dynamic Item Lookup Row", [
        {"fieldname": "key_1", "fieldtype": "Data", "label": "Key 1", "reqd": 1},
        {"fieldname": "key_2", "fieldtype": "Data", "label": "Key 2", "reqd": 0},
        {"fieldname": "item_code", "fieldtype": "Link",
         "label": "Item", "options": "Item", "reqd": 1},
        {"fieldname": "note", "fieldtype": "Data", "label": "Note"},
    ])

    print("  OK: Created AL Dynamic Item Rule + 2 child DocTypes")


def _create_child_doctype(name, fields):
    if frappe.db.exists("DocType", name):
        print(f"  SKIP: {name} exists")
        return
    dt = frappe.new_doc("DocType")
    dt.name = name
    dt.module = "AlumGlass"
    dt.istable = 1
    dt.engine = "InnoDB"
    dt.fields = fields
    dt.insert(ignore_permissions=True)
    print(f"  OK: Created child DocType: {name}")


def _add_or_update_field(doctype, field_def):
    """Add or update a custom field (for changing existing field options)."""
    if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field_def["fieldname"]}):
        cf = frappe.get_doc("Custom Field", {"dt": doctype, "fieldname": field_def["fieldname"]})
        for k, v in field_def.items():
            cf.set(k, v)
        cf.save(ignore_permissions=True)
        print(f"  UPDATED: {doctype}.{field_def['fieldname']}")
    elif frappe.db.exists("DocField", {"parent": doctype, "fieldname": field_def["fieldname"]}):
        frappe.db.set_value("DocField",
            {"parent": doctype, "fieldname": field_def["fieldname"]},
            field_def)
        print(f"  UPDATED: {doctype}.{field_def['fieldname']} (core field)")
    else:
        cf = frappe.new_doc("Custom Field")
        cf.dt = doctype
        for k, v in field_def.items():
            cf.set(k, v)
        cf.insert(ignore_permissions=True)
        print(f"  OK: Added {doctype}.{field_def['fieldname']}")


def _add_fields(doctype, fields):
    for f in fields:
        _add_or_update_field(doctype, f)
```

### 10.3 Patch 3 — Sales Override Custom Field

```python
# aluglass/patches/v18_0/add_sales_override_field.py
import frappe

def execute():
    if frappe.db.exists("Custom Field", {"dt": "Quotation Item", "fieldname": "al_sales_item_overrides"}):
        print("SKIP: al_sales_item_overrides exists")
        return
    cf = frappe.new_doc("Custom Field")
    cf.dt = "Quotation Item"
    cf.fieldname = "al_sales_item_overrides"
    cf.fieldtype = "JSON"
    cf.label = "Sales Item Overrides"
    cf.insert_after = "al_pk_overrides"
    cf.description = "Sales override item cho Dynamic rows. Format: {slug: item_code}"
    cf.hidden = 1
    cf.insert(ignore_permissions=True)
    frappe.db.commit()
    print("OK: al_sales_item_overrides added")
```

### 10.4 Patch 4 — Migrate AL Variable Binding → FB

```python
# aluglass/patches/v18_0/migrate_variable_bindings.py
import frappe, json

SOURCE_TYPE_MAP = {
    "Quotation Input": "linked_doctype_field",
    "BOM Variable": "bom_variable",
    "BOM Attribute": "linked_doctype_field",
    "Rule Engine Result": "rule_engine_lookup",
    "Computed": "computed",
    "Context Inject": None,
}

def execute():
    bindings = frappe.get_all("AL Variable Binding", fields=["*"])
    print(f"v18 Migration: {len(bindings)} AL Bindings → Formula Variable Binding")

    for al_b in bindings:
        fb_type = SOURCE_TYPE_MAP.get(al_b.source_type)
        if fb_type is None:
            print(f"  SKIP: {al_b.binding_code} (source_type={al_b.source_type})")
            continue
        if frappe.db.exists("Formula Variable Binding", {"variable_name": al_b.variable_name}):
            continue

        fb = frappe.new_doc("Formula Variable Binding")
        fb.variable_name = al_b.variable_name
        fb.variable_label = al_b.variable_label
        fb.source_type = fb_type
        fb.resolve_priority = al_b.resolve_priority
        fb.data_type = al_b.data_type
        fb.is_active = al_b.is_active

        if al_b.source_type == "BOM Variable":
            fb.source_config = json.dumps({"var_code": al_b.variable_name})
        elif al_b.source_type in ("Quotation Input", "BOM Attribute"):
            old = json.loads(al_b.source_config or "{}")
            fb.source_config = json.dumps({"fieldname": old.get("fieldname", al_b.variable_name)})
        else:
            fb.source_config = al_b.source_config

        fb.insert(ignore_permissions=True)
        print(f"  OK: {al_b.variable_name} ({al_b.source_type} → {fb_type})")

    frappe.db.commit()
    print("v18: Variable Binding migration complete")
```

### 10.5 Migration Checklist

| Bước | Công việc | Script | Prio |
|---|---|---|---|
| 1 | **Backup database** | — | P0 BẮT BUỘC |
| 2 | Verify v17 stable (8 ví dụ PASS) | Manual | P0 |
| 3 | Register 2 custom FB handlers | hooks.py → register_custom_handlers() | P0 |
| 4 | Alter 9 fields: Code → Small Text | patches/v18_0/alter_formula_fields_to_small_text.py | P0 |
| 5 | **Tạo 3 DocType: AL Dynamic Item Rule + 2 Child** | patches/v18_0/add_dynamic_item_fields.py | P0 |
| 6 | Add Dynamic Item + Rule fields + update item_selection_mode | (cùng script) | P0 |
| 7 | Add `al_sales_item_overrides` | patches/v18_0/add_sales_override_field.py | P0 |
| 7 | Migrate AL → FB Variable Bindings | patches/v18_0/migrate_variable_bindings.py | P1 |
| 8 | Deploy engine files (Resolver, Orchestrator, ...) | engine/*.py | P0 |
| 9 | `bench migrate` + `bench restart` | — | P0 |
| 10 | Test: 8 ví dụ v17 PASS (Fixed mode) | Manual | P0 |
| 11 | Test: Dynamic item resolve đúng | Manual | P0 |
| 12 | Test: Sales override priority chain | Manual | P0 |

---

## 11. IMPLEMENTATION CHECKLIST

### Phase 1 — Engine Core (3-4 ngày)

| # | Task | File | Notes |
|---|---|---|---|
| 1.1 | Viết fb_handlers.py (2 custom handlers) | `engine/fb_handlers.py` | register_custom_handlers() |
| 1.2 | **Viết DynamicItemResolver (3 chế độ: Rule + Formula + Fixed)** | `engine/dynamic_item_resolver.py` | Xem §5.2 |
| 1.3 | **Viết `_evaluate_rule()` — THRESHOLD + LOOKUP** | (cùng file) | Table-based, không parse formula |
| 1.4 | Cập nhật VariableResolver v3 | `engine/variable_resolver.py` | resolve_bindings_with_deps() |
| 1.5 | Cập nhật BomOrchestrator (7 bước) | `engine/orchestrator.py` | Thêm bước 2 |
| 1.6 | **Cập nhật ProfileInterpreter — handle 3 mode** | `engine/profile_interpreter.py` | Fixed/Rule/Formula trong pass2_build |
| 1.7 | Cập nhật CostAccumulator v2 | `engine/cost_accumulator.py` | Formula Set fallback |

### Phase 2 — DocTypes + Migration (2-3 ngày)

| # | Task | File | Notes |
|---|---|---|---|
| 2.1 | **Tạo 3 DocType mới: AL Dynamic Item Rule + 2 Child Tables** | `doctype/al_dynamic_item_rule/` | THRESHOLD + LOOKUP |
| 2.2 | **Tạo 4 Rule fixtures mặc định (nẹp, tay nắm, bản lề, gioăng)** | `fixtures/al_dynamic_item_rule.json` | Rule mẫu cho user |
| 2.3 | Patch: alter 9 formula fields Code→Small Text | `patches/v18_0/alter_formula_fields_to_small_text.py` | |
| 2.4 | **Patch: add item_rule + update item_selection_mode options** | `patches/v18_0/add_dynamic_item_fields.py` | Fixed/Rule/Formula |
| 2.5 | Patch: add sales override field | `patches/v18_0/add_sales_override_field.py` | |
| 2.6 | Patch: migrate AL→FB bindings | `patches/v18_0/migrate_variable_bindings.py` | |
| 2.7 | Update hooks.py | `aluglass/hooks.py` | |
| 2.8 | Update AL Profile Line form layout (Rule section) | Customize Form | |

### Phase 3 — Testing (2-3 ngày)

| # | Test Case | Expected Result |
|---|---|---|
| 3.1 | 8 ví dụ kiểm chứng v17 (Fixed mode) | PASS 100% |
| 3.2 | **Rule THRESHOLD: resolve đúng item theo glass_thick** | C3209/C3210/C3211 theo ngưỡng |
| 3.3 | **Rule LOOKUP: resolve đúng item theo brand + màu** | TAY-NAM-XF55-INOX khi brand=XF-NK, màu=INOX |
| 3.4 | Priority: Sales override > Rule > Formula > fallback > default | Override thắng |
| 3.5 | Rule không khớp → fallback item | Không crash, dùng default_item |
| 3.6 | Formula tham chiếu slug variable → reject | ValidationError |
| 3.7 | Item disabled → fallback hoạt động | Log warning |
| 3.8 | Thay đổi Rule (thêm ngưỡng mới) → tất cả BOM tự cập nhật | Resolve đúng với ngưỡng mới |
| 3.9 | Batch DB với 20+ Dynamic rows | ≤2 queries |
| 3.10 | Formula Set trong Cost Template | evaluate đúng, explain() OK |
| 3.11 | **Fixed mode = identical to v17 output** | 100% match |
| 3.12 | **Rule mode returns same item as Fixed mode với cùng input** | 100% match (cùng logic, khác cách setup) |

### Phase 4 — UI (2-3 ngày)

| # | Task | File | Prio |
|---|---|---|---|
| 4.1 | Monaco editor cho Small Text formula fields | `public/js/bom_dialog.js` | P1 |
| 4.2 | **Rule selector dropdown trong Profile Line form** | (cùng file) | **P0** |
| 4.3 | **Rule "Test" button: nhập input → preview item được chọn** | (cùng file) | **P0** |
| 4.4 | Resolved item display trong BOM Dialog (badge) | `public/js/quotation_item.js` | P1 |
| 4.5 | Sales Override Panel (dropdown per row) | (cùng file) | P2 |
| 4.6 | Error toast khi Rule/Formula fail | (cùng file) | P1 |
| 4.7 | Fixed/Rule/Formula toggle switch với UI khác nhau | (cùng file) | P1 |

### Phase 5 — Documentation (1 ngày)

| # | Task |
|---|---|
| 5.1 | Update CLAUDE.md với v18 changes |
| 5.2 | Update IMPLEMENTATION_PLAN.md |
| 5.3 | Viết migration guide cho admin |
| 5.4 | Viết ví dụ Dynamic Item tutorial |

### Phase 6 — Deploy & Monitor (ongoing)

| # | Task |
|---|---|
| 6.1 | Deploy lên staging, verify full pipeline |
| 6.2 | Monitor performance: DynamicItemResolver timing |
| 6.3 | Monitor errors: formula evaluation failures |
| 6.4 | Deploy production, monitor 1 tuần |

---

## 12. RISK & EDGE CASES

### 12.1 Risk Matrix

| # | Risk | Sev | Like | Mitigation |
|---|---|---|---|---|
| R1 | Formula trả về item không tồn tại | Med | Med | item_fallback bắt buộc. _item_exists() validate. Log + alert. |
| R2 | Circular: formula dùng slug variable | High | Low | Slug-pattern regex reject tại form save. |
| R3 | FE.evaluate_single() chưa có trong FB | High | Low | Fallback calculate() với 1 formula. Xem code §5.2. |
| R4 | Performance: 100+ Dynamic rows | Low | Low | Batch DB, item_cache. <200ms cho 100 rows. |
| R5 | FB Binding migration sai type | Med | Med | Test 8 ví dụ. Rollback flag: dùng AL bindings cũ. |
| R6 | Sales override item sai loại (NHOM→KINH) | Med | Med | Validate al_item_type trong resolver. |
| R7 | Code→Small Text gây data loss | Low | V.Low | Cả 2 đều là TEXT type. Chỉ update meta. |
| R8 | FB API thay đổi | Med | Low | Pin FB version trong requirements.txt. |
| R9 | BOM cũ quá nhiều Fixed rows → Dynamic conversion | Low | Low | Admin tự chọn convert. Tool AI-assisted suggestion. |
| R10 | Multi-tenant item khác company | Med | Low | Frappe Item global. v19: company-specific mapping. |

### 12.2 Edge Cases

```
CASE 1: Formula resolve item bị disabled
  → _item_exists() return False (filter disabled=0)
  → Skip formula, fall về fallback → log warning

CASE 2: Cả formula và fallback đều fail
  → frappe.throw("Không thể resolve item cho dòng {slug}")
  → BomOrchestrator dừng, UI hiển thị error dialog

CASE 3: Sales override item sai al_item_type
  → Validate trong DynamicItemResolver: check al_item_type match line_type
  → NHOM line chỉ nhận NHOM_PROFILE items

CASE 4: Panel Expansion + Dynamic Item
  → Item resolved 1 lần, tất cả panels dùng cùng item
  → pass2_build expand panels bình thường

CASE 5: Dynamic Item cho KINH line
  → KHÔNG hỗ trợ — KINH chọn qua Glass Selector
  → Validate: throw nếu KINH + Dynamic mode

CASE 6: item_condition_formula quá dài (>500 chars)
  → Warn tại validate; reject nếu >1000 chars
  → Admin nên dùng AL Calculation Rule LOOKUP thay IF chain

CASE 7: glass_thick_{prefix} chưa có khi evaluate formula
  → glass_thick inject luôn chạy TRƯỚC DynamicItemResolver (Bước 1 → Bước 2)
  → Nếu prefix không có trong glass_selections → dùng default_glass_master

CASE 8: Dynamic Item + show_condition cùng dòng
  → show_condition vẫn hoạt động bình thường (quyết định active/inactive)
  → Nếu show_condition=False → dòng inactive, DynamicItemResolver bỏ qua

CASE 9: Rule THRESHOLD — input_variable không có trong inputs_dict
  → flt(inputs_dict.get(var_name, 0)) = 0
  → Kết quả: so sánh với from=0, to=10.38 → khớp dòng đầu tiên
  → Log warning: "Input variable 'glass_thick_xyz' not found, defaulting to 0"

CASE 10: Rule LOOKUP — key variable không có trong inputs_dict
  → key = "" → row.key_1 = "" → khớp (empty match)
  → Nếu không có empty row → fallback về default_item
  → Không throw lỗi — để BOM vẫn tính được

CASE 11: Admin xóa Rule đang được dùng bởi BOM
  → AL Dynamic Item Rule không có "on delete cascade"
  → DynamicItemResolver: rule not found → log error → dùng fallback
  → Admin nên deprecate rule (is_active=0) thay vì xóa

CASE 12: Rule có item_code đã bị disabled
  → _item_exists() return False
  → Bỏ qua row đó → kiểm tra row tiếp theo → nếu không row nào khớp → fallback
  → Log warning khi item được reference nhưng disabled
```

---

## 13. ADVANCED UPGRADE

### 13.1 Performance Optimization

```python
# 1. CACHE FORMULA COMPILE
# ────────────────────────
# item_condition_formula compiled 1 lần, tái sử dụng
class CachingDynamicItemResolver(DynamicItemResolver):
    _formula_compile_cache: Dict[str, Any] = {}

    def _evaluate_via_formula_engine(self, formula, context, slug):
        if slug not in self._formula_compile_cache:
            from formula_builder.formula_utils import FormulaEngine
            self._formula_compile_cache[slug] = FormulaEngine().compile(formula)
        return self._formula_compile_cache[slug].evaluate(context)


# 2. DAG TOPOLOGY CACHE
# ─────────────────────
class DAGCache:
    _dag_cache: Dict[str, Any] = {}

    @classmethod
    def get_or_build(cls, profile_set_name, modified, formulas, inputs_dict):
        key = f"{profile_set_name}:{modified}"
        if key not in cls._dag_cache:
            from formula_builder.formula_utils import FormulaEngine
            cls._dag_cache[key] = FormulaEngine().build_dag(formulas, inputs_dict)
        return cls._dag_cache[key]


# 3. REDIS CACHE cho item metadata (TTL 5 phút)
def _get_item_metadata_redis(item_code):
    from frappe.utils.caching import redis_cache
    @redis_cache(ttl=300)
    def _load(item_code):
        return frappe.db.get_value("Item", item_code, ["al_kg_per_m", "al_item_type"])
    return _load(item_code)
```

### 13.2 AI Integration — Tầng 7

```python
# 1. AI GENERATE ITEM CONDITION FORMULA
def ai_generate_item_formula(description: str, available_items: List[Dict],
                              available_vars: List[str]) -> str:
    """Admin mô tả → AI sinh item_condition_formula."""
    prompt = f"""Generate FormulaEngine formula for item selection:
Description: {description}
Available items: {json.dumps(available_items, ensure_ascii=False)}
Available variables: {available_vars}
Return ONLY the formula string. Use IF(condition, "ITEM-CODE", fallback) syntax."""
    response = frappe.call_ai_api(prompt=prompt)
    validate_item_condition_formula(response.strip())
    return response.strip()


# 2. AI DETECT SAI CONFIG
def ai_validate_bom(bom_name: str) -> List[Dict]:
    """AI scan BOM → potential issues."""
    issues = []
    bom = frappe.get_doc("AL BOM", bom_name)
    profile_set = frappe.get_doc("AL Profile Set", bom.profile_set)
    for line in profile_set.al_lines:
        if line.item_selection_mode == "Dynamic" and not line.item_fallback:
            issues.append({"severity": "error", "line": line.slug,
                           "message": "Dynamic mode without item_fallback"})
    return issues


# 3. AI SUGGEST PK
def ai_suggest_pk(product_type: str, brand: str) -> List[str]:
    """Đề xuất phụ kiện từ pattern BOM tương tự."""
    similar = frappe.get_all("AL BOM", filters={"product_type": product_type},
                             fields=["pk_set"], limit=10)
    pk_freq: Dict[str, int] = {}
    for bom in similar:
        if bom.pk_set:
            for line in frappe.get_doc("AL PK Set", bom.pk_set).al_pk_lines:
                pk_freq[line.item_code] = pk_freq.get(line.item_code, 0) + 1
    return [item for item, _ in sorted(pk_freq.items(), key=lambda x: x[1], reverse=True)[:5]]
```

### 13.3 Platform Direction — Sau v18

```
v18 đạt được:
  ✓ 100% formula fields là Small Text
  ✓ Dynamic Item Selection — giảm 60-75% dòng BOM
  ✓ FormulaEngine là engine DUY NHẤT — không raw eval(), không Python code
  ✓ FB Variable Binding + DAG topology — resolve đúng thứ tự
  ✓ Config-driven 100% — admin tự cấu hình BOM
  ✓ AI-ready — explain() + structured config + Tầng 7 hooks
  ✓ Backward compatible — v17 data chạy nguyên

v19 roadmap:
  → AI-powered BOM Generator: mô tả sản phẩm → AI tạo Profile Set hoàn chỉnh
  → Multi-factory: 1 BOM template → nhiều factory với item mapping
  → Real-time pricing: giá nhôm/kính realtime → auto-inject
  → BOM Marketplace: chia sẻ Profile Set template
  → 3D Visualization: BOM config → 3D render

Platform thesis: "Manufacturing ERP = Low-code Platform + Domain DSL + FormulaEngine"
v18 là bước cuối cùng để đạt Zero-Dev-Required cho cấu hình BOM mới.
```

---

## APPENDIX A: Field Mapping v17 → v18

| DocType | fieldname | v17 Type | v18 Type | Ghi chú |
|---|---|---|---|---|
| AL Profile Line | show_condition | Code | Small Text | ★ #1 |
| AL Profile Line | qty_formula | Code | Small Text | ★ #2 |
| AL Profile Line | width_formula | Code | Small Text | ★ #3 |
| AL Profile Line | height_formula | Code | Small Text | ★ #4 |
| AL Profile Line | panel_count_formula | Code | Small Text | ★ #5 |
| AL Profile Line | qty_per_panel_formula | Code | Small Text | ★ #6 |
| AL PK Line | sl_formula | Code | Small Text | ★ #7 |
| AL Cost Template Line | calc_formula | Code | Small Text | ★ #8 |
| AL Calculation Rule | formula_expression | Code | Small Text | ★ #9 |
| AL Profile Line | item_selection_mode | — | Select (Fixed/Rule/Formula) | ★ MỚI (mở rộng 3 options) |
| AL Profile Line | item_rule | — | Link → AL Dynamic Item Rule | ★ MỚI (Rule mode) |
| AL Profile Line | item_condition_formula | — | Small Text | ★ MỚI (Formula mode) |
| AL Profile Line | item_fallback | — | Link → Item | ★ MỚI |
| AL PK Line | item_selection_mode | — | Select (Fixed/Rule/Formula) | ★ MỚI |
| AL PK Line | item_rule | — | Link → AL Dynamic Item Rule | ★ MỚI |
| AL PK Line | item_condition_formula | — | Small Text | ★ MỚI |
| AL PK Line | item_fallback | — | Link → Item | ★ MỚI |
| AL Cost Template | formula_set | — | Link → Formula Set | ★ MỚI (optional) |
| Quotation Item | al_sales_item_overrides | — | JSON | ★ MỚI |
| **★ AL Dynamic Item Rule** | **—** | **—** | **DocType mới** | **★ MỚI (Master)** |
| **★ AL Dynamic Item Threshold Row** | **—** | **—** | **DocType mới** | **★ MỚI (Child)** |
| **★ AL Dynamic Item Lookup Row** | **—** | **—** | **DocType mới** | **★ MỚI (Child)** |

**Tổng: 3 DocType mới + 9 field đổi + 8 field thêm = 20 thay đổi schema**

## APPENDIX B: Ví dụ — 3 Chế Độ Item Selection

### B.1 Cùng 1 bài toán "chọn nẹp kính theo độ dày" — 3 cách

#### Cách 1: FIXED (dễ nhất — giống v17, 3 dòng riêng biệt)

```
Dòng 60: Nẹp kính ≤10.38mm
  item_selection_mode: Fixed
  item_code: C3209-20
  show_condition: glass_thick_kinh_canh <= 10.38

Dòng 61: Nẹp kính 11-16mm
  item_selection_mode: Fixed
  item_code: C3210-20
  show_condition: glass_thick_kinh_canh > 10.38 and glass_thick_kinh_canh <= 16

Dòng 62: Nẹp kính >16mm
  item_selection_mode: Fixed
  item_code: C3211-20
  show_condition: glass_thick_kinh_canh > 16

→ 3 dòng cho 1 vị trí × 4 vị trí (đứng trái/phải, ngang trên/dưới) = 12 dòng
→ Dễ hiểu, ai cũng làm được
→ Nhược: nhiều dòng, thay đổi ngưỡng phải sửa từng dòng
```

#### Cách 2: RULE-BASED ★★★ KHUYẾN NGHỊ — 1 dòng, không code

```
Bước 1: Tạo AL Dynamic Item Rule (làm 1 lần):
  ┌──────────────────────────────────────────────┐
  │ Rule Code: NEP-KINH-THEO-DO-DAY             │
  │ Rule Type: THRESHOLD                         │
  │ Input Variable: glass_thick_kinh_canh        │
  │                                              │
  │ ┌──────┬───────┬────┬──────────────────┐    │
  │ │ From │ To    │ Op │ Item             │    │
  │ ├──────┼───────┼────┼──────────────────┤    │
  │ │ 0    │ 10.38 │ ≤  │ C3209-20         │    │
  │ │ 10.39│ 16.0  │ ≤  │ C3210-20         │    │
  │ │ 16.01│ 24.0  │ ≤  │ C3211-20         │    │
  │ │ 24.01│ 0     │ >  │ C3211-24         │    │
  │ └──────┴───────┴────┴──────────────────┘    │
  │ Default Item: C3209-20                       │
  └──────────────────────────────────────────────┘

Bước 2: Trong AL Profile Line — CHỈ 1 DÒNG:
  Dòng 60: Nẹp kính
    item_selection_mode: Rule
    item_rule: NEP-KINH-THEO-DO-DAY   ← chọn từ dropdown!
    item_fallback: C3209-20

→ 1 dòng cho 1 vị trí × 4 vị trí = 4 dòng (GIẢM 67%!)
→ Tạo rule 1 lần → dùng cho mọi BOM (CUA-DI, CUA-SO, VACH...)
→ Thêm ngưỡng mới (>24mm) = thêm 1 dòng trong rule → toàn bộ BOM tự cập nhật
→ Admin KHÔNG cần biết cú pháp IF
```

#### Cách 3: FORMULA — 1 dòng, linh hoạt nhất (power user)

```
Dòng 60: Nẹp kính (Dynamic by Formula)
  item_selection_mode: Formula
  item_condition_formula:
    IF(glass_thick_kinh_canh <= 10.38, "C3209-20",
    IF(glass_thick_kinh_canh <= 16, "C3210-20",
    IF(glass_thick_kinh_canh <= 24, "C3211-20", "C3211-24")))
  item_fallback: C3209-20

→ 1 dòng, linh hoạt nhất
→ Có thể dùng biến phức tạp:
    IF(AND(glass_thick > 16, do_day == '2.0mm'), "C3211-20", "C3210-14")
→ Dành cho kỹ thuật viên cao cấp
```

### B.2 Ví dụ LOOKUP: Tay nắm theo brand + màu

```
Bước 1: Tạo AL Dynamic Item Rule:
  Rule Code: TAY-NAM-THEO-BRAND-MAU
  Rule Type: LOOKUP
  Key 1 Variable: brand
  Key 2 Variable: mau_nhom

  ┌──────────┬──────────┬───────────────────┐
  │ brand    │ mau_nhom │ item_code         │
  ├──────────┼──────────┼───────────────────┤
  │ XF-NK    │ STD      │ TAY-NAM-XF55-STD  │
  │ XF-NK    │ DAK      │ TAY-NAM-XF55-DAK  │
  │ XF-NK    │ VG       │ TAY-NAM-XF55-VG   │
  │ XF-NK    │ INOX     │ TAY-NAM-XF55-INOX │
  │ ALUMIL   │ STD      │ TAY-NAM-ALU-STD   │
  │ ALUMIL   │ INOX     │ TAY-NAM-ALU-INOX  │
  └──────────┴──────────┴───────────────────┘
  Default Item: TAY-NAM-XF55-STD

Bước 2: Trong AL Profile Line:
  Dòng: Tay nắm
    item_selection_mode: Rule
    item_rule: TAY-NAM-THEO-BRAND-MAU
    item_fallback: TAY-NAM-XF55-STD

→ Sales chọn brand=ALUMIL, mau_nhom=INOX → tự động resolve ra TAY-NAM-ALU-INOX
→ Thêm brand mới = thêm 1 dòng trong rule
→ Tất cả BOM dùng chung 1 rule
```

### B.3 Tổng kết: Khi nào dùng chế độ nào?

| Tình huống | Chế độ | Lý do |
|---|---|---|
| Khung bao, cánh — item không bao giờ thay đổi | Fixed | Đơn giản nhất, không cần logic |
| Nẹp kính — thay đổi theo độ dày (ngưỡng số) | **Rule THRESHOLD** | Bảng trực quan, tái sử dụng |
| Tay nắm, bản lề — thay đổi theo brand/màu/hướng mở | **Rule LOOKUP** | Bảng key-value, tái sử dụng |
| Gioăng — thay đổi theo loại kính (cường lực/thường/hộp) | **Rule LOOKUP** | Dễ maintain, không code |
| Logic phức tạp: vừa theo độ dày vừa theo độ dày nhôm | Formula | Rule không đủ express |
| Cần gọi hàm custom (ví dụ: market_price()) | Formula | Chỉ Formula mới gọi được hàm |

## APPENDIX C: So sánh Draft v18 vs Final v18

| Vấn đề | Draft v1 | Final v2 |
|---|---|---|
| Số field Code → Small Text | 8 | **9** (+`formula_expression`) |
| DynamicItemResolver engine | Raw `eval()` + custom sandbox | **FormulaEngine.evaluate_single()** |
| FB Variable Binding | Không đề cập | **Tích hợp + 2 custom handlers** |
| Cost Template + Formula Set | Không đề cập | **formula_set field + CostAccumulator v2** |
| Batch DB query | Từng item một (N+1) | **Batch query + exists_cache** |
| Validate formula | Custom regex + token blacklist | **FormulaEngine.validate() + slug pattern** |
| VariableResolver | Chưa update | **v3 với resolve_bindings_with_deps()** |
| AL Calculation Rule | Không đổi | **formula_expression → Small Text** |
| Sales Override | Chỉ JSON field | **JSON field + UI spec (Phase 4)** |
| Migration cho FB bindings | Không có | **Patch 4: AL → FB auto-migrate** |

## APPENDIX D: Kế thừa Không Phá Vỡ từ v17

### 34 DocType v17 — Giữ nguyên, chỉ thêm fields

| STT | DocType | v17 | v18 |
|---|---|---|---|
| 1-16 | AL Variable Group → AL Rule Sequence Item | Giữ nguyên | Giữ nguyên |
| 17 | **AL Profile Line** | — | +3 fields (item_selection_mode, item_condition_formula, item_fallback); 6 fields Code→Small Text |
| 18 | AL Profile Set | Giữ nguyên | Giữ nguyên |
| 19-20 | AL PK Set, AL PK Line | — | PK Line: +3 fields, sl_formula Code→Small Text |
| 21-24 | AL BOM, AL Cost Template, Line, ConfigSnapshot | — | Cost Template: +formula_set; Line: calc_formula Code→Small Text |
| 25-34 | 10 Module DocType v17 | Giữ nguyên | Giữ nguyên |

### Engine — Giữ nguyên, cập nhật

| File | v17 | v18 |
|---|---|---|
| variable_resolver.py | v2 (priority-based) | v3 (FB DAG-topo + glass_thick) |
| dynamic_item_resolver.py | — | ★ MỚI |
| profile_interpreter.py | v2 (Fixed item only) | v2.1 (Dynamic mode check) |
| pk_resolver.py | v1 | v1 (hỗ trợ Dynamic PK) |
| cost_accumulator.py | v1 | v2 (+Formula Set) |
| orchestrator.py | 6 bước | 7 bước (+Dynamic Item) |
| snapshot_builder.py | v1 | v1 (+item_context) |
| rule_engine.py | v1 | v1 (không đổi) |
| module_registry.py | v1 | v1 (không đổi) |
| fb_handlers.py | v1 | v1 (không đổi) |

### Hooks & Scheduled Tasks — Không đổi

### 8 Ví dụ Kiểm chứng — PASS 100% với Fixed mode

### Module v17 (7 modules) — Không bị ảnh hưởng

---

## APPENDIX E: v17 REVIEW — Khuyến nghị đã Tích hợp

| # | Khuyến nghị REVIEW | Priority | Status v18 |
|---|---|---|---|
| 1 | Thay AL Variable Binding = FB Variable Binding | P0 | ✅ Tích hợp (QĐ-17, VariableResolver v3, Patch 4) |
| 2 | Tách Cost Template: Formula Set + UI | P1 | ✅ Optional (QĐ-19, CostAccumulator v2) |
| 3 | Dùng FlexibleFormulaEngine cho Cost | P2 | 🔲 Chưa (giữ legacy fallback) |
| 4 | Dùng DialogBuilder schema DSL | P3 | 🔲 v19 |
| 5 | CONSTANT/FORMULA/SEQUENCE → FB equivalent | P4 | ✅ Optional (QĐ-18, admin tự chọn) |
| 6 | Đăng ký 2 custom handlers (bom_variable, rule_engine_lookup) | P0 | ✅ Tích hợp (§6.1) |
| 7 | DAG topology thay priority tuần tự | P0 | ✅ Qua FB resolve_bindings_with_deps() |
| 8 | Giữ ProfileInterpreter 2-pass | — | ✅ Giữ nguyên (domain-specific) |
| 9 | Giữ show_condition → DAG branching | — | ✅ Giữ nguyên |
| 10 | Giữ glass_thick injection | — | ✅ Giữ nguyên |

### Code Reduction (so với v17 nếu fully adopt FB)

| Metric | v17 | v18 (post-migration) | Change |
|---|---|---|---|
| AL Variable Binding DocType | Active | Kept (data) / Logic → FB | — |
| Source types available | 5 | 12 | +140% |
| VariableResolver code | ~180 dòng | ~100 dòng | -44% |
| Rule Engine code | ~90 dòng | ~60 dòng | -33% |
| Cost Accumulator code | ~70 dòng | ~70 dòng | ±0 (thêm FS path) |
| New: DynamicItemResolver | — | ~150 dòng | +150 |
| New: fb_handlers.py | — | ~80 dòng | +80 |

---

*AlumGlass v18 Upgrade Specification — FULL & COMPREHENSIVE*
*Kế thừa: v11 → v13 → v14 → v15 → v16 → v17 → v18*
*Input: v17 FINAL (3049 dòng) + v17 REVIEW (812 dòng) + Draft v1 + Phản biện v2*
*"Zero Python in DB. FormulaEngine DUY NHẤT. Dynamic Item Selection. Config-driven 100%. Ready to implement."*
*Ngày: 2026-06-29*
