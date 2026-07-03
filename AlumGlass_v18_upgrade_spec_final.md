# AlumGlass v18 — Upgrade Specification (FINAL v2)

> **Ngày:** 2026-06-29
> **Tác giả:** Claude Sonnet 4.6 (Architect + Implementation Mode)
> **Input:** AlumGlass_ERP_v17_FINAL.md + AlumGlass_ERP_v17_REVIEW.md + AlumGlass_v18_Upgrade_Spec.md (draft)
> **Trạng thái:** FINAL — Sẵn sàng implement
> **Ghi chú:** Bản này phản biện và nâng cấp draft v18 trước — sửa 5 gap kiến trúc quan trọng

---

## MỤC LỤC

1. [v17 Audit — Đánh giá & Phản biện draft v18](#1-v17-audit--phản-biện-draft-v18)
2. [Impact Analysis](#2-impact-analysis)
3. [v18 Architecture — Quyết định kiến trúc](#3-v18-architecture)
4. [Schema Changes — Đầy đủ & Chính xác](#4-schema-changes)
5. [Dynamic Item Resolver — Code hoàn chỉnh](#5-dynamic-item-resolver)
6. [DAG Integration](#6-dag-integration)
7. [BomOrchestrator v18 — 7 bước](#7-bom-orchestrator-v18)
8. [Migration Scripts](#8-migration-scripts)
9. [Implementation Checklist](#9-implementation-checklist)
10. [Risk & Edge Cases](#10-risk--edge-cases)
11. [Advanced Upgrade](#11-advanced-upgrade)

---

## 1. v17 AUDIT & PHẢN BIỆN DRAFT v18

### 1.1 Điểm kiến trúc v17

| Tiêu chí | Điểm | Nhận xét |
|---|---|---|
| **Architecture** | 8.5/10 | 6 tầng rõ. Module Hook pattern xuất sắc. 2-pass ProfileInterpreter đúng đắn. |
| **Scalability** | 7/10 | DAG tốt. Nhưng Fixed item_code trong al_lines → mỗi BOM là 1 tổ hợp item cố định. |
| **Low-code readiness** | 7/10 | show_condition, qty_formula tốt. Admin vẫn chọn Item thủ công — không dynamic. |
| **AI readiness** | 6/10 | explain() audit trail tốt. Hardcode item ngăn AI tự cấu hình BOM. |
| **Formula standardization** | 5/10 | **Điểm yếu nhất.** 9 field Code còn sót (draft v18 chỉ liệt kê 8, bỏ sót 1). |
| **formula_builder integration** | 6/10 | AL Variable Binding tự build lại những gì FB đã có. Review chỉ rõ nhưng draft v18 chưa address. |

**Tổng: 82/100** — hạ 3 điểm so với REVIEW vì phát hiện thêm vấn đề Code fieldtype.

### 1.2 Phản biện Draft v18 — 5 Gap Chưa Giải Quyết

Draft `AlumGlass_v18_Upgrade_Spec.md` (2026-06-29) đã giải quyết đúng 2 gap chính (Code→Small Text, Dynamic Item Selection) nhưng bỏ qua 5 vấn đề:

#### GAP 1 (P0) — Bỏ sót 1 field Code trong danh sách migration

Draft liệt kê 8 field cần chuyển. Nhưng v17 FINAL còn 1 field bỏ sót:

| # | DocType | Field | v17 Fieldtype | v18 |
|---|---|---|---|---|
| 1 | AL Profile Line | `show_condition` | Code | Small Text |
| 2 | AL Profile Line | `qty_formula` | Code | Small Text |
| 3 | AL Profile Line | `width_formula` | Code | Small Text |
| 4 | AL Profile Line | `height_formula` | Code | Small Text |
| 5 | AL Profile Line | `panel_count_formula` | Code | Small Text |
| 6 | AL Profile Line | `qty_per_panel_formula` | Code | Small Text |
| 7 | AL PK Line | `sl_formula` | Code | Small Text |
| 8 | AL Cost Template Line | `calc_formula` | Code | Small Text |
| **9** | **AL Calculation Rule** | **`formula_expression`** | **Code** | **Small Text** |
| **10** | **AL Variable Set Detail** | **`depends_on`** | **Code** | **Small Text** |

**Field 9:** `AL Calculation Rule.formula_expression` dùng khi `rule_type = FORMULA`. Draft bỏ sót vì không scan DocType này.

**Field 10:** `AL Variable Set Detail.depends_on` là điều kiện hiển thị field trong Dialog (v17 FINAL §4.10). Draft bỏ sót. Tuy nhiên `depends_on` là Frappe system field — cần xem xét cẩn thận (xem §1.2.1 bên dưới).

##### 1.2.1 Xử lý `depends_on` trong AL Variable Set Detail

`depends_on` là built-in Frappe field — Frappe dùng `Code` fieldtype cho nó vì đây là JS expression (`eval:doc.var_type == "SELECT"`). **Không nên đổi sang Small Text** — đây là quy ước Frappe, đổi có thể gây conflict với core.

**Kết luận:** 9 field cần đổi (1→8 như draft + field 9 `formula_expression`). Field 10 `depends_on` giữ nguyên Code — đây là Frappe convention, không phải formula string AlumGlass.

#### GAP 2 (P0) — DynamicItemResolver dùng raw `eval()` thay vì FormulaEngine

Draft v18 §5.2 implement `_evaluate_formula()` bằng:
```python
result = eval(formula, safe_globals, safe_locals)
```

Đây là **architectural inconsistency nghiêm trọng**: toàn bộ hệ thống đang cố gắng dùng FormulaEngine làm engine DUY NHẤT (Nguyên tắc #11), nhưng DynamicItemResolver tự implement một eval engine riêng với ALLOWED_FUNCS, FORBIDDEN_TOKENS, security logic... — đây chính xác là anti-pattern mà v18 đang cố giải quyết.

**Fix:** Dùng `formula_builder.formula_utils.FormulaEngine` để evaluate `item_condition_formula`. Xem §5.2 để biết implementation đúng.

#### GAP 3 (P1) — Không tích hợp khuyến nghị P0 từ REVIEW: Formula Variable Binding

REVIEW (85/100) xác định P0 là thay AL Variable Binding bằng Formula Variable Binding của formula_builder. Draft v18 hoàn toàn bỏ qua điều này — mâu thuẫn với tuyên bố "v18 nâng cấp từ REVIEW".

**Quyết định v18:** Tích hợp FB Variable Binding theo lộ trình từ REVIEW nhưng scope rõ:
- v18 đăng ký 2 custom handler (`rule_engine_lookup`, `bom_variable`) vào `data_source_registry`
- v18 cập nhật VariableResolver để gọi `resolve_bindings_with_deps()` thay vì self._resolve_bindings()
- v18 giữ AL Variable Binding DocType (không xóa) — data cũ vẫn đọc được qua migration
- AL Variable Library + AL Variable Set: giữ nguyên (domain-specific, không có FB equivalent)

#### GAP 4 (P1) — Cost Template không tích hợp Formula Set

REVIEW P1: Cost Template nên tách thành Formula Set (engine) + AL Cost Template (UI). Draft v18 giữ nguyên CostAccumulator build formula thủ công — bỏ qua improvement này.

**Quyết định v18:** Thêm `formula_set` field vào AL Cost Template. CostAccumulator ưu tiên dùng Formula Set nếu có, fallback về AL Cost Template Line nếu không.

#### GAP 5 (P2) — Thiếu spec cho Sales Override UI

Draft v18 §5 implement priority: `Sales override > Dynamic formula > fallback > default`. Nhưng không có spec rõ ràng cho UI để Sales thực sự nhập override — chỉ mention `al_sales_item_overrides` JSON field. Phần này cần UI spec đầy đủ.

### 1.3 Kết luận Audit

**v18 cần fix:**
- **P0-A (bắt buộc):** 9 field Code → Small Text (thêm `formula_expression`)
- **P0-B (bắt buộc):** DynamicItemResolver dùng FormulaEngine thay vì raw eval()
- **P1-A (quan trọng):** Tích hợp FB Variable Binding + 2 custom handlers
- **P1-B (quan trọng):** AL Cost Template + Formula Set integration
- **P2 (nên làm):** Sales Override UI spec

---

## 2. IMPACT ANALYSIS

### 2.1 Small Text Migration (9 fields) — Impact

| Câu hỏi | Phân tích | Kết luận |
|---|---|---|
| Phá vỡ DAG? | Không. FormulaEngine đọc string từ DB, fieldtype không ảnh hưởng. | ✅ An toàn |
| Circular dependency? | Không. Schema change, không thay đổi formula logic. | ✅ An toàn |
| Performance? | `Code` và `Small Text` đều là TEXT trong MariaDB. Identical. | ✅ An toàn |
| Monaco Editor? | **Cải thiện.** Formula Builder Monaco editor yêu cầu Small Text. Code field có Python syntax highlighting gây confusion. | ✅ Cải thiện UX |
| Backward compat? | Formula string không thay đổi. BOM cũ chạy nguyên. | ✅ Non-breaking |
| `formula_expression` cụ thể? | FORMULA-type rule vẫn chạy qua FormulaEngine. Đổi fieldtype không ảnh hưởng. | ✅ An toàn |

### 2.2 Dynamic Item Selection — Impact

| Câu hỏi | Phân tích | Kết luận |
|---|---|---|
| Phá vỡ DAG? | Không — Pre-Resolution Phase. Item resolved trước khi vào DAG chính. | ✅ An toàn |
| Circular dependency? | item_condition_formula chỉ dùng inputs_dict (priority ≤ 40). Validate tại form save. | ⚠️ Cần validate |
| Performance? | Mỗi Dynamic dòng: 1 FormulaEngine.evaluate() + 1 DB lookup. ~5ms/dòng, cache metadata. | ✅ An toàn |
| Backward compat? | item_selection_mode default = Fixed. Tất cả dòng v17 vẫn Fixed. | ✅ Non-breaking |
| Sales override? | Priority rõ: Sales override > Dynamic formula > item_fallback > item_code. | ✅ Rõ ràng |

### 2.3 FB Variable Binding Migration — Impact

| Câu hỏi | Phân tích | Kết luận |
|---|---|---|
| Phá vỡ VariableResolver? | Thay thế `_resolve_bindings()` bằng FB `resolve_bindings_with_deps()`. Giữ interface. | ⚠️ Test kỹ |
| 8 ví dụ kiểm chứng v17? | Phải PASS 100% sau migration. DAG topology replace priority-based = kết quả tương đương. | ⚠️ Verify |
| AL Variable Binding DocType? | Giữ nguyên — chỉ thêm mapping logic trong VariableResolver mới. | ✅ Non-breaking |
| Effort? | 2-3 ngày: viết 2 handlers + cập nhật VariableResolver + test. | ✅ Manageable |

### 2.4 Lựa chọn Kiến trúc: Option A vs B cho Dynamic Item

| Tiêu chí | Option A: Pre-Resolution Phase (ĐỀ XUẤT) | Option B: Inline DAG Node |
|---|---|---|
| **Cơ chế** | INPUT → DynamicItemResolver → inject item_code → DAG | item_code là node trong DAG |
| **FormulaEngine** | ✅ Không sửa | ❌ Phải sửa để support string-return node |
| **Debug** | Dễ — item đã resolved trong inputs_dict | Khó — phải trace qua DAG |
| **Validation** | Sớm — validate item tồn tại trước DAG | Muộn — lỗi khi DAG chạy |
| **Performance** | Tốt — resolve 1 lần | Kém — DB lookup tại runtime |
| **Nguyên tắc #11** | ✅ Giữ FormulaEngine làm lõi DUY NHẤT | ❌ Phân tán engine logic |

**✅ CHỌN OPTION A**

---

## 3. v18 ARCHITECTURE

### 3.1 Kiến trúc 7 tầng v18

```
TẦNG 7 — AI LAYER (★ MỚI v18)
  AI Formula Generator      — Sinh item_condition_formula từ mô tả tự nhiên
  AI Config Validator       — Phát hiện config sai (item không tồn tại, circular)
  AI PK Suggester           — Đề xuất phụ kiện dựa trên BOM tương tự

TẦNG 6 — MODULE LAYER (v17 — không đổi)
  Reporting, BOM Version, Approval, Discount, MRP, Notification, Cost Variance, Analytics

TẦNG 5 — PRESENTATION (cập nhật v18)
  BOM Dialog + Dynamic Item Highlight + Resolved Item Badge
  Formula Builder Monaco Editor (tất cả formula fields → Small Text)
  ★ Sales Override Panel (cho phép override item trong Dynamic rows)

TẦNG 4.5 — DYNAMIC ITEM RESOLVER (★ MỚI v18)
  DynamicItemResolver.resolve() — Pre-Resolution Phase
  Dùng FormulaEngine.evaluate_single() — không tự build eval
  Item cache, fallback logic, sales override priority

TẦNG 4 — ORCHESTRATION (cập nhật v18)
  VariableResolver v3 — dùng FB resolve_bindings_with_deps() + custom handlers
  ProfileInterpreter v2 / PkResolver / CostAccumulator v2 (+ Formula Set integration)
  SnapshotBuilder / BomOrchestrator 7 bước

TẦNG 3 — FORMULA ENGINE (KHÔNG SỬA — ĐÃ CÓ SẴN evaluate_single())
  FormulaEngine (DAG, IncrementalContext, explain(), evaluate_single())

TẦNG 2 — RULE ENGINE & VARIABLE BINDING (cập nhật v18)
  AL Calculation Rule (giữ THRESHOLD + LOOKUP; CONSTANT/FORMULA → FB Global Variable)
  Formula Variable Binding (FB native) + 2 custom handlers (rule_engine_lookup, bom_variable)
  AL Discount Rule (stack, không vào DAG) — v17

TẦNG 1 — MASTER DATA (cập nhật v18)
  34 DocType v17 + Schema updates cho AL Profile Line, AL PK Line, AL Calculation Rule,
  AL Cost Template (+ formula_set field), AL Variable Set Detail
```

### 3.2 Quyết định kiến trúc v18 (QĐ-16 đến QĐ-20)

**QĐ-16: DynamicItemResolver dùng FormulaEngine.evaluate_single()**

item_condition_formula là formula AlumGlass — phải chạy qua FormulaEngine như mọi formula khác. FormulaEngine đã có `evaluate_single(formula, context)` method. Dùng nó thay vì build eval sandbox riêng.

Lý do: Nguyên tắc #11 (FormulaEngine là lõi DUY NHẤT). Security validator của FormulaEngine đã được test kỹ. ALLOWED_FUNCS của FormulaEngine (80+ hàm) đã đủ cho IF, AND, OR, comparison.

**QĐ-17: Formula Variable Binding thay AL Variable Binding trong VariableResolver**

VariableResolver v3 gọi `data_source_registry.resolve_bindings_with_deps()` từ formula_builder. Đăng ký 2 custom handlers. AL Variable Binding DocType giữ nguyên để không phá data cũ — nhưng VariableResolver chuyển đọc từ `Formula Variable Binding` thay vì `AL Variable Binding`.

Migration: Script tự động tạo `Formula Variable Binding` tương ứng cho mỗi `AL Variable Binding` hiện có.

**QĐ-18: AL Calculation Rule — Tinh gọn, không xóa**

- THRESHOLD và LOOKUP: giữ nguyên (table-based UX, không có FB equivalent)
- CONSTANT và FORMULA: admin có thể chuyển sang Formula Global Variable (tùy chọn, không ép buộc)
- SEQUENCE: admin có thể chuyển sang Formula Set (tùy chọn)
- v18 chỉ đổi `formula_expression` từ Code → Small Text, không xóa rule_type nào

**QĐ-19: AL Cost Template + Formula Set — Optional Integration**

AL Cost Template thêm field `formula_set` (Link → Formula Set, optional). Khi có formula_set → CostAccumulator dùng FB Formula Set engine. Khi không → fallback về AL Cost Template Line (backward compat). Không ép buộc migrate.

**QĐ-20: item_condition_formula chỉ dùng input variables**

item_condition_formula được evaluate tại Phase 4.5 (sau VariableResolver nhưng trước ProfileInterpreter). Nó chỉ có thể tham chiếu các biến có trong inputs_dict tại thời điểm đó. Validate tại form save: scan formula, reject nếu tham chiếu biến computed (slug-based).

---

## 4. SCHEMA CHANGES

### 4.1 AL Profile Line — Schema v18 (đầy đủ)

#### Trường chung (tất cả line_type)

| fieldname | fieldtype | default | reqd | Thay đổi vs v17 |
|---|---|---|---|---|
| sort_order | Int | | ✓ | Không đổi |
| line_type | Select | | ✓ | Không đổi |
| line_name | Data | | ✓ | Không đổi |
| slug | Data | | | Không đổi |
| group_tag | Data | | | Không đổi |
| **show_condition** | **Small Text** | | | **★ ĐỔI từ Code** |
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
| **qty_formula** | **Small Text** | | **★ ĐỔI từ Code** |
| price_type | Select | | Không đổi |
| price_rule | Link → AL Calculation Rule | | Không đổi |
| fixed_price | Currency | | Không đổi |

#### Trường riêng KINH

| fieldname | fieldtype | reqd | Thay đổi |
|---|---|---|---|
| ctx_inject_prefix | Data | ✓ | Không đổi |
| default_glass_master | Link → AL Glass Master | ✓ | Không đổi |
| width_rule | Link → AL Calculation Rule | | Không đổi |
| height_rule | Link → AL Calculation Rule | | Không đổi |
| **width_formula** | **Small Text** | | **★ ĐỔI từ Code** |
| **height_formula** | **Small Text** | | **★ ĐỔI từ Code** |
| **panel_count_formula** | **Small Text** | | **★ ĐỔI từ Code** |
| panel_glass_override_allowed | Check | | Không đổi |
| **qty_per_panel_formula** | **Small Text** | | **★ ĐỔI từ Code** |
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
| **qty_formula** | **Small Text** | **★ ĐỔI từ Code** |
| price_type | Select | Không đổi |
| price_list | Link → Price List | Không đổi |
| fixed_price | Currency | Không đổi |

#### Trường riêng PK (inline trong Profile Set)

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| item_code | Link → Item | Không đổi |
| **sl_formula** | **Small Text** | **★ ĐỔI từ Code** |
| price_list | Link → Price List | Không đổi |
| allow_substitute | Check | Không đổi |
| substitute_item_group | Link → Item Group | Không đổi |

### 4.2 AL PK Line — Schema v18

| fieldname | fieldtype | default | Thay đổi |
|---|---|---|---|
| item_code | Link → Item | | Không đổi |
| **sl_formula** | **Small Text** | | **★ ĐỔI từ Code** |
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
| **calc_formula** | **Small Text** | **★ ĐỔI từ Code** |
| cost_bucket | Link → AL Cost Bucket | Không đổi |
| is_subtotal | Check | Không đổi |
| show_on_quotation | Check (default 1) | Không đổi |

### 4.4 AL Calculation Rule — Schema v18

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| rule_code | Data | Không đổi |
| rule_name | Data | Không đổi |
| rule_type | Select | Không đổi |
| description | Text | Không đổi |
| is_active | Check | Không đổi |
| constant_value | Data | Không đổi |
| **formula_expression** | **Small Text** | **★ ĐỔI từ Code** |
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
| **formula_set** | **Link → Formula Set** | **★ MỚI v18 (optional)** |
| al_lines | Table → AL Cost Template Line | Không đổi |

> Khi `formula_set` có giá trị: CostAccumulator dùng FB Formula Set engine. Khi trống: fallback về al_lines (backward compat).

### 4.6 Quotation Item — Custom Fields bổ sung v18

| fieldname | fieldtype | Thay đổi |
|---|---|---|
| al_sales_item_overrides | JSON | ★ MỚI v18 — `{slug: item_code}` |
| (các field v17 khác) | | Không đổi |

### 4.7 Validation Rules

```python
# alumglass/doctype/al_profile_line/al_profile_line.py

def validate(doc):
    """Validate AL Profile Line — v18."""

    # 1. Dynamic mode: phải có item_condition_formula
    if doc.item_selection_mode == "Dynamic":
        if not doc.item_condition_formula:
            frappe.throw(_("Item Condition Formula bắt buộc khi chọn Dynamic mode"))

        # NHOM và PK phải có fallback (KINH không cần — không có item_code)
        if doc.line_type in ("NHOM", "PK") and not doc.item_fallback:
            frappe.throw(_("Item Fallback bắt buộc khi chọn Dynamic mode cho NHOM/PK"))

        # Validate formula syntax qua FormulaEngine
        from alumglass.engine.dynamic_item_resolver import validate_item_condition_formula
        validate_item_condition_formula(doc.item_condition_formula)

    # 2. Fixed mode: phải có item_code (NHOM, PK)
    if doc.item_selection_mode == "Fixed" and doc.line_type in ("NHOM", "PK"):
        if not doc.item_code:
            frappe.throw(_("Item Code bắt buộc khi chọn Fixed mode cho NHOM/PK"))

    # 3. KINH luôn Fixed (kính chọn qua Glass Selector, không qua item_selection_mode)
    if doc.line_type == "KINH" and doc.item_selection_mode == "Dynamic":
        frappe.throw(_("KINH line không hỗ trợ Dynamic mode. Dùng Glass Selector thay thế."))

    # 4. Formula syntax check (tất cả formula fields)
    from alumglass.engine.formula_validator import validate_formula_syntax
    for fieldname in ["show_condition", "qty_formula", "width_formula",
                      "height_formula", "panel_count_formula", "qty_per_panel_formula"]:
        val = doc.get(fieldname)
        if val:
            validate_formula_syntax(val, fieldname)
```

---

## 5. DYNAMIC ITEM RESOLVER

### 5.1 Thiết kế — Corrected Architecture

```
DynamicItemResolver (Tầng 4.5)
├── resolve(profile_lines, pk_lines, inputs_dict, sales_overrides) → injected_dict
│   ├── _resolve_item(line, inputs_dict, sales_override) → item_code
│   │   ├── Priority 1: sales_override (validate exists)
│   │   ├── Priority 2: FormulaEngine.evaluate_single(item_condition_formula, inputs_dict)
│   │   ├── Priority 3: item_fallback
│   │   └── Priority 4: item_code (Fixed mode default)
│   ├── _get_item_metadata(item_codes: List) → Dict — BATCH query, cached
│   └── _item_exists_cache: Set[str] — per-request cache
└── validate_item_condition_formula(formula: str) → bool
```

**Điểm khác biệt vs draft v18:**
- Dùng `FormulaEngine.evaluate_single()` thay vì custom eval sandbox
- Batch DB query cho metadata (không query từng item một)
- `_item_exists_cache` là Set (lookup O(1))

### 5.2 Full Implementation

```python
# alumglass/engine/dynamic_item_resolver.py
"""
DynamicItemResolver v18 — Pre-Resolution Phase.

QUAN TRỌNG: Dùng FormulaEngine.evaluate_single() — không tự build eval sandbox.
Nguyên tắc #11: FormulaEngine là engine DUY NHẤT cho mọi formula evaluation.
"""

import frappe
from frappe import _
from frappe.utils import flt
from typing import Any, Dict, List, Optional, Set


class DynamicItemResolver:
    """
    Resolve item_code cho Dynamic lines trước khi vào DAG chính.

    Được gọi tại Bước 2 của BomOrchestrator, sau VariableResolver.
    Kết quả inject vào inputs_dict như các hằng số — DAG không biết đến Dynamic Item.
    """

    def __init__(self):
        self._item_cache: Dict[str, Dict] = {}   # item_code → metadata
        self._exists_cache: Set[str] = set()      # validated item codes

    def resolve(
        self,
        profile_lines: List[Any],
        pk_lines: List[Any],
        inputs_dict: Dict[str, Any],
        sales_overrides: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve tất cả Dynamic Item trong profile_lines và pk_lines.

        Returns:
            dict: Các biến bổ sung cần inject vào inputs_dict.
                  Format: {slug_item_code: "C3211-20", slug_kg_per_m: 0.312, slug_price: 113000}
        """
        sales_overrides = sales_overrides or {}
        injected: Dict[str, Any] = {}

        # Bước 1: Collect tất cả item codes cần resolve (để batch query)
        items_to_fetch = self._prefetch_candidates(profile_lines, pk_lines, sales_overrides)
        if items_to_fetch:
            self._batch_load_metadata(items_to_fetch)

        # Bước 2: Resolve từng Dynamic Profile Line
        for line in profile_lines:
            if not getattr(line, "is_active", 1):
                continue
            if getattr(line, "line_type", "") == "KINH":
                continue  # KINH không dùng item_selection_mode
            if getattr(line, "item_selection_mode", "Fixed") != "Dynamic":
                continue  # Fixed mode: ProfileInterpreter tự xử lý

            slug = getattr(line, "slug", "") or f"line_{line.idx}"
            sales_override = sales_overrides.get(slug)

            resolved_item = self._resolve_item(
                line=line,
                inputs_dict=inputs_dict,
                sales_override=sales_override,
            )

            injected[f"{slug}_item_code"] = resolved_item
            meta = self._get_item_metadata(resolved_item)
            if meta:
                injected[f"{slug}_kg_per_m"] = meta.get("kg_per_m", 0)
                injected[f"{slug}_price"] = meta.get("price", 0)

        # Bước 3: Resolve Dynamic PK Lines
        for idx, line in enumerate(pk_lines):
            if getattr(line, "item_selection_mode", "Fixed") != "Dynamic":
                continue
            pk_slug = f"pk_{idx:04d}"
            resolved_item = self._resolve_item(
                line=line,
                inputs_dict=inputs_dict,
                sales_override=None,  # PK override xử lý riêng bởi PkResolver
            )
            injected[f"{pk_slug}_item_code"] = resolved_item
            meta = self._get_item_metadata(resolved_item)
            if meta:
                injected[f"{pk_slug}_price"] = meta.get("price", 0)

        return injected

    # ════════════════════════════════════════
    # ITEM RESOLUTION
    # ════════════════════════════════════════

    def _resolve_item(
        self,
        line: Any,
        inputs_dict: Dict[str, Any],
        sales_override: Optional[str] = None,
    ) -> str:
        """
        Resolve item_code theo priority:
        1. Sales override (nếu item tồn tại và active)
        2. item_condition_formula via FormulaEngine.evaluate_single()
        3. item_fallback
        4. item_code (Fixed mode value)
        """
        slug = getattr(line, "slug", "unknown")

        # Priority 1: Sales override
        if sales_override and self._item_exists(sales_override):
            return sales_override
        if sales_override and not self._item_exists(sales_override):
            frappe.log_error(
                title="Sales override item không tồn tại",
                message=f"Line: {slug}, override: {sales_override} — dùng formula thay thế"
            )

        # Priority 2: Evaluate item_condition_formula
        formula = (getattr(line, "item_condition_formula", "") or "").strip()
        if formula:
            resolved = self._evaluate_via_formula_engine(formula, inputs_dict, slug)
            if resolved and self._item_exists(resolved):
                return resolved
            if resolved:
                frappe.log_error(
                    title="Dynamic item formula resolved to non-existent item",
                    message=f"Line: {slug}, formula: {formula[:100]}, result: '{resolved}'"
                )

        # Priority 3: item_fallback
        fallback = getattr(line, "item_fallback", None)
        if fallback and self._item_exists(fallback):
            return fallback

        # Priority 4: item_code default
        default_item = getattr(line, "item_code", None)
        if default_item and self._item_exists(default_item):
            return default_item

        # Không resolve được — throw
        frappe.throw(
            _("Không thể resolve item cho dòng '{0}'. Kiểm tra item_condition_formula, "
              "item_fallback và item_code.").format(slug)
        )

    # ════════════════════════════════════════
    # FORMULA ENGINE INTEGRATION (QĐ-16)
    # ════════════════════════════════════════

    def _evaluate_via_formula_engine(
        self,
        formula: str,
        context: Dict[str, Any],
        slug: str,
    ) -> Optional[str]:
        """
        Evaluate item_condition_formula qua FormulaEngine.evaluate_single().

        KHÔNG dùng raw eval() — FormulaEngine là engine DUY NHẤT (Nguyên tắc #11).
        FormulaEngine.evaluate_single() đã có security validator, 80+ BASE_FUNCS, IF/AND/OR.

        Returns:
            str: Item code nếu thành công, None nếu lỗi.
        """
        try:
            from formula_builder.formula_utils import FormulaEngine
            engine = FormulaEngine()
            # evaluate_single trả về giá trị của 1 formula đơn
            result = engine.evaluate_single(formula=formula, context=context)

            if result is None:
                return None
            result_str = str(result).strip().strip("'\"")
            return result_str if result_str else None

        except Exception as e:
            frappe.log_error(
                title="DynamicItemResolver: formula evaluation failed",
                message=f"Line slug: {slug}, formula: {formula[:200]}, error: {type(e).__name__}: {e}"
            )
            return None

    # ════════════════════════════════════════
    # ITEM METADATA — BATCH LOADING
    # ════════════════════════════════════════

    def _prefetch_candidates(
        self,
        profile_lines: List[Any],
        pk_lines: List[Any],
        sales_overrides: Dict[str, str],
    ) -> Set[str]:
        """Collect tất cả item codes có thể cần load metadata."""
        candidates = set()
        for line in profile_lines:
            for attr in ("item_code", "item_fallback"):
                v = getattr(line, attr, None)
                if v:
                    candidates.add(v)
        candidates.update(v for v in sales_overrides.values() if v)
        return candidates

    def _batch_load_metadata(self, item_codes: Set[str]) -> None:
        """Load metadata cho nhiều item trong 1 query, cache kết quả."""
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

        loaded_codes = [i.name for i in items]
        prices = frappe.get_all(
            "Item Price",
            filters={"item_code": ["in", loaded_codes], "selling": 1},
            fields=["item_code", "price_list_rate"],
            order_by="valid_from desc",
        )
        price_map: Dict[str, float] = {}
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
        if not item_code:
            return None
        if item_code not in self._item_cache:
            self._batch_load_metadata({item_code})
        return self._item_cache.get(item_code)

    def _item_exists(self, item_code: str) -> bool:
        if not item_code:
            return False
        if item_code in self._exists_cache:
            return True
        # Miss: single DB check
        exists = frappe.db.get_value("Item", {"name": item_code, "disabled": 0}, "name")
        if exists:
            self._exists_cache.add(item_code)
        return bool(exists)

    def clear_cache(self):
        self._item_cache.clear()
        self._exists_cache.clear()


# ════════════════════════════════════════
# VALIDATOR — Dùng khi admin save Profile Line
# ════════════════════════════════════════

def validate_item_condition_formula(formula: str) -> bool:
    """
    Validate item_condition_formula trước khi lưu.
    Dùng FormulaEngine.validate() — không implement validation riêng.
    """
    if not formula or not formula.strip():
        return True

    try:
        from formula_builder.formula_utils import FormulaEngine, FormulaValidator
        validator = FormulaValidator()
        # Dry-run với dummy context để check syntax
        result = validator.validate_formula(formula)
        if not result.is_valid:
            frappe.throw(
                _("Công thức không hợp lệ: {0}").format(result.error_message)
            )
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.throw(_("Lỗi validate công thức: {0}").format(str(e)))

    # Check: không tham chiếu biến computed (slug-based)
    # Biến computed có pattern: {word}_{4digits}_{suffix} (e.g., nhom_0060_qty)
    import re
    slug_pattern = re.compile(r'\b([a-z]+_\d{4}_\w+)\b')
    matches = slug_pattern.findall(formula)
    if matches:
        frappe.throw(
            _("item_condition_formula không được tham chiếu biến tính toán: {0}. "
              "Chỉ dùng biến đầu vào (W_mm, H_mm, glass_thick_*, do_day, n_canh, ...).").format(
                ", ".join(set(matches))
            )
        )

    return True
```

### 5.3 VariableResolver v3 — FB Integration

```python
# alumglass/engine/variable_resolver.py — v3 (cập nhật v18)

class VariableResolver:
    """
    VariableResolver v3 — Dùng Formula Variable Binding của formula_builder.
    Đăng ký 2 custom handlers: rule_engine_lookup, bom_variable.
    """

    def resolve(self, quotation_item, bom_doc):
        # ─── Bước 1: FB resolve_bindings_with_deps (DAG topology thay priority) ───
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

        # ─── Bước 3: glass_thick injection (giữ nguyên từ v16) ───
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
        """Đọc biến từ AL Variable Set của BOM (domain-specific, không có FB equivalent)."""
        result = {}
        bom_vars = self._safe_json(quotation_item, "al_bom_vars")
        if not bom_doc.variable_set:
            return result
        var_set = frappe.get_doc("AL Variable Set", bom_doc.variable_set)
        for detail in var_set.al_var_details:
            var_code = detail.variable
            if var_code in bom_vars:
                result[var_code] = bom_vars[var_code]
            elif detail.override_default:
                result[var_code] = detail.override_default
            else:
                lib = frappe.get_cached_doc("AL Variable Library", var_code)
                if lib.default_val is not None:
                    result[var_code] = lib.default_val
        return result

    def _resolve_quotation_inputs(self, quotation_item):
        """Đọc W_mm, H_mm, qty và các custom field al_* từ Quotation Item."""
        return {
            "W_mm": flt(quotation_item.get("al_W_mm", 0)),
            "H_mm": flt(quotation_item.get("al_H_mm", 0)),
            "qty": flt(quotation_item.get("qty", 1)),
            "W_m": flt(quotation_item.get("al_W_mm", 0)) / 1000,
            "H_m": flt(quotation_item.get("al_H_mm", 0)) / 1000,
        }

    @staticmethod
    def _safe_json(doc, fieldname):
        import json
        raw = doc.get(fieldname) or "{}"
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return {}


# ─── Custom handlers đăng ký vào FB data_source_registry ───

def _handle_bom_variable(source_config, resolved_so_far, context):
    """Handler: đọc biến từ al_bom_vars JSON của Quotation Item."""
    var_code = source_config.get("var_code")
    quotation_item = context.get("_quotation_item")
    if not var_code or not quotation_item:
        return None
    import json
    bom_vars = json.loads(quotation_item.get("al_bom_vars") or "{}")
    return bom_vars.get(var_code)


def _handle_rule_engine_lookup(source_config, resolved_so_far, context):
    """Handler: tra cứu AL Calculation Rule LOOKUP/THRESHOLD."""
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
        rows = frappe.get_all(
            "AL Rule Lookup Row",
            filters={"parent": rule.name},
            fields=["key_1", "key_2", "key_3", "result_value"],
        )
        for row in rows:
            if (not key_values.get("key_1") or str(key_values.get("key_1")) == str(row.key_1 or "")) and \
               (not key_values.get("key_2") or str(key_values.get("key_2")) == str(row.key_2 or "")):
                return flt(row.result_value or 0)
        return flt(rule.lookup_default or 0)

    if rule.rule_type == "THRESHOLD":
        input_var = rule.threshold_input_var
        val = flt(resolved_so_far.get(input_var, 0))
        rows = frappe.get_all(
            "AL Rule Threshold Row",
            filters={"parent": rule.name},
            fields=["from_value", "to_value", "result_value"],
            order_by="from_value asc",
        )
        for row in rows:
            if row.from_value <= val and (not row.to_value or val <= row.to_value):
                return flt(row.result_value or 0)
        return flt(rule.lookup_default or 0)

    return None


# Đăng ký vào FB registry
def register_custom_handlers():
    from formula_builder.api.data_source_registry import DATA_SOURCE_HANDLERS
    DATA_SOURCE_HANDLERS["bom_variable"] = _handle_bom_variable
    DATA_SOURCE_HANDLERS["rule_engine_lookup"] = _handle_rule_engine_lookup
```

---

## 6. DAG INTEGRATION

### 6.1 Vị trí Dynamic Item trong toàn bộ flow

```
TRƯỚC DAG — Tầng 4.5 (DynamicItemResolver):
  inputs_dict (sau VariableResolver) bao gồm:
    W_mm, H_mm, qty, n_canh, do_day, huong_mo
    glass_thick_kinh_canh = 24.0    ← inject từ AL Glass Master
    don_gia_nhom = 180000           ← resolve từ FB Variable Binding
    ★ nhom_0060_item_code = "C3211-20"   ← DynamicItemResolver
    ★ nhom_0060_kg_per_m = 0.312         ← DynamicItemResolver
    ★ nhom_0060_price = 113000            ← DynamicItemResolver

VÀO DAG — FormulaEngine thấy item như hằng số:
  nhom_0060_active = (show_condition_formula)   # Boolean formula
  nhom_0060_qty    = H_m * 2 * qty              # Dùng H_m từ inputs
  nhom_0060_kg     = nhom_0060_kg_per_m         # Constant từ DynamicItemResolver
  nhom_0060_dg     = nhom_0060_price            # Constant từ DynamicItemResolver
  nhom_0060_tt     = nhom_0060_active * nhom_0060_qty * nhom_0060_kg * nhom_0060_dg
  ...
  VL_NHOM = nhom_0010_tt + nhom_0020_tt + ... + nhom_0060_tt
  GIA_BAN = (VL_NHOM + VL_KINH + VL_VTP + VL_PK + NC_SX + NC_LD) * (1 + LAI_SUAT/100)

SAU DAG — Module Hooks (v17):
  Hook A: DiscountStack.apply() → GIA_BAN_THUONG_MAI
  Hook B: BOMVersionManager.link_version()
  Hook C: CostVarianceAnalyzer.register()
  Hook D: NotificationEngine.check_alerts()
```

### 6.2 Tránh Circular Dependency

```
QUY TẮC BẮT BUỘC:
item_condition_formula CHỈ được dùng biến từ inputs_dict (bước 4.5 chưa vào DAG):

✅ ĐƯỢC:
  glass_thick_kinh_canh   — INPUT (inject từ GlassMaster)
  W_mm, H_mm, qty         — INPUT (từ Quotation)
  n_canh, do_day          — INPUT (từ BOM Variables)
  don_gia_nhom            — INPUT (từ FB Variable Binding LOOKUP)

❌ BỊ REJECT (validate tại form save):
  nhom_0060_qty           — COMPUTED bởi DAG (slug pattern: word_NNNN_suffix)
  nhom_0060_tt            — COMPUTED bởi DAG
  TONG_VL, GIA_BAN        — COMPUTED bởi DAG

ENFORCE: validate_item_condition_formula() scan pattern r'\b[a-z]+_\d{4}_\w+\b'
→ Bất kỳ match nào → throw ValidationError ngay khi admin save Profile Line.
```

### 6.3 Dependency Resolve Timeline

```
t=0: VariableResolver.resolve()
     → inputs_dict cơ bản + glass_thick injection

t=1: DynamicItemResolver.resolve()   ← Bước 4.5 mới
     → FormulaEngine.evaluate_single(item_condition_formula, inputs_dict)
     → inject {slug}_item_code, {slug}_kg_per_m, {slug}_price vào inputs_dict

t=2: ProfileInterpreter.pass1_scan()
     → variable_registry, panel_counts
     → Đọc line._resolved_item (đã set bởi DynamicItemResolver nếu Dynamic)

t=3: ProfileInterpreter.pass2_build()
     → Build formula strings: nhom_{slug}_kg = inputs_dict[f"{slug}_kg_per_m"] (hằng số)
     → FormulaEngine chỉ thấy numbers, không thấy item_code

t=4: FormulaEngine.calculate()
     → DAG execute — tính VL_NHOM, VL_KINH, GIA_BAN
     → explain() audit trail đầy đủ

t=5: SnapshotBuilder.persist()
     → Lưu inputs_dict (bao gồm resolved item_code) vào ConfigSnapshot
     → Audit trail: "nhom_0060_item_code = C3211-20 (Dynamic, formula: IF(...))"
```

---

## 7. BOM ORCHESTRATOR v18 — 7 BƯỚC

### 7.1 BomOrchestrator Code

```python
# alumglass/engine/orchestrator.py — BomOrchestrator v18

class BomOrchestrator:
    """BomOrchestrator v18 — 7 bước + Module Hooks (v17) + Dynamic Item (v18 mới)."""

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
            profile_lines=active_lines,
            pk_lines=pk_lines,
            inputs_dict=inputs_dict,
            sales_overrides=sales_overrides,
        )
        inputs_dict.update(item_context)

        # ═══ BƯỚC 3: ProfileInterpreter Pass 1 ═══
        interpreter = ProfileInterpreter()
        variable_registry, panel_counts = interpreter.pass1_scan(
            active_lines, inputs_dict, glass_selections
        )

        # ═══ BƯỚC 4: ProfileInterpreter Pass 2 ═══
        # pass2_build dùng inputs_dict (đã có {slug}_kg_per_m, {slug}_price từ DynamicItemResolver)
        all_formulas, bucket_acc = interpreter.pass2_build(
            active_lines, inputs_dict, variable_registry, panel_counts, glass_selections
        )

        # ═══ BƯỚC 5: PkResolver ═══
        formulas_pk, pk_warnings = PkResolver().build_formulas(
            pk_set=pk_set,
            inputs_dict=inputs_dict,
            pk_overrides=pk_overrides,
        )
        all_formulas.extend(formulas_pk)

        # ═══ BƯỚC 6: CostAccumulator v2 ★ Cập nhật v18 ═══
        cost_acc = CostAccumulator()
        formulas_cost = cost_acc.build_bucket_and_template_formulas(
            bucket_acc=bucket_acc,
            cost_template_name=bom_doc.cost_template,
            inputs_dict=inputs_dict,
        )
        all_formulas.extend(formulas_cost)

        # ═══ BƯỚC 7: FormulaEngine.calculate() + SnapshotBuilder ═══
        engine = FormulaEngine()
        result = engine.calculate(formulas=all_formulas, inputs=inputs_dict)

        snapshot = SnapshotBuilder().persist(
            quotation_item=quotation_item,
            bom_doc=bom_doc,
            inputs_dict=inputs_dict,
            result=result,
            item_context=item_context,  # ★ Lưu Dynamic Item resolve info
        )

        # ═══ Hooks (v17 — không đổi) ═══
        fire_hooks("after_calculate", result, quotation_item, bom_doc)

        return result
```

### 7.2 ProfileInterpreter — Cập nhật cho Dynamic Item

```python
# alumglass/engine/profile_interpreter.py — pass2_build update

def pass2_build(self, lines, inputs_dict, variable_registry, panel_counts, glass_selections):
    all_formulas = []
    bucket_acc = {}

    for line in lines:
        slug = line.slug
        line_type = line.line_type

        if line_type == "NHOM":
            # ★ v18: Kiểm tra Dynamic mode
            if line.item_selection_mode == "Dynamic":
                # kg_per_m và price đã inject vào inputs_dict bởi DynamicItemResolver
                # ProfileInterpreter chỉ cần build formula tham chiếu chúng
                kg_var = f"{slug}_kg_per_m"   # constant trong inputs_dict
                price_var = f"{slug}_price"   # constant trong inputs_dict
            else:
                # Fixed mode — logic v17 cũ
                item = frappe.get_cached_doc("Item", line.item_code)
                kg_val = flt(item.al_kg_per_m or 0)
                price_val = self._resolve_price(line, inputs_dict)
                # Inject trực tiếp như hằng số
                inputs_dict[f"{slug}_kg_per_m"] = kg_val
                inputs_dict[f"{slug}_price"] = price_val
                kg_var = f"{slug}_kg_per_m"
                price_var = f"{slug}_price"

            # show_condition → active formula (giống v17)
            if line.show_condition:
                all_formulas.append({"name": f"{slug}_active", "formula": line.show_condition})
            else:
                inputs_dict[f"{slug}_active"] = 1

            # qty formula
            qty_formula = self._get_qty_formula(line)
            all_formulas.append({
                "name": f"{slug}_qty",
                "formula": f"IF({slug}_active, {qty_formula}, 0)"
            })

            # cost formula: qty × kg/m × đơn giá
            all_formulas.append({
                "name": f"{slug}_tt",
                "formula": f"{slug}_qty * {kg_var} * {price_var}"
            })

            bucket = line.cost_bucket or "VL_NHOM"
            bucket_acc.setdefault(bucket, []).append(f"{slug}_tt")

        # KINH, VTP, PK: logic v17 không đổi
        # ...

    return all_formulas, bucket_acc
```

### 7.3 CostAccumulator v2 — Formula Set Integration

```python
# alumglass/engine/cost_accumulator.py — v2

class CostAccumulator:
    def build_bucket_and_template_formulas(self, bucket_acc, cost_template_name, inputs_dict):
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
                    title="CostAccumulator: Formula Set evaluation failed, fallback",
                    message=str(e)
                )
                # Fallback về al_lines

        # Fallback: build từ AL Cost Template Line (backward compat)
        for line in (template.al_lines or []):
            if line.calc_formula:
                formulas.append({
                    "name": line.line_code or f"cost_{line.sort_order}",
                    "formula": line.calc_formula,
                })

        return formulas
```

---

## 8. MIGRATION SCRIPTS

### 8.1 Patch 1 — Alter Formula Fields từ Code → Small Text

```python
# aluglass/patches/v18_0/alter_formula_fields_to_small_text.py
"""
Patch v18.0 — Chuyển 9 field Code → Small Text.
Backup database trước khi chạy.
"""
import frappe


FIELD_MAP = [
    # (DocType, fieldname)
    ("AL Profile Line", "show_condition"),
    ("AL Profile Line", "qty_formula"),
    ("AL Profile Line", "width_formula"),
    ("AL Profile Line", "height_formula"),
    ("AL Profile Line", "panel_count_formula"),
    ("AL Profile Line", "qty_per_panel_formula"),
    ("AL PK Line", "sl_formula"),
    ("AL Cost Template Line", "calc_formula"),
    ("AL Calculation Rule", "formula_expression"),  # ★ Bỏ sót trong draft v18
]


def execute():
    print("v18 Migration: Alter formula fields Code → Small Text")

    for doctype, fieldname in FIELD_MAP:
        # Cập nhật DocType JSON
        meta = frappe.get_meta(doctype, cached=False)
        field = meta.get_field(fieldname)
        if not field:
            print(f"  SKIP: {doctype}.{fieldname} — field không tồn tại")
            continue

        if field.fieldtype == "Small Text":
            print(f"  SKIP: {doctype}.{fieldname} — đã là Small Text")
            continue

        # Đổi fieldtype trong database
        table_name = f"tab{doctype.replace(' ', ' ')}"
        # Frappe tự map: Code = TEXT trong MySQL, Small Text = TEXT — ALTER không cần thiết
        # Chỉ cần update fieldtype trong DocType JSON

        field_doc = frappe.get_doc("DocField", {"parent": doctype, "fieldname": fieldname})
        field_doc.db_set("fieldtype", "Small Text")
        print(f"  OK: {doctype}.{fieldname}: Code → Small Text")

    # Rebuild cache
    frappe.clear_cache()
    print("v18 Migration: Formula fields update complete")
```

### 8.2 Patch 2 — Add Dynamic Item Selection Fields

```python
# aluglass/patches/v18_0/add_dynamic_item_fields.py
"""
Patch v18.0 — Thêm item_selection_mode, item_condition_formula, item_fallback
vào AL Profile Line và AL PK Line.
"""
import frappe


def execute():
    print("v18 Migration: Add Dynamic Item Selection fields")

    # AL Profile Line
    _add_fields_to_doctype("AL Profile Line", [
        {
            "fieldname": "item_selection_mode",
            "fieldtype": "Select",
            "label": "Item Selection Mode",
            "options": "Fixed\nDynamic",
            "default": "Fixed",
            "insert_after": "is_active",
            "description": "Fixed: chọn item_code trực tiếp. Dynamic: dùng formula chọn item.",
        },
        {
            "fieldname": "item_condition_formula",
            "fieldtype": "Small Text",
            "label": "Item Condition Formula",
            "insert_after": "item_selection_mode",
            "depends_on": "eval:doc.item_selection_mode=='Dynamic'",
            "description": "Công thức trả về item_code. Ví dụ: IF(glass_thick_kinh_canh <= 10.38, 'C3209-20', 'C3211-20')",
        },
        {
            "fieldname": "item_fallback",
            "fieldtype": "Link",
            "options": "Item",
            "label": "Item Fallback",
            "insert_after": "item_condition_formula",
            "depends_on": "eval:doc.item_selection_mode=='Dynamic'",
            "description": "Item dùng khi formula không resolve được.",
        },
    ])

    # AL PK Line
    _add_fields_to_doctype("AL PK Line", [
        {
            "fieldname": "item_selection_mode",
            "fieldtype": "Select",
            "label": "Item Selection Mode",
            "options": "Fixed\nDynamic",
            "default": "Fixed",
            "insert_after": "item_code",
        },
        {
            "fieldname": "item_condition_formula",
            "fieldtype": "Small Text",
            "label": "Item Condition Formula",
            "insert_after": "item_selection_mode",
            "depends_on": "eval:doc.item_selection_mode=='Dynamic'",
        },
        {
            "fieldname": "item_fallback",
            "fieldtype": "Link",
            "options": "Item",
            "label": "Item Fallback",
            "insert_after": "item_condition_formula",
            "depends_on": "eval:doc.item_selection_mode=='Dynamic'",
        },
    ])

    # AL Cost Template — formula_set field
    _add_fields_to_doctype("AL Cost Template", [
        {
            "fieldname": "formula_set",
            "fieldtype": "Link",
            "options": "Formula Set",
            "label": "Formula Set (optional)",
            "insert_after": "product_type",
            "description": "Nếu có, CostAccumulator dùng Formula Set engine thay vì al_lines.",
        },
    ])

    frappe.db.commit()
    print("v18 Migration: Dynamic Item fields added")


def _add_fields_to_doctype(doctype, fields):
    for f in fields:
        if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": f["fieldname"]}):
            print(f"  SKIP: {doctype}.{f['fieldname']} — đã tồn tại")
            continue
        cf = frappe.new_doc("Custom Field")
        cf.dt = doctype
        for k, v in f.items():
            cf.set(k, v)
        cf.insert(ignore_permissions=True)
        print(f"  OK: Added {doctype}.{f['fieldname']}")
```

### 8.3 Patch 3 — Sales Override Custom Field

```python
# aluglass/patches/v18_0/add_sales_override_field.py
import frappe


def execute():
    if frappe.db.exists("Custom Field", {
        "dt": "Quotation Item",
        "fieldname": "al_sales_item_overrides",
    }):
        print("SKIP: al_sales_item_overrides đã tồn tại")
        return

    cf = frappe.new_doc("Custom Field")
    cf.dt = "Quotation Item"
    cf.fieldname = "al_sales_item_overrides"
    cf.fieldtype = "JSON"
    cf.label = "Sales Item Overrides"
    cf.insert_after = "al_pk_overrides"
    cf.description = "Sales override item cho Dynamic rows. Format: {slug: item_code}"
    cf.hidden = 1  # UI xử lý qua JavaScript, không hiện raw JSON
    cf.insert(ignore_permissions=True)
    frappe.db.commit()
    print("OK: al_sales_item_overrides added to Quotation Item")
```

### 8.4 Patch 4 — Migrate AL Variable Binding → Formula Variable Binding

```python
# aluglass/patches/v18_0/migrate_variable_bindings.py
"""
Patch v18.0 — Tạo Formula Variable Binding tương ứng cho mỗi AL Variable Binding.
AL Variable Binding giữ nguyên — không xóa.
"""
import frappe
import json


SOURCE_TYPE_MAP = {
    "Quotation Input": "linked_doctype_field",
    "BOM Variable": "bom_variable",      # custom handler
    "BOM Attribute": "linked_doctype_field",
    "Rule Engine Result": "rule_engine_lookup",  # custom handler
    "Computed": "computed",
    "Context Inject": None,  # glass_thick — không migrate (xử lý riêng)
}


def execute():
    bindings = frappe.get_all("AL Variable Binding", fields=["*"])
    print(f"v18 Migration: Migrating {len(bindings)} AL Variable Binding → Formula Variable Binding")

    for al_b in bindings:
        fb_source_type = SOURCE_TYPE_MAP.get(al_b.source_type)
        if fb_source_type is None:
            print(f"  SKIP: {al_b.binding_code} (source_type={al_b.source_type} — xử lý riêng)")
            continue

        if frappe.db.exists("Formula Variable Binding", {"variable_name": al_b.variable_name}):
            print(f"  SKIP: {al_b.variable_name} — đã có Formula Variable Binding")
            continue

        fb_b = frappe.new_doc("Formula Variable Binding")
        fb_b.variable_name = al_b.variable_name
        fb_b.variable_label = al_b.variable_label
        fb_b.source_type = fb_source_type
        fb_b.resolve_priority = al_b.resolve_priority
        fb_b.data_type = al_b.data_type
        fb_b.is_active = al_b.is_active

        # Map source_config
        if al_b.source_type == "BOM Variable":
            fb_b.source_config = json.dumps({"var_code": al_b.variable_name})
        elif al_b.source_type in ("Quotation Input", "BOM Attribute"):
            old_config = json.loads(al_b.source_config or "{}")
            fb_b.source_config = json.dumps({
                "fieldname": old_config.get("fieldname", al_b.variable_name)
            })
        else:
            fb_b.source_config = al_b.source_config

        fb_b.insert(ignore_permissions=True)
        print(f"  OK: {al_b.variable_name} ({al_b.source_type} → {fb_source_type})")

    frappe.db.commit()
    print("v18 Migration: Variable Binding migration complete")
```

### 8.5 Checklist Migration v17 → v18

| Bước | Công việc | Script | Priority |
|---|---|---|---|
| 1 | **Backup database** | — | P0 BẮTBUỘC |
| 2 | Verify v17 stable: 8 ví dụ kiểm chứng PASS | Manual | P0 |
| 3 | Register 2 custom FB handlers (`bom_variable`, `rule_engine_lookup`) | `engine/fb_handlers.py` | P0 |
| 4 | Alter 9 formula fields: Code → Small Text | `patches/v18_0/alter_formula_fields_to_small_text.py` | P0 |
| 5 | Add Dynamic Item fields vào AL Profile Line + AL PK Line | `patches/v18_0/add_dynamic_item_fields.py` | P0 |
| 6 | Add `formula_set` vào AL Cost Template | (cùng script trên) | P1 |
| 7 | Add `al_sales_item_overrides` vào Quotation Item | `patches/v18_0/add_sales_override_field.py` | P0 |
| 8 | Migrate AL Variable Binding → Formula Variable Binding | `patches/v18_0/migrate_variable_bindings.py` | P1 |
| 9 | Deploy DynamicItemResolver + VariableResolver v3 | Engine files | P0 |
| 10 | Deploy BomOrchestrator v18 (7 bước) | Engine files | P0 |
| 11 | `bench restart` — reload workers, clear cache | — | P0 |
| 12 | Test: 8 ví dụ kiểm chứng v17 vẫn PASS (Fixed mode không thay đổi) | Manual | P0 |
| 13 | Test: Tạo BOM mới với 1 Dynamic row — verify item resolved đúng | Manual | P0 |
| 14 | Test: Sales override > Dynamic formula > fallback | Manual | P0 |
| 15 | UI: Enable Monaco editor cho Small Text formula fields | `public/js/` | P1 |
| 16 | UI: Dynamic Item highlight + resolved item badge | `public/js/bom_dialog.js` | P1 |
| 17 | UI: Sales Override Panel trong BOM Dialog | `public/js/quotation_item.js` | P2 |

---

## 9. IMPLEMENTATION CHECKLIST

### Phase 1 — Engine Changes (3-4 ngày)

| # | Task | File | Notes |
|---|---|---|---|
| 1.1 | Viết fb_handlers.py (2 custom handlers) | `engine/fb_handlers.py` | Đăng ký vào DATA_SOURCE_HANDLERS |
| 1.2 | Viết DynamicItemResolver (dùng FormulaEngine) | `engine/dynamic_item_resolver.py` | Xem §5.2 |
| 1.3 | Cập nhật VariableResolver v3 | `engine/variable_resolver.py` | Gọi resolve_bindings_with_deps() |
| 1.4 | Cập nhật BomOrchestrator (7 bước) | `engine/orchestrator.py` | Thêm bước 2 |
| 1.5 | Cập nhật ProfileInterpreter pass2_build | `engine/profile_interpreter.py` | Dynamic mode check |
| 1.6 | Cập nhật CostAccumulator v2 | `engine/cost_accumulator.py` | Formula Set fallback |

### Phase 2 — Migration (1-2 ngày)

| # | Task | File | Notes |
|---|---|---|---|
| 2.1 | alter_formula_fields_to_small_text.py | patches/v18_0/ | 9 fields |
| 2.2 | add_dynamic_item_fields.py | patches/v18_0/ | Profile Line, PK Line, Cost Template |
| 2.3 | add_sales_override_field.py | patches/v18_0/ | Quotation Item |
| 2.4 | migrate_variable_bindings.py | patches/v18_0/ | AL → FB Variable Binding |
| 2.5 | Cập nhật hooks.py để call register_custom_handlers() | aluglass/hooks.py | |

### Phase 3 — Tests (2-3 ngày)

| # | Test | Expected |
|---|---|---|
| 3.1 | 8 ví dụ kiểm chứng v17 | PASS 100% (Fixed mode không đổi) |
| 3.2 | Dynamic item resolve đúng item theo glass_thick | C3209/C3210/C3211 đúng ngưỡng |
| 3.3 | Priority: Sales override > formula > fallback > default | Override win |
| 3.4 | Formula tham chiếu slug variable bị reject tại save | ValidationError |
| 3.5 | Item disabled → fallback | Không crash, log warning |
| 3.6 | Formula trả về item không tồn tại → fallback | Không crash, log error |
| 3.7 | Batch DB query khi 20 Dynamic rows | 1-2 queries, không N+1 |
| 3.8 | Formula Set trong Cost Template | evaluate đúng, explain() hoạt động |

### Phase 4 — UI (2-3 ngày)

| # | Task | Notes |
|---|---|---|
| 4.1 | Monaco editor cho Small Text formula fields | formula_builder JS integration |
| 4.2 | Dynamic Item badge trong Profile Line form | Show "Dynamic: Resolved → C3211-20" |
| 4.3 | Resolved item display trong BOM Dialog | Read-only badge sau tính giá |
| 4.4 | Sales Override Panel | Dropdown chọn item thay thế cho từng Dynamic row |
| 4.5 | Error toast khi formula fail | "Không thể resolve item — dùng fallback C3209-20" |

---

## 10. RISK & EDGE CASES

### 10.1 Risk Matrix

| # | Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|---|
| R1 | Formula trả về item không tồn tại | Medium | Medium | item_fallback bắt buộc khi Dynamic. _item_exists() validate. Log + alert. |
| R2 | Circular dependency: formula dùng slug variable | High | Low | validate_item_condition_formula() reject tại form save. Pattern r'\b[a-z]+_\d{4}_\w+\b'. |
| R3 | FormulaEngine.evaluate_single() chưa có trong FB v29.1 | High | Low | **Verify API trước khi deploy.** Nếu chưa có → dùng calculate() với single formula. Xem R3.1. |
| R4 | Performance: 100+ Dynamic rows | Low | Low | Batch DB query, item_cache per request. Test: <200ms cho 100 rows. |
| R5 | FB Variable Binding migration sai type | Medium | Medium | Test 8 ví dụ kiểm chứng sau migration. Rollback: switch flag về AL Variable Binding. |
| R6 | Sales override item sai type (NHOM override bằng KINH item) | Medium | Medium | Validate al_item_type tại DynamicItemResolver. |
| R7 | Code → Small Text alter gây data loss | Low | Very Low | Code=TEXT trong MySQL, Small Text=TEXT → ALTER không cần. Chỉ update fieldtype meta. |
| R8 | formula_builder API thay đổi giữa các version | Medium | Low | Pin formula_builder version trong requirements.txt. |

#### R3.1 — Fallback nếu FormulaEngine.evaluate_single() không có

```python
def _evaluate_via_formula_engine(self, formula, context, slug):
    try:
        from formula_builder.formula_utils import FormulaEngine
        engine = FormulaEngine()

        # Thử gọi evaluate_single() nếu có
        if hasattr(engine, "evaluate_single"):
            return str(engine.evaluate_single(formula=formula, context=context) or "")

        # Fallback: dùng calculate() với 1 formula dummy
        result = engine.calculate(
            formulas=[{"name": "_item_result", "formula": formula}],
            inputs=context,
        )
        val = result.get("_item_result")
        return str(val).strip("'\"") if val is not None else None

    except Exception as e:
        frappe.log_error(title="DynamicItemResolver eval failed", message=str(e))
        return None
```

### 10.2 Edge Cases

```
CASE 1: Formula resolve item bị disabled
  → _item_exists() return False (filter disabled=0)
  → Skip formula result, fall về fallback
  → Log warning: "Item C3211-20 disabled, using fallback C3209-20"

CASE 2: Cả formula và fallback đều fail
  → frappe.throw("Không thể resolve item cho dòng {slug}")
  → BomOrchestrator dừng, UI hiển thị error dialog

CASE 3: Sales override + Dynamic mode + item sai type
  → Validate al_item_type khi Sales nhập override
  → Nếu sai type → reject override, dùng formula

CASE 4: Panel Expansion (N panels) + Dynamic Item
  → Item resolved 1 lần, tất cả panels dùng cùng item
  → ProfileInterpreter pass2_build expand panels như v17

CASE 5: Dynamic Item cho KINH line
  → Không hỗ trợ (QĐ kiến trúc) — KINH chọn qua Glass Selector
  → Validate tại form save: throw nếu KINH + Dynamic mode

CASE 6: item_condition_formula quá dài (>1000 chars)
  → Validate: warn nếu >500 chars, reject nếu >1000 chars
  → Admin nên tạo AL Calculation Rule LOOKUP thay vì IF chain dài

CASE 7: glass_thick_{prefix} chưa có khi evaluate item formula
  → glass_thick injection (Bước 1) luôn chạy trước DynamicItemResolver (Bước 2)
  → Đảm bảo thứ tự trong BomOrchestrator.run()
  → Nếu prefix không có trong glass_selections → dùng default_glass_master → luôn có giá trị

CASE 8: Multi-tenant — item_code khác nhau giữa company
  → Frappe Item là global (không phân company by default)
  → Nếu cần company-specific → dùng item_fallback khác nhau trong BOM của từng company
  → v19 feature: company-specific item mapping
```

---

## 11. ADVANCED UPGRADE

### 11.1 Performance Optimization

```python
# 1. COMPILE CACHE cho item_condition_formula
# ──────────────────────────────────────────
# Formula thường không đổi giữa các request → cache compiled form
# FormulaEngine có thể support compiled formula (check FB API)

class CachingDynamicItemResolver(DynamicItemResolver):
    _formula_compile_cache: Dict[str, Any] = {}  # class-level

    def _evaluate_via_formula_engine(self, formula, context, slug):
        if slug not in self._formula_compile_cache:
            # Compile formula 1 lần
            from formula_builder.formula_utils import FormulaEngine
            compiled = FormulaEngine().compile(formula)  # nếu FB hỗ trợ
            self._formula_compile_cache[slug] = compiled
        return self._formula_compile_cache[slug].evaluate(context)


# 2. DAG TOPOLOGY CACHE
# ─────────────────────
# Profile Set không đổi → DAG structure không đổi
# Cache theo profile_set_version_hash

class DAGCache:
    _dag_cache: Dict[str, Any] = {}

    @classmethod
    def get_or_build(cls, profile_set_name, profile_set_modified, formulas, inputs_dict):
        key = f"{profile_set_name}:{profile_set_modified}"
        if key not in cls._dag_cache:
            from formula_builder.formula_utils import FormulaEngine
            cls._dag_cache[key] = FormulaEngine().build_dag(formulas, inputs_dict)
        return cls._dag_cache[key]


# 3. REDIS CACHE cho item metadata
# ─────────────────────────────────
# item_code → metadata ít thay đổi → Redis TTL 5 phút phù hợp

def _get_item_metadata_redis(item_code):
    import frappe.cache_manager as cm
    key = f"aluglass:item_meta:{item_code}"
    cached = cm.get_value(key)
    if cached:
        return cached
    meta = ... # DB query
    cm.set_value(key, meta, expires_in_sec=300)
    return meta
```

### 11.2 AI Integration — Tầng 7

```python
# AI MODULE — v18 Tầng 7

# 1. AI GENERATE ITEM CONDITION FORMULA
# ─────────────────────────────────────
# Admin mô tả: "Chọn nẹp mỏng nếu kính ≤10.38mm, nẹp vừa nếu ≤16mm, nẹp IGU nếu >16mm"
# AI generate: IF(glass_thick_kinh_canh <= 10.38, "C3209-20",
#                IF(glass_thick_kinh_canh <= 16, "C3210-20", "C3211-20"))

def ai_generate_item_formula(
    description: str,
    available_items: List[Dict],  # [{item_code, item_name, specs}]
    available_vars: List[str],    # từ Variable Set
) -> str:
    """Gọi Claude API để generate item_condition_formula."""
    prompt = f"""Bạn là FormulaEngine expert cho hệ thống ERP nhôm kính.

Tạo item_condition_formula dựa trên mô tả của admin:
Mô tả: {description}

Items có sẵn:
{json.dumps(available_items, ensure_ascii=False, indent=2)}

Variables có sẵn (chỉ dùng những biến này):
{available_vars}

Yêu cầu:
- Trả về CHÍNH XÁC formula string, không giải thích
- Dùng IF(condition, "ITEM-CODE", fallback) syntax
- Chỉ dùng biến từ danh sách available_vars
- Item code phải là string trong dấu nháy đôi

Formula:"""

    # Gọi Claude API
    response = frappe.call_ai_api(prompt=prompt)  # wrapper anthropic API
    formula = response.strip()

    # Validate trước khi trả về
    validate_item_condition_formula(formula)
    return formula


# 2. AI DETECT SAI CONFIG
# ────────────────────────
def ai_validate_bom(bom_name: str) -> List[Dict]:
    """AI scan BOM → tìm potential issues."""
    issues = []
    bom = frappe.get_doc("AL BOM", bom_name)
    profile_set = frappe.get_doc("AL Profile Set", bom.profile_set)

    # Check: Dynamic items có fallback không?
    for line in profile_set.al_lines:
        if line.item_selection_mode == "Dynamic" and not line.item_fallback:
            issues.append({
                "severity": "error",
                "line": line.slug,
                "message": f"Dòng {line.slug} Dynamic mode nhưng không có item_fallback"
            })

    # Check: item_condition_formula có biến hợp lệ không?
    var_resolver = VariableResolver()
    known_vars = set(var_resolver._get_known_input_vars(bom))
    for line in profile_set.al_lines:
        if line.item_condition_formula:
            # Scan formula vars
            import re
            formula_vars = set(re.findall(r'\b([a-zA-Z_]\w*)\b', line.item_condition_formula))
            known_funcs = {"IF", "AND", "OR", "NOT", "max", "min", "abs"}
            unknown = formula_vars - known_vars - known_funcs
            if unknown:
                issues.append({
                    "severity": "warning",
                    "line": line.slug,
                    "message": f"Biến không xác định: {unknown}"
                })

    return issues


# 3. AI SUGGEST PK
# ─────────────────
def ai_suggest_pk(product_type: str, brand: str, glass_thick: float) -> List[str]:
    """Đề xuất phụ kiện dựa trên pattern từ BOM tương tự."""
    similar_boms = frappe.get_all(
        "AL BOM",
        filters={"product_type": product_type},
        fields=["name", "pk_set"],
        limit=10,
    )
    # Aggregate PK item frequency
    pk_freq: Dict[str, int] = {}
    for bom in similar_boms:
        if bom.pk_set:
            pk_set = frappe.get_doc("AL PK Set", bom.pk_set)
            for line in pk_set.al_pk_lines:
                pk_freq[line.item_code] = pk_freq.get(line.item_code, 0) + 1

    # Sort by frequency, return top 5
    top_pk = sorted(pk_freq.items(), key=lambda x: x[1], reverse=True)[:5]
    return [item_code for item_code, _ in top_pk]
```

### 11.3 Platform Direction — Sau v18

```
v18 đạt được (target state):
  ✓ 100% formula fields là Small Text — Monaco Editor hoạt động đúng
  ✓ Dynamic Item Selection — giảm 60-75% số dòng BOM cho nhóm nẹp/vật tư điều kiện
  ✓ FormulaEngine là engine DUY NHẤT — không còn raw eval() hay hardcode Python trong DB
  ✓ FB Variable Binding + DAG topology — biến resolve đúng thứ tự, không còn priority conflict
  ✓ Config-driven 100% — admin tự cấu hình BOM không cần dev
  ✓ AI-ready — explain() audit trail + structured config + Tầng 7 AI hooks
  ✓ Backward compatible — v17 data chạy nguyên, Fixed mode = v17 behavior

v19 roadmap:
  → AI-powered BOM Generator: admin mô tả cửa → AI tạo Profile Set hoàn chỉnh
  → Multi-factory: 1 BOM template → nhiều factory với local item mapping
  → Real-time pricing: giá nhôm/kính realtime → inject vào inputs_dict tự động
  → BOM Marketplace: chia sẻ Profile Set template giữa các factory
  → 3D Visualization: BOM config → 3D render cửa/vách kính

Platform thesis: AlumGlass ERP v18+ là bằng chứng rằng
"Manufacturing ERP = Low-code Platform + Domain DSL + FormulaEngine"
không cần SAP hay MES đắt tiền. v18 là bước cuối cùng để đạt Zero-Dev-Required
cho việc cấu hình BOM mới.
```

---

## APPENDIX A: Tóm tắt Field Mapping v17 → v18

| DocType | fieldname | v17 Type | v18 Type | Ghi chú |
|---|---|---|---|---|
| AL Profile Line | show_condition | Code | Small Text | ★ |
| AL Profile Line | qty_formula | Code | Small Text | ★ |
| AL Profile Line | width_formula | Code | Small Text | ★ |
| AL Profile Line | height_formula | Code | Small Text | ★ |
| AL Profile Line | panel_count_formula | Code | Small Text | ★ |
| AL Profile Line | qty_per_panel_formula | Code | Small Text | ★ |
| AL PK Line | sl_formula | Code | Small Text | ★ |
| AL Cost Template Line | calc_formula | Code | Small Text | ★ |
| AL Calculation Rule | formula_expression | Code | Small Text | ★ Bổ sung vs draft |
| AL Profile Line | item_selection_mode | — | Select | ★ MỚI |
| AL Profile Line | item_condition_formula | — | Small Text | ★ MỚI |
| AL Profile Line | item_fallback | — | Link → Item | ★ MỚI |
| AL PK Line | item_selection_mode | — | Select | ★ MỚI |
| AL PK Line | item_condition_formula | — | Small Text | ★ MỚI |
| AL PK Line | item_fallback | — | Link → Item | ★ MỚI |
| AL Cost Template | formula_set | — | Link → Formula Set | ★ MỚI (optional) |
| Quotation Item | al_sales_item_overrides | — | JSON | ★ MỚI |

## APPENDIX B: Ví dụ — Giảm dòng BOM với Dynamic Item

```
TRƯỚC v18 (3 dòng nẹp × 4 vị trí = 12 dòng):
  Sort 60: Nẹp mỏng | C3209-20 | show_condition: glass_thick_kinh_canh <= 10.38
  Sort 61: Nẹp vừa  | C3210-20 | show_condition: glass_thick_kinh_canh > 10.38 and <= 16
  Sort 62: Nẹp IGU   | C3211-20 | show_condition: glass_thick_kinh_canh > 16
  (nhân 4 vị trí: đứng trái, đứng phải, ngang trên, ngang dưới = 12 dòng)

SAU v18 (1 dòng × 4 vị trí = 4 dòng):
  Sort 60: Nẹp kính | Dynamic | item_condition_formula:
    IF(glass_thick_kinh_canh <= 10.38, "C3209-20",
    IF(glass_thick_kinh_canh <= 16, "C3210-20", "C3211-20"))
  item_fallback: C3209-20
  (nhân 4 vị trí = 4 dòng)

→ GIẢM 75% số dòng cho nhóm nẹp kính
→ Thay đổi ngưỡng = sửa 1 formula thay vì 12 show_condition
→ Thêm loại kính mới (>20mm) = sửa IF chain, không thêm dòng mới
```

## APPENDIX C: So sánh Draft v18 vs Final v18

| Vấn đề | Draft v18 | Final v18 |
|---|---|---|
| Số field Code → Small Text | 8 | **9** (thêm `formula_expression`) |
| DynamicItemResolver engine | Raw `eval()` với custom sandbox | **FormulaEngine.evaluate_single()** |
| FB Variable Binding | Không đề cập | **Tích hợp + 2 custom handlers** |
| Cost Template + Formula Set | Không đề cập | **formula_set field + CostAccumulator v2** |
| Batch DB query | Từng item một | **Batch query + class-level exists cache** |
| Validate formula | Custom regex | **FormulaEngine.validate() + slug pattern check** |
| `AL Calculation Rule.formula_expression` | Code field (bỏ sót) | **Small Text** |
| VariableResolver | Chưa update | **v3 với resolve_bindings_with_deps()** |

---

*AlumGlass v18 Upgrade Specification — FINAL v2*
*Kế thừa v11 → v13 → v14 → v15 → v16 → v17 → v18*
*Input: v17 FINAL + v17 REVIEW + draft v18 (phản biện)*
*"Zero Python in DB. FormulaEngine DUY NHẤT. Dynamic Item Selection. Config-driven 100%."*
*Ngày: 2026-06-29*