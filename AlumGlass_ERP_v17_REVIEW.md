# AlumGlass ERP v17.0 — Đánh Giá Kiến Trúc & Đề Xuất Cải Tiến

> **Ngày đánh giá:** 2026-06-26
> **Đối tượng đánh giá:** `AlumGlass_ERP_v17_FINAL.md` + toàn bộ codebase `formula_builder` v29.1+
> **Tiêu chí:** Tận dụng tối đa formula_builder/formula_utils, trao quyền cấu hình nghiệp vụ cho user, giảm thiểu code Python cần dev can thiệp
> **Phạm vi:** 34 DocType, 15 nguyên tắc thiết kế, kiến trúc 6 tầng

---

## TÓM TẮT

Thiết kế v17 đạt **85/100 điểm** về kiến trúc. Các nguyên tắc cốt lõi (Zero Python, `show_condition`, DAG, `glass_thick` injection, module hooks) là xuất sắc và không cần thay đổi.

**Khoảng trống 15 điểm** đến từ việc **4/24 DocType lõi đang xây dựng lại infrastructure mà `formula_builder` đã cung cấp sẵn và mạnh hơn**:

| DocType lõi (AL) | Formula Builder equivalent | Kết luận |
|---|---|---|
| AL Variable Binding | Formula Variable Binding (10 source types + DAG topo) | **FB mạnh hơn đáng kể** |
| AL Cost Template (phần tính toán) | Formula Set | **Có thể thay thế** |
| AL Calculation Rule (CONSTANT, FORMULA) | Formula Global Variable | **Hoàn toàn thay thế được** |
| AL Calculation Rule (SEQUENCE) | Formula Set | **Hoàn toàn thay thế được** |

**Khuyến nghị cốt lõi:** Giữ nguyên 15 nguyên tắc và kiến trúc 6 tầng. Hợp nhất 3 DocType lõi vào formula_builder. Điều này **giảm ~2 DocType, mở rộng source_type từ 5→12, trao cho user khả năng cấu hình mạnh hơn mà không phá vỡ bất kỳ logic engine nào**.

---

## MỤC LỤC

1. [So sánh chi tiết từng DocType với formula_builder](#1-so-sánh-chi-tiết-từng-doctype-với-formula_builder)
2. [Đánh giá 15 nguyên tắc thiết kế](#2-đánh-giá-15-nguyên-tắc-thiết-kế)
3. [Khuyến nghị theo mức độ ưu tiên](#3-khuyến-nghị-theo-mức-độ-ưu-tiên)
4. [So sánh kiến trúc: Hiện tại vs Đề xuất](#4-so-sánh-kiến-trúc-hiện-tại-vs-đề-xuất)
5. [Lộ trình triển khai cải tiến](#5-lộ-trình-triển-khai-cải-tiến)
6. [Nguyên tắc giữ lại — không bao giờ thay đổi](#6-nguyên-tắc-giữ-lại--không-bao-giờ-thay-đổi)
7. [Phân tích rủi ro khi áp dụng cải tiến](#7-phân-tích-rủi-ro-khi-áp-dụng-cải-tiến)
8. [Phụ lục: Code mẫu cho custom source_type handler](#8-phụ-lục-code-mẫu-cho-custom-source_type-handler)

---

## 1. SO SÁNH CHI TIẾT TỪNG DOCTYPE VỚI FORMULA_BUILDER

### 1.1 AL Variable Library vs Formula Global Variable

```
AL VARIABLE LIBRARY               FORMULA GLOBAL VARIABLE           ĐÁNH GIÁ
──────────────────────────────────────────────────────────────────────────────
var_code (Data, unique, reqd)     var_name (Data, unique, reqd)     Tương đương
var_label (Data)                  label (Data)                      Tương đương
var_group (Link → AL Var Group)   category (Data)                   Tương đương
var_type: FLOAT/INT/STR/BOOL      var_type: Float/Int/Currency/     Tương đương +
                                               Percent/Check/Data    FB có thêm Currency
default_val (Data)                constant_value (Data)             Tương đương
options (Data)                    — KHÔNG có                        ← AL giữ lại (Select UI)
ui_widget: Text/Select/Number/    — KHÔNG có                        ← AL giữ lại (widget config)
          Toggle
description (Small Text)          description (Small Text)          Tương đương
— KHÔNG có                        formula_expr (Small Text)         ← FB MẠNH HƠN
                                  value_source: CONSTANT/FORMULA/   ← FB MẠNH HƠN
                                               DB_QUERY
— KHÔNG có                        db_query_doctype (Link)           ← FB MẠNH HƠN
— KHÔNG có                        db_query_field (Data)             ← FB MẠNH HƠN
— KHÔNG có                        db_query_filters (JSON)           ← FB MẠNH HƠN
— KHÔNG có                        unit (Data)                       ← FB có thêm
— KHÔNG có                        is_active (Check)                 ← FB có thêm
```

**Kết luận:** AL Variable Library nên được **giữ lại** vì có `options` và `ui_widget` — hai trường đặc thù cho UI Variable Dialog mà Formula Global Variable không có. Tuy nhiên, với các biến CONSTANT và FORMULA đơn giản, nên dùng Formula Global Variable để tận dụng `formula_expr` và DAG evaluation.

### 1.2 AL Variable Set + AL Variable Set Detail

```
AL VARIABLE SET + DETAIL           FORMULA BUILDER EQUIVALENT        ĐÁNH GIÁ
──────────────────────────────────────────────────────────────────────────────
set_code (Data, unique, reqd)     — Không có trực tiếp              AL đặc thù
set_name (Data)                   —                                AL đặc thù
al_var_details (child table)      ScopeContext + local_vars         Khác cách tiếp cận
  variable (Link → AL Var Lib)      — (dùng filter hoặc context)    AL domain-specific
  is_required (Check)               —                                AL đặc thù
  override_default (Data)           —                                AL đặc thù
  depends_on (Code)                 —                                AL đặc thù (UI logic)
  sort_order (Int)                  —                                AL đặc thù
```

**Kết luận:** AL Variable Set là **domain-specific** — không có equivalent trực tiếp trong formula_builder. Nó phục vụ 2 mục đích: (a) nhóm biến cho từng loại BOM, (b) cấu hình UI Dialog (depends_on, is_required, override_default). **Giữ nguyên**.

### 1.3 AL Variable Binding vs Formula Variable Binding

Đây là điểm **quan trọng nhất** cần cải tiến.

```
AL VARIABLE BINDING                FORMULA VARIABLE BINDING          ĐÁNH GIÁ
──────────────────────────────────────────────────────────────────────────────
binding_code (Data, unique)        — (tự sinh)                       AL đặc thù
variable_name (Data, reqd)         variable_name (Data, reqd)        Tương đương
variable_label (Data)              variable_label (Data)             Tương đương

source_type (Select):              source_type (Select):             FB MẠNH HƠN (10 vs 5)
  Quotation Input                    constant                        ← FB có
  BOM Variable                       linked_doctype_field             ← FB có
  BOM Attribute                      whole_doctype                   ← FB có (mới)
  Rule Engine Result                 child_table_aggregate           ← FB có (mới)
  Computed                           global_default                  ← FB có
  Context Inject                     session_variable                ← FB có
                                     doctype_query                   ← FB có (mới)
                                     custom_function                 ← FB có (mới)
                                     dynamic_link                    ← FB có
                                     computed (có DAG topo!)         ← FB MẠNH HƠN

resolve_priority (Int, default 50)  resolve_priority (Int,           Tương đương
                                                        default 100)
                                    + topological sort (Kahn's       ← FB MẠNH HƠN ĐÁNG KỂ
                                      algorithm) cho computed type

source_config (JSON)                source_config (JSON)             Tương đương
data_type: Float/String/Integer/    data_type: Float/Int/Currency/   Tương đương
           Boolean                             Percent/Check/Data/Object
is_active (Check, default 1)        is_active (Check, default 1)     Tương đương
description (Small Text)            —                                 AL có thêm

— KHÔNG có                          applies_to_doctype (Link)        ← FB: scope theo doctype
— KHÔNG có                          applies_to_field (Data)          ← FB: scope theo field
— KHÔNG có                          is_global (Check)                ← FB: scope global
— KHÔNG có                          default_value (Data)             ← FB có thêm
```

#### Phân tích 5 source_type của AL:

| AL Source Type | Cách hoạt động | Map sang FB handler |
|---|---|---|
| Quotation Input | `config.fieldname` → `quotation_item.get(fieldname)` | `linked_doctype_field` hoặc custom handler đọc từ unsaved doc |
| BOM Variable | `config.var_code` → `al_bom_vars[var_code]` | **Cần custom handler** `bom_variable` |
| BOM Attribute | `config.attribute` → `bom_doc.get(attribute)` | `linked_doctype_field` |
| Rule Engine Result | `config.rule_code` + `config.args` → LOOKUP table | **Cần custom handler** `rule_engine_lookup` |
| Computed | `config.formula` → eval đơn giản | `computed` của FB (mạnh hơn: có DAG) |
| Context Inject | (không resolve — handled separately) | Giữ nguyên logic `glass_thick` injection |

#### Phân tích 10 source_type của FB mà AL chưa dùng:

| FB Source Type | Mô tả | Ví dụ ứng dụng trong AlumGlass |
|---|---|---|
| `linked_doctype_field` | Đọc field từ doctype liên kết | `customer.default_price_list` → bảng giá mặc định |
| `whole_doctype` | Trả về toàn bộ document dạng dict | `quotation.*` → truy cập mọi field của Quotation |
| `child_table_aggregate` | SUM/AVG/MIN/MAX/COUNT dòng con | **Tổng diện tích kính** từ tất cả dòng KINH |
| `global_default` | Đọc Global Defaults | `default_company`, `default_currency` |
| `session_variable` | user, roles, company, today, now | `today` → tự động áp dụng discount theo mùa |
| `doctype_query` | Query bất kỳ doctype | Tra cứu tỷ giá USD/VND, lãi suất ngân hàng |
| `custom_function` | Gọi hàm Python whitelist | `get_aluminum_market_price("XF-NK", "STD")` |
| `dynamic_link` | Dynamic Link field | Linh hoạt hơn linked_doctype_field |
| `computed` | Formula với DAG topology | Thay thế AL Computed — **mạnh hơn vì có DAG** |

**Kết luận:** AL Variable Binding là bản sao yếu hơn của Formula Variable Binding. Nên **thay thế hoàn toàn**, đăng ký 2 custom handler `rule_engine_lookup` và `bom_variable` vào `data_source_registry`. User sẽ có 12 source types thay vì 5, và được hưởng DAG topology resolution.

### 1.4 AL Cost Template + Line vs Formula Set + Line

```
AL COST TEMPLATE + LINE            FORMULA SET + LINE                ĐÁNH GIÁ
──────────────────────────────────────────────────────────────────────────────
template_code (Data, unique)       set_code (Data, unique)           Tương đương
template_name (Data)               label (Data)                      Tương đương
product_type (Link)                linked_doctype (Link)             Cùng ý nghĩa (scope)
al_lines (child table)             formulas (child table)            Cùng cấu trúc
  sort_order (Int)                   — (theo thứ tự row)             AL đặc thù
  line_code (Data)                   var_name (Data)                 Tương đương
  line_label (Data)                  description (Small Text)        Gần tương đương
  calc_formula (Code)                formula (Small Text)            Tương đương ★
  cost_bucket (Link)                 — KHÔNG có                      ← AL đặc thù
  is_subtotal (Check)                — KHÔNG có                      ← AL đặc thù
  show_on_quotation (Check)          — KHÔNG có                      ← AL đặc thù
```

**★ Ghi chú về `calc_formula`:** Đây là formula string chạy qua FormulaEngine. Về mặt kỹ thuật, nó tương đương với `formula` trong Formula Set Line. Sự khác biệt nằm ở **ngữ cảnh sử dụng**: AL Cost Template formulas tham chiếu đến các cost bucket (VL_NHOM, TONG_VL, GIA_THANH...) — đây là các biến được sinh ra từ engine. Formula Set không có context này mặc định.

**Kết luận:** AL Cost Template nên được **tách thành 2 layer**:
- **Layer tính toán:** Dùng `Formula Set` của formula_builder. Các dòng `calc_formula` chuyển thành `formula` trong Formula Set Line.
- **Layer trình bày:** AL Cost Template giữ lại các metadata hiển thị (line_label, is_subtotal, show_on_quotation, sort_order) và thêm trường `formula_set` (Link → Formula Set).

### 1.5 AL Calculation Rule vs Formula Global Variable + Formula Set

```
AL CALCULATION RULE                FB EQUIVALENT                     ĐÁNH GIÁ
──────────────────────────────────────────────────────────────────────────────
rule_type: CONSTANT                Formula Global Variable           ← HOÀN TOÀN THAY THẾ
  constant_value (Data)              (CONSTANT) + constant_value       ĐƯỢC

rule_type: FORMULA                 Formula Global Variable           ← HOÀN TOÀN THAY THẾ
  formula_expression (Code)          (FORMULA) + formula_expr          ĐƯỢC

rule_type: LOOKUP                  — KHÔNG có trực tiếp              ← CẦN GIỮ LẠI
  lookup_key_1_var, lookup_key_2    (có thể dùng doctype_query       (table UX đặc thù)
  lookup_rows (child table)          hoặc custom_function,           quá đặc thù để thay
  lookup_default                     nhưng mất table UX)             bằng FB generic)

rule_type: THRESHOLD               — KHÔNG có                        ← CẦN GIỮ LẠI
  threshold_input_var               (có thể dùng IFS() trong         (IFS chain generation
  threshold_rows (child table)       formula trực tiếp,              là domain-specific)
                                     nhưng mất table UX)

rule_type: SEQUENCE                Formula Set                       ← HOÀN TOÀN THAY THẾ
  sequence_items (child table)       (tập hợp các formula)            ĐƯỢC
```

**Kết luận:** AL Calculation Rule nên được **tinh gọn**:
- **Giữ lại** THRESHOLD và LOOKUP — đây là domain-specific với table-based UX không có trong FB
- **Chuyển sang** Formula Global Variable cho CONSTANT và FORMULA — tận dụng `formula_expr` evaluation của FB
- **Chuyển sang** Formula Set cho SEQUENCE — tập hợp formula tái sử dụng

### 1.6 AL Profile Line — so sánh với FlexibleFormulaEngine ChildTableConfig

```
AL PROFILE LINE                    ChildTableConfig                   ĐÁNH GIÁ
──────────────────────────────────────────────────────────────────────────────
1 bảng al_lines (NHOM/KINH/VTP/PK) table_key                         Tương đương
qty_formula / width_formula /      formula_field                     AL phức tạp hơn (nhiều
height_formula / show_condition /                                     formula fields, không
panel_count_formula / ...                                             chỉ 1 field)
slug (unique per Profile Set)      id_field                          Tương đương
line_type + các trường riêng       row_fields (auto-detect)          AL dùng Python build,
                                                                     FB dùng inject tự động

★ ĐIỂM KHÁC BIỆT CHÍNH:
- AL: 2-pass (scan → build), sinh formula string thủ công, 1 dòng KINH → N panel formulas
- FB: 1-pass, inject row values thành literals trước khi evaluate, 1 row → 1 formula
- AL: show_condition → biến boolean trong DAG
- FB: không có khái niệm show_condition riêng
- AL: glass_thick_{prefix} → inject vào context phẳng
- FB: không có cơ chế cross-row variable injection tương tự
```

**Kết luận:** ProfileInterpreter 2-pass **phải giữ nguyên** vì FlexibleFormulaEngine không được thiết kế để xử lý:
1. `show_condition` → DAG branching
2. `glass_thick_{prefix}` → cross-line injection
3. Panel Expansion (1 dòng → N panel)
4. Sort-order-independent calculation

Đây là phần **domain-specific nhất** của toàn bộ hệ thống, và việc tự build formula string là cần thiết.

---

## 2. ĐÁNH GIÁ 15 NGUYÊN TẮC THIẾT KẾ

| # | Nguyên tắc | Điểm | Đánh giá | Ghi chú |
|---|---|---|---|---|
| 1 | Zero Python trong DB | ⭐⭐⭐⭐⭐ | Xuất sắc | Nguyên tắc quan trọng nhất — giữ vững tuyệt đối |
| 2 | Chọn Item trực tiếp | ⭐⭐⭐⭐ | Tốt | Đúng với triết lý ERPNext — không cần thay đổi |
| 3 | `show_condition` thay `if/elif` | ⭐⭐⭐⭐⭐ | Xuất sắc | Pattern này nên được đề xuất upstream cho formula_builder adopt |
| 4 | Thống nhất bảng `al_lines` | ⭐⭐⭐⭐⭐ | Xuất sắc | Đơn giản hơn multi-table của FlexibleFormulaEngine cho use case này |
| 5 | DAG là nguồn sự thật | ⭐⭐⭐⭐ | Tốt | **Nhưng chưa dùng DAG cho variable binding** → điểm cần cải thiện |
| 6 | Panel Expansion động | ⭐⭐⭐⭐⭐ | Xuất sắc | Rất khó làm với FlexibleFormulaEngine thuần — giữ nguyên |
| 7 | Giá kính tách kích thước SX | ⭐⭐⭐⭐ | Tốt | Cho phép Phase 3 độc lập |
| 8 | PK: mặc định + thay thế | ⭐⭐⭐⭐ | Tốt | Pattern chuẩn với validation |
| 9 | Context phẳng | ⭐⭐⭐⭐⭐ | Xuất sắc | Debug = `print(inputs_dict)` — triết lý đúng đắn |
| 10 | Rule là thư viện dùng chung | ⭐⭐⭐ | Khá | **CONSTANT/FORMULA/SEQUENCE nên dùng FB equivalent** |
| 11 | Formula Engine là lõi DUY NHẤT | ⭐⭐⭐⭐ | Tốt | **Nhưng bỏ qua FlexibleFormulaEngine cho cost template** |
| 12 | Minh bạch tuyệt đối | ⭐⭐⭐⭐⭐ | Xuất sắc | ConfigSnapshot + explain() — gold standard |
| 13 | Module hook không phá lõi | ⭐⭐⭐⭐⭐ | Xuất sắc | Pattern xuất sắc — nên chuẩn hóa thành best practice |
| 14 | BOM Version immutable | ⭐⭐⭐⭐⭐ | Xuất sắc | SHA-256 snapshot + diff + rollback — chuẩn audit |
| 15 | Approval trước hiệu lực | ⭐⭐⭐⭐ | Tốt | Tích hợp tốt với ERPNext workflow |

**Điểm tổng quan: 85/100**

- **15 điểm mất** đến từ: Variable Binding không dùng FB (5đ), Cost Template không dùng Formula Set (5đ), Rule CONSTANT/FORMULA/SEQUENCE tự build (5đ)
- **Không có điểm yếu nghiêm trọng** nào về kiến trúc — tất cả đều là cơ hội tối ưu

---

## 3. KHUYẾN NGHỊ THEO MỨC ĐỘ ƯU TIÊN

### 🔴 P0 — QUAN TRỌNG NHẤT: Thay AL Variable Binding bằng Formula Variable Binding

**Hiện trạng:**
- AL Variable Binding: 5 source_type, resolve tuần tự theo priority, không có DAG
- ~180 dòng Python trong `variable_resolver.py` để xử lý binding
- Nếu binding B phụ thuộc binding A, dev phải set đúng `resolve_priority` (dễ sai)

**Đề xuất chi tiết:**

1. **Xóa DocType `AL Variable Binding`** khỏi thiết kế (giữ lại data cũ để migration)
2. **Sử dụng `Formula Variable Binding`** của formula_builder làm nguồn binding duy nhất
3. **Đăng ký 2 custom source_type handler** vào `data_source_registry` của FB:
   ```python
   # Handler 1: rule_engine_lookup
   # Thay thế AL source_type "Rule Engine Result"
   # Input: source_config = {"rule_code": "TRA-GIA-NHOM", "args": {"key_1": "brand", "key_2": "mau_nhom"}}
   # Output: giá trị từ AL Calculation Rule LOOKUP table

   # Handler 2: bom_variable
   # Thay thế AL source_type "BOM Variable"
   # Input: source_config = {"var_code": "n_canh"}
   # Output: giá trị từ al_bom_vars JSON của quotation_item
   ```
4. **Cập nhật VariableResolver**: bỏ `_resolve_bindings()`, gọi `data_source_registry.resolve_bindings_with_deps()` thay thế
5. **5 AL source_type map sang FB như sau:**

| AL source_type | FB source_type / Handler |
|---|---|
| Quotation Input | `linked_doctype_field` — đọc field từ Quotation Item |
| BOM Variable | `bom_variable` (custom handler) |
| BOM Attribute | `linked_doctype_field` — đọc field từ AL BOM |
| Rule Engine Result | `rule_engine_lookup` (custom handler) |
| Computed | `computed` của FB (có DAG topology) |

**Lợi ích cụ thể cho user cuối:**
- Kỹ thuật viên có thể cấu hình `child_table_aggregate` để tính "tổng diện tích toàn bộ kính trong BOM" — không cần dev
- Kế toán có thể dùng `doctype_query` để tra cứu tỷ giá USD/VND, lãi suất ngân hàng — không cần dev
- Admin có thể đăng ký `custom_function` để gọi API giá nhôm thị trường — không cần sửa code
- Mọi binding resolve theo DAG topology — không còn lỗi "biến B chưa có khi biến A cần"
- User được 12 source types thay vì 5
- Dev giảm ~140 dòng code Python phải maintain

**Impact đánh giá:**
- Rủi ro: **Trung bình** — cần migrate data, test kỹ 8 ví dụ kiểm chứng
- Effort: **2-3 tuần** — đăng ký handler, cập nhật VariableResolver, migration script
- Rollback: **Dễ** — giữ AL Variable Binding DocType, switch flag để dùng lại logic cũ

### 🟠 P1 — CAO: Tách Cost Template thành Formula Set (engine) + AL Cost Template (UI)

**Hiện trạng:**
- AL Cost Template vừa làm engine tính toán vừa làm metadata hiển thị
- `CostAccumulator.build_bucket_and_template_formulas()` build formula string thủ công

**Đề xuất chi tiết:**

1. **Giữ nguyên AL Cost Template** với các trường hiển thị:
   - `template_code`, `template_name`, `product_type`
   - `al_lines` child table với: `sort_order`, `line_code`, `line_label`, `cost_bucket`, `is_subtotal`, `show_on_quotation`
2. **Thêm trường `formula_set`** (Link → Formula Set) vào AL Cost Template
3. **Khi tạo Cost Template**:
   - User khai báo display metadata trong AL Cost Template form
   - Phần `calc_formula` được quản lý bởi Formula Set (mở Formula Builder editor)
4. **Khi tính toán**:
   - `CostAccumulator` gọi `VariableResolver._get_formula_set_output()` để evaluate Formula Set
   - Các cost bucket (VL_NHOM, TONG_VL...) vẫn được build như cũ → inject vào context của Formula Set
5. **Migration**: Tự động tạo Formula Set từ AL Cost Template Line hiện có

**Lợi ích:**
- Cost Template formula được quản lý bởi formula_builder's DAG engine
- User có thể dùng tất cả 100+ BASE_FUNCS trong cost template formulas
- Tận dụng Monaco editor có sẵn của formula_builder
- explain() của formula_builder cho từng dòng cost → audit trail mạnh hơn

### 🟡 P2 — TRUNG BÌNH: Dùng FlexibleFormulaEngine cho phần Cost Accumulator

**Hiện trạng:** `CostAccumulator.build_bucket_and_template_formulas()` build danh sách `[{name, formula}]` thủ công.

**Đề xuất:** Sử dụng `FlexibleFormulaEngine` với `ChildTableConfig`:
```python
from formula_builder.integration import FlexibleFormulaEngine, EngineConfig, ChildTableConfig

engine = FlexibleFormulaEngine(EngineConfig(
    child_tables=[
        ChildTableConfig(
            table_key="cost_template_lines",
            formula_field="calc_formula",
            id_field="line_code",
            row_fields=[],          # auto-detect
            output_field=None,      # không write-back
        ),
    ],
    global_formulas=bucket_formulas,  # VL_NHOM = sum of all nhom lines
    extra_context=bucket_context,     # Các biến bucket đã tính
    deterministic=True,
))
result = engine.calculate({"cost_template_lines": template_lines})
```

**Lợi ích:** Loại bỏ code build formula thủ công; auto-detect row fields; hỗ trợ assertion/validation; multi-scenario comparison có sẵn.

### 🟢 P3 — THẤP: Dùng DialogBuilder schema DSL cho BOM Dialog

**Hiện trạng:** `quotation_item.js` dài ~400 dòng, build dialog hoàn toàn thủ công.

**Đề xuất:** Dùng `formula_builder.formulaDialog.define()` + `filterSection()` + `tableSection()`:
```javascript
const schema = formula_builder.formulaDialog.define({
    title: "Tính giá BOM",
    sections: [
        formula_builder.formulaDialog.filterSection({
            label: "Kích thước & Thông số",
            key: "inputs",
            fields: [
                { fieldname: "al_W_mm", label: "Chiều rộng (mm)", fieldtype: "Float", reqd: 1 },
                { fieldname: "al_H_mm", label: "Chiều cao (mm)", fieldtype: "Float", reqd: 1 },
                // ... dynamic fields from Variable Set
            ],
        }),
        formula_builder.formulaDialog.tableSection({
            label: "Chọn kính",
            key: "glass_selections",
            columns: [
                { fieldname: "line_name", label: "Loại kính", fieldtype: "Data", read_only: 1 },
                { fieldname: "glass_code", label: "Mã kính", fieldtype: "Select", formula: false },
            ],
        }),
    ],
    onSave: (data) => { alumglass_calculate(data); },
});
formula_builder.formulaDialog.open(schema);
```

**Lợi ích:**
- Giảm ~200 dòng JS
- Giao diện consistent với formula_builder
- Tự động có resize/drag/close/Esc
- Monaco cells cho formula fields với autocomplete
- Table rows có add/delete tự động

### 🔵 P4 — THAM KHẢO: Chuyển CONSTANT/FORMULA/SEQUENCE rules sang FB

**Đề xuất:**
- CONSTANT → `Formula Global Variable` (value_source = CONSTANT)
- FORMULA → `Formula Global Variable` (value_source = FORMULA)
- SEQUENCE → `Formula Set`
- Giữ lại THRESHOLD và LOOKUP trong AL Calculation Rule

**Lưu ý:** Đây là cải tiến thẩm mỹ/kiến trúc hơn là chức năng. User experience không thay đổi nhiều. Có thể triển khai sau P0-P3.

---

## 4. SO SÁNH KIẾN TRÚC: HIỆN TẠI VS ĐỀ XUẤT

### 4.1 Số lượng DocType

```
DOC TYPE                         HIỆN TẠI    ĐỀ XUẤT    THAY ĐỔI
──────────────────────────────────────────────────────────────
AL Variable Group                    ✓           ✓         Giữ
AL Material Type                     ✓           ✓         Giữ
AL Glass Type                        ✓           ✓         Giữ
AL Glass Layer Type                  ✓           ✓         Giữ
AL Glass Master                      ✓           ✓         Giữ
AL Glass Layer Line                  ✓           ✓         Giữ
AL Product Type                      ✓           ✓         Giữ
AL Variable Library                  ✓           ✓         Giữ (có UI fields riêng)
AL Variable Set                      ✓           ✓         Giữ (nhóm biến cho BOM)
AL Variable Set Detail               ✓           ✓         Giữ
AL Variable Binding                  ✓           ✗         ← THAY bằng Formula Variable Binding
AL Cost Bucket                       ✓           ✓         Giữ
AL Calculation Rule                  ✓           ✓         Giữ (chỉ THRESHOLD + LOOKUP)
AL Rule Threshold Row                ✓           ✓         Giữ
AL Rule Lookup Row                   ✓           ✓         Giữ
AL Rule Sequence Item                ✓           ✗         ← THAY bằng Formula Set
AL Profile Line                      ✓           ✓         Giữ (domain-specific)
AL Profile Set                       ✓           ✓         Giữ
AL PK Set                            ✓           ✓         Giữ
AL PK Line                           ✓           ✓         Giữ
AL BOM                               ✓           ✓         Giữ
AL Cost Template                     ✓           ✓         Giữ (thêm ref → Formula Set)
AL Cost Template Line                ✓           ✓         Giữ (display metadata)
ConfigSnapshot                       ✓           ✓         Giữ
AL BOM Version                       ✓           ✓         Giữ (v17)
AL BOM Change Log                    ✓           ✓         Giữ (v17)
AL Discount Rule                     ✓           ✓         Giữ (v17)
AL Discount Rule Line                ✓           ✓         Giữ (v17)
AL Material Plan                     ✓           ✓         Giữ (v17)
AL Material Plan Line                ✓           ✓         Giữ (v17)
AL Cost Variance                     ✓           ✓         Giữ (v17)
AL Alert Config                      ✓           ✓         Giữ (v17)
AL Dashboard Config                  ✓           ✓         Giữ (v17)
AL Sales KPI                         ✓           ✓         Giữ (v17)
──────────────────────────────────────────────────────────────
TỔNG                                34          32        Giảm 2 (Variable Binding + Sequence Item)
```

### 4.2 Số dòng code Python

```
FILE                              HIỆN TẠI    ĐỀ XUẤT    THAY ĐỔI
──────────────────────────────────────────────────────────────
variable_resolver.py               ~180 dòng   ~80 dòng    Giảm ~100 dòng (dùng FB thay vì tự build)
rule_engine.py                      ~90 dòng   ~50 dòng    Giảm ~40 dòng (bỏ CONSTANT, FORMULA, SEQUENCE)
cost_accumulator.py                 ~70 dòng   ~40 dòng    Giảm ~30 dòng (dùng FlexibleFormulaEngine)
orchestrator.py                    ~280 dòng  ~250 dòng    Giảm ~30 dòng
data_source_registry (FB)          —           +40 dòng    Thêm 2 custom handler
──────────────────────────────────────────────────────────────
TỔNG                               ~620 dòng  ~460 dòng    Giảm ~160 dòng Python (-26%)
```

### 4.3 Số dòng JavaScript

```
FILE                              HIỆN TẠI    ĐỀ XUẤT    THAY ĐỔI
──────────────────────────────────────────────────────────────
quotation_item.js                  ~400 dòng   ~200 dòng    Giảm ~200 dòng (dùng DialogBuilder)
bom_dialog.js                      ~280 dòng   ~220 dòng    Giảm ~60 dòng
──────────────────────────────────────────────────────────────
TỔNG                               ~680 dòng   ~420 dòng    Giảm ~260 dòng JS (-38%)
```

### 4.4 Source types available cho user

```
HIỆN TẠI: 5 loại
  Quotation Input, BOM Variable, BOM Attribute,
  Rule Engine Result, Computed

ĐỀ XUẤT: 12 loại
  10 loại có sẵn từ Formula Variable Binding:
    constant, linked_doctype_field, whole_doctype,
    child_table_aggregate, global_default, session_variable,
    doctype_query, custom_function, dynamic_link, computed
  + 2 custom handler:
    rule_engine_lookup, bom_variable
```

### 4.5 Variable Resolution Engine

```
HIỆN TẠI:
  resolve_priority ASC → duyệt tuần tự → nếu biến B phụ thuộc biến A, 
  dev phải set priority B > priority A (dễ sai, khó debug)

ĐỀ XUẤT:
  Kahn's algorithm topological sort → tự động phát hiện dependency graph
  → resolve theo topological order → cycle detection tự động
  → fallback về resolve_priority nếu có cycle
```

---

## 5. LỘ TRÌNH TRIỂN KHAI CẢI TIẾN

### Giai đoạn 1: Chuẩn bị — Không phá vỡ (1-2 tuần)

**Mục tiêu:** Thêm infrastructure mới, giữ nguyên engine cũ chạy song song.

| # | Công việc | File/Area | Effort |
|---|---|---|---|
| 1.1 | Đăng ký 2 custom source_type handler vào `data_source_registry` của FB | `formula_builder/api/data_source_registry.py` — thêm `_handle_bom_variable` và `_handle_rule_engine_lookup` | 2 ngày |
| 1.2 | Thêm trường `formula_set` (optional) vào AL Cost Template | AL Cost Template DocType | 1 ngày |
| 1.3 | Tạo migration script: sinh Formula Global Variable từ AL Calculation Rule CONSTANT | `patches/v17_1/migrate_rules_to_fb.py` | 1 ngày |
| 1.4 | Viết test: gọi `resolve_bindings_with_deps()` song song với logic cũ, so sánh kết quả | `tests/test_variable_binding_migration.py` | 2 ngày |
| 1.5 | Verify: 8 ví dụ kiểm chứng v17 vẫn PASS 100% | Manual test | 2 ngày |

### Giai đoạn 2: Chuyển đổi Variable Binding (2-3 tuần)

**Mục tiêu:** Switch hoàn toàn sang Formula Variable Binding, deprecate AL Variable Binding.

| # | Công việc | Effort |
|---|---|---|
| 2.1 | Migration script: tạo Formula Variable Binding records từ AL Variable Binding | 2 ngày |
| 2.2 | Cập nhật `VariableResolver._resolve_bindings()`: gọi `resolve_bindings_with_deps()` thay vì duyệt tuần tự | 1 ngày |
| 2.3 | Cập nhật `RuleEngine`: xóa logic CONSTANT, FORMULA, SEQUENCE | 1 ngày |
| 2.4 | Integration test: chạy toàn bộ pipeline với FB bindings | 3 ngày |
| 2.5 | Deprecate AL Variable Binding DocType (ẩn khỏi Desk, không xóa data) | 0.5 ngày |
| 2.6 | Cập nhật documentation: hướng dẫn user dùng 12 source types mới | 2 ngày |

### Giai đoạn 3: Tối ưu hóa (1-2 tuần)

**Mục tiêu:** Dùng FlexibleFormulaEngine cho Cost Accumulator, DialogBuilder cho UI.

| # | Công việc | Effort |
|---|---|---|
| 3.1 | `CostAccumulator` dùng `FlexibleFormulaEngine` với `ChildTableConfig` | 2 ngày |
| 3.2 | `BOM Dialog` dùng `DialogBuilder` schema DSL thay vì build thủ công | 3 ngày |
| 3.3 | AL Calculation Rule SEQUENCE → migrate sang Formula Set | 1 ngày |
| 3.4 | Cleanup: xóa code cũ không dùng nữa | 1 ngày |
| 3.5 | Full regression test: tất cả ví dụ kiểm chứng + thêm test case mới | 3 ngày |

---

## 6. NGUYÊN TẮC GIỮ LẠI — KHÔNG BAO GIỜ THAY ĐỔI

Những thành phần sau **phải được bảo vệ tuyệt đối** vì chúng là domain-specific, đã được chứng minh qua 7 phiên bản (v11→v17), và formula_builder không có equivalent:

| # | Component | Lý do không thể thay thế bằng FB |
|---|---|---|
| 1 | **`show_condition` → `IF(cond, formula, 0)`** | Pattern đặc thù: nhiều dòng NHOM cùng vai trò, điều kiện hiển thị dựa trên `glass_thick`. FB không có khái niệm "conditional formula activation". |
| 2 | **`glass_thick_{prefix}` injection** | Giải quyết circular dependency Al↔Kính: NHOM cần biết độ dày kính để chọn nẹp, nhưng KINH chưa được build formula. Inject vào context phẳng → DAG không bị cycle. |
| 3 | **`panel_count_formula` + Panel Expansion** | 1 dòng KINH → N panel formulas. FB không hỗ trợ row → multi-row expansion tại runtime. |
| 4 | **1 bảng `al_lines` thống nhất** | Đơn giản hơn multi-table của FlexibleFormulaEngine. Admin khai báo tự do sort_order. Code xử lý tập trung 1 nơi. |
| 5 | **ProfileInterpreter 2-pass** | Pass 1 đăng ký biến → Pass 2 build formula. Đảm bảo biến `glass_thick_kinh_canh` tồn tại trước khi NHOM formulas tham chiếu. FB không có cơ chế 2-pass. |
| 6 | **AL Calculation Rule THRESHOLD + LOOKUP** | Table-based UX cho phép user không cần code. Ví dụ: thêm 1 dòng ngưỡng mới = thêm 1 row trong bảng. FB không có UX equivalent. |
| 7 | **ConfigSnapshot + verify()** | Audit trail với SHA-256 hash, drift detection cho cả Profile Set và BOM Version. Đặc thù AlumGlass — không có trong FB. |
| 8 | **PK substitution với validation** | Cho phép Sales chọn item thay thế nhưng giới hạn trong item_group. Validation chain: allow_substitute → substitute_item_group → is_active → al_item_type. |
| 9 | **BOM Version = immutable snapshot** | Full JSON snapshot của Profile Set + Variable Set + Cost Template + PK Set. Rollback tạo version mới (không xóa). Audit trail đầy đủ. |
| 10 | **Module Hook Registry** | Event bus pattern: modules đăng ký hook, engine fire hooks. Orchestrator không import module nào. Đây là pattern nên chuẩn hóa, không thay đổi. |

---

## 7. PHÂN TÍCH RỦI RO KHI ÁP DỤNG CẢI TIẾN

| # | Rủi ro | Mức độ | Biện pháp giảm thiểu |
|---|---|---|---|
| 1 | **Regression 8 ví dụ kiểm chứng** | Cao | Chạy test sau mỗi giai đoạn. Giữ logic cũ chạy song song trong GĐ1. |
| 2 | **Formula Variable Binding không hỗ trợ unsaved doc** | Trung bình | AL VariableResolver cần truy cập unsaved Quotation Item. Giải pháp: dùng `extra` param của `build_full_context()` để inject `__frm_doc__`. |
| 3 | **Performance: DAG topo sort cho nhiều binding** | Thấp | Kahn's algorithm O(V+E). Với <100 bindings, chi phí không đáng kể. Cache kết quả topo sort. |
| 4 | **User quen với AL Variable Binding UI** | Thấp | Formula Variable Binding có UI tương tự (cũng là Frappe form). Thêm documentation + video hướng dẫn. |
| 5 | **Rollback nếu FB thay đổi API** | Thấp | FB đã ổn định ở v29.1+. Pin version FB trong requirements. |
| 6 | **custom_function bảo mật** | Trung bình | Chỉ whitelist các module path được admin phê duyệt. Dùng `Formula Builder Settings` để quản lý whitelist. |

---

## 8. PHỤ LỤC: CODE MẪU CHO CUSTOM SOURCE_TYPE HANDLER

### 8.1 Handler: `bom_variable`

```python
# Đăng ký trong formula_builder/api/data_source_registry.py
# hoặc trong alumglass/modules/__init__.py nếu FB hỗ trợ plugin

def _handle_bom_variable(binding, doc, resolved_so_far):
    """Resolve BOM variable từ al_bom_vars JSON của quotation_item.
    
    source_config format:
        {"var_code": "n_canh", "default": 1}
    """
    import json
    
    config = binding.source_config or {}
    var_code = config.get("var_code", "")
    default = config.get("default")
    
    # Đọc từ quotation_item (doc là Quotation Item)
    bom_vars = doc.get("al_bom_vars", {})
    if isinstance(bom_vars, str):
        try:
            bom_vars = json.loads(bom_vars)
        except (json.JSONDecodeError, TypeError):
            bom_vars = {}
    
    return bom_vars.get(var_code, default)


# Đăng ký handler
DATA_SOURCE_HANDLERS["bom_variable"] = _handle_bom_variable
```

### 8.2 Handler: `rule_engine_lookup`

```python
def _handle_rule_engine_lookup(binding, doc, resolved_so_far):
    """Resolve LOOKUP rule từ AL Calculation Rule.
    
    source_config format:
        {
            "rule_code": "TRA-GIA-NHOM",
            "arg_mapping": {
                "key_1": "brand",       # variable name in resolved_so_far
                "key_2": "mau_nhom"     # variable name in resolved_so_far
            }
        }
    """
    import frappe
    from frappe.utils import flt
    
    config = binding.source_config or {}
    rule_code = config.get("rule_code", "")
    arg_mapping = config.get("arg_mapping", {})
    
    if not rule_code:
        return None
    
    # Kiểm tra rule tồn tại
    rule = frappe.db.get_value(
        "AL Calculation Rule",
        {"rule_code": rule_code, "rule_type": "LOOKUP", "is_active": 1},
        ["name", "lookup_default"],
        as_dict=True,
    )
    if not rule:
        frappe.log_error(f"LOOKUP rule not found: {rule_code}")
        return None
    
    # Build key values từ resolved_so_far
    key_values = {}
    for key_name, var_name in arg_mapping.items():
        key_values[key_name] = resolved_so_far.get(var_name, "")
    
    # Tra bảng lookup
    lookup_rows = frappe.get_all(
        "AL Rule Lookup Row",
        filters={"parent": rule.name},
        fields=["key_1", "key_2", "key_3", "result_value"],
    )
    
    for row in lookup_rows:
        match = True
        if key_values.get("key_1") and row.key_1:
            if str(key_values["key_1"]) != str(row.key_1):
                match = False
        if key_values.get("key_2") and row.key_2:
            if str(key_values["key_2"]) != str(row.key_2):
                match = False
        if key_values.get("key_3") and row.key_3:
            if str(key_values["key_3"]) != str(row.key_3):
                match = False
        if match:
            return flt(row.result_value or 0)
    
    # Fallback về default
    return flt(rule.lookup_default or 0)


# Đăng ký handler
DATA_SOURCE_HANDLERS["rule_engine_lookup"] = _handle_rule_engine_lookup
```

### 8.3 Cập nhật VariableResolver

```python
# alumglass/engine/variable_resolver.py — phiên bản đề xuất

class VariableResolver:
    def resolve(self, quotation_item, bom_doc):
        # Bước 1: Resolve qua Formula Variable Binding (có DAG topo)
        from formula_builder.api.data_source_registry import resolve_bindings_with_deps
        
        bindings = frappe.get_all(
            "Formula Variable Binding",
            filters={"is_active": 1},
            fields=["*"],
        )
        
        # Bindings được resolve theo topological order
        # (computed bindings tự động xếp sau dependencies của nó)
        inputs_dict = resolve_bindings_with_deps(bindings, quotation_item)
        
        # Bổ sung biến từ AL Variable Set (BOM variables + overrides)
        inputs_dict.update(self._resolve_bom_variables(bom_doc, quotation_item))
        
        # Bổ sung quotation inputs trực tiếp (W_mm, H_mm, qty)
        inputs_dict.update(self._resolve_quotation_inputs(quotation_item))
        
        # Resolve LOOKUP rules (cần inputs_dict đã có brand, mau_nhom)
        inputs_dict.update(self._resolve_lookup_rules(inputs_dict, quotation_item, bom_doc))
        
        # Bước 2: Inject glass_thick cho mọi dòng KINH (GIỮ NGUYÊN)
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
```

### 8.4 Cost Accumulator dùng FlexibleFormulaEngine

```python
# alumglass/engine/cost_accumulator.py — phiên bản đề xuất

from formula_builder.integration import FlexibleFormulaEngine, EngineConfig, ChildTableConfig
from formula_builder.formula_utils import FormulaEngine

class CostAccumulator:
    def build_bucket_and_template_formulas(self, bucket_acc, cost_template_name):
        formulas = []
        
        # Bucket formulas vẫn build thủ công (đơn giản)
        for bucket_code, var_list in bucket_acc.items():
            if var_list:
                formulas.append({
                    "name": bucket_code,
                    "formula": " + ".join(var_list),
                })
        
        # Nếu Cost Template có formula_set → dùng Formula Set
        if cost_template_name:
            formula_set = frappe.db.get_value(
                "AL Cost Template", cost_template_name, "formula_set"
            )
            if formula_set:
                # Dùng Formula Set có sẵn
                from formula_builder.api.variable_resolver import VariableResolver as FBVarResolver
                resolver = FBVarResolver()
                set_formulas = resolver._get_formula_set_output(formula_set)
                formulas += set_formulas
            else:
                # Fallback: build từ AL Cost Template Line (logic cũ)
                template_lines = frappe.get_all(
                    "AL Cost Template Line",
                    filters={"parent": cost_template_name},
                    fields=["line_code", "calc_formula"],
                    order_by="sort_order asc",
                )
                for line in template_lines:
                    if line.calc_formula:
                        formulas.append({
                            "name": line.line_code or f"cost_{line.sort_order}",
                            "formula": line.calc_formula,
                        })
        
        return formulas
```

---

## KẾT LUẬN

Thiết kế v17 là một nền tảng vững chắc — **85/100 điểm**. Các nguyên tắc cốt lõi đều đúng đắn và đã được chứng minh qua 7 phiên bản.

**15 điểm còn thiếu** không phải là lỗi thiết kế, mà là **cơ hội tối ưu** — tận dụng những gì formula_builder đã cung cấp thay vì tự xây dựng lại. Việc áp dụng các khuyến nghị trên sẽ:

1. **Giảm 26% code Python** (620 → 460 dòng) — ít bug hơn, dễ maintain hơn
2. **Giảm 38% code JavaScript** (680 → 420 dòng) — UI consistent với FB
3. **Tăng 140% source types** (5 → 12) — user có thể cấu hình được nhiều hơn
4. **DAG topology thay vì priority tuần tự** — hết lỗi "biến B chưa có"
5. **Giảm 2 DocType** (AL Variable Binding, AL Rule Sequence Item)

**Quan trọng nhất:** Tất cả cải tiến đều tuân thủ triết lý *"Khai báo theo thứ tự tư duy nghề. Tính theo thứ tự DAG. Mở rộng theo module không phá lõi."* — và nâng tầm triết lý *"trao quyền cho user"* lên một mức mới.

---

*Đánh giá thực hiện bởi Claude Code — 2026-06-26*
*Phạm vi: AlumGlass ERP v17.0 + formula_builder v29.1+*
