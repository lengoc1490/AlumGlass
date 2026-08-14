# HƯỚNG DẪN CẤU HÌNH FORMULA BUILDER CONTEXT — ALUMGLASS

> **Mục tiêu:** Đảm bảo mọi field công thức đều có autocomplete gợi ý đầy đủ biến.
> **Nguyên tắc:** KHÔNG sửa code formula_builder. Mọi cấu hình từ phía alumglass.

---

## MỤC LỤC

1. [Tổng quan các đường dẫn UI của Formula Builder](#1-tổng-quan-các-đường-dẫn-ui)
2. [3 cấp độ inject context variables](#2-3-cấp-độ-inject-context-variables)
3. [Cấu hình cho từng doctype](#3-cấu-hình-cho-từng-doctype)
4. [Fix show_preview: false vẫn hiện nút](#4-fix-show_preview-false)
5. [Debug & kiểm tra](#5-debug--kiểm-tra)

---

## 1. TỔNG QUAN CÁC ĐƯỜNG DẪN UI

Khi user tương tác với 1 field công thức, có 4 đường dẫn UI khác nhau:

```
                     ┌──────────────────────┐
                     │  Cấu hình trong      │
                     │  formula_setup.js    │
                     └──────────┬───────────┘
                                │
        ┌───────────────────────┼───────────────────────────┐
        ▼                       ▼                           ▼
┌───────────────┐   ┌─────────────────────┐   ┌─────────────────────────┐
│ 1. INLINE CELL│   │ 2. EXPANDED ROW     │   │ 3. DBLCLICK DIALOG      │
│ (single click)│   │ (Frappe ▸ expand)   │   │ (double click)          │
├───────────────┤   ├─────────────────────┤   ├─────────────────────────┤
│ Context từ:   │   │ Context từ:         │   │ Context từ:             │
│ _buildContext │   │ _buildContext       │   │ _loadLiveContext() API  │
│ + _afbField   │   │ + _afbFieldConfig   │   │ → Formula Variable      │
│ Config        │   │                     │   │   Binding records       │
├───────────────┤   ├─────────────────────┤   ├─────────────────────────┤
│ show_preview: │   │ show_preview:       │   │ show_toolbar: TRUE      │
│ FALSE (forced)│   │ TRUE (BUG hardcode) │   │ show_sidebar: TRUE      │
│ Không có nút  │   │ CÓ nút Chạy+Editor  │   │ CÓ full toolbar         │
└───────────────┘   └─────────────────────┘   └─────────────────────────┘

        ┌───────────────────────┼───────────────────────────┐
        ▼                       ▼                           ▼
┌───────────────┐   ┌─────────────────────┐   ┌─────────────────────────┐
│ 4. PATCHFIELD │   │ 5. PATCHCHILDFIELD  │   │ 6. FLOAT POPUP          │
│ (form mẹ)     │   │ (child table row)   │   │ (float_popup: true)     │
├───────────────┤   ├─────────────────────┤   ├─────────────────────────┤
│ Context từ:   │   │ Context từ:         │   │ Context từ:             │
│ _buildContext │   │ _buildContext       │   │ _buildContext           │
│ + _afbField   │   │ + _afbFieldConfig   │   │ + _afbFieldConfig       │
│ Config        │   │                     │   │                         │
├───────────────┤   ├─────────────────────┤   ├─────────────────────────┤
│ show_preview  │   │ show_preview        │   │ show_preview: FALSE     │
│ theo opts     │   │ theo opts           │   │ (forced)                │
└───────────────┘   └─────────────────────┘   └─────────────────────────┘
```

### Bảng tóm tắt: Cấu hình nào ảnh hưởng đến đường dẫn nào

| Cấu hình | Inline Cell | Expanded Row | DblClick Dialog | patchField | patchChildField |
|----------|:---:|:---:|:---:|:---:|:---:|
| `opts.show_toolbar` | ✅ | ✅ | ❌ | ✅ | ✅ |
| `opts.show_preview` | ❌ forced false | ❌ BUG hardcode true | ❌ | ✅ | ✅ |
| `_afbFieldConfig.global_vars` | ✅ | ✅ | ❌ | ✅ | ✅ |
| `opts.extra_completions` | ❌ | ❌ | ❌ | ✅ | ✅ |
| `Formula Variable Binding` (DB) | ❌ | ❌ | ✅ | ❌ | ❌ |
| `_afbSlugFieldMap` (id_field) | ✅ | ✅ | ✅ | — | — |

---

## 2. 3 CẤP ĐỘ INJECT CONTEXT VARIABLES

### Cấp 1: `window._afbFieldConfig.global_vars` — Toàn cục

**Ảnh hưởng:** TẤT CẢ `patchField`, `patchChildField`, `initGridField` inline editor, expanded row
**Không ảnh hưởng:** dblclick dialog

**Cách dùng:** Set trong file JS bất kỳ load sớm. VD trong `cost_template.js`:

```javascript
// cost_template.js
alumglass.CostTemplate = {
    injectContext: async function(frm) {
        const ctx = await alumglass.CostTemplate.fetchContext();
        window._afbFieldConfig = window._afbFieldConfig || {};
        window._afbFieldConfig.global_vars = ctx.variables.map(v => ({
            name: v.name,
            label: v.label || v.name,
            value: v.value,
            field_type: v.type || "Float",
            source: "global",
            doctype: v.source_type || "Config",
        }));
    },
};
```

**Khi nào dùng:** Khi cần biến dùng chung cho nhiều doctype (Cost Bucket codes, system variables, global rates...)

### Cấp 2: `opts.extra_completions` — Per-field (chỉ patchField)

**Ảnh hưởng:** Chỉ `patchField` được gọi với option này
**Không ảnh hưởng:** `initGridField`, dialog

**Cách dùng:**

```javascript
formula_builder.formula.patchField(frm, "calc_fn", {
    language: "formula-builder",
    extra_completions: [
        { name: "w", label: "Width (mm)", insert: "w", type: "var" },
        { name: "h", label: "Height (mm)", insert: "h", type: "var" },
        { name: "tlr", label: "Weight/m (kg)", insert: "tlr", type: "var" },
    ],
});
```

**Khi nào dùng:** Khi 1 field cụ thể cần biến đặc thù, không dùng chung với field khác.

### Cấp 3: `Formula Variable Binding` records — Database

**Ảnh hưởng:** CHỈ dblclick dialog (qua `get_live_context` API)
**Không ảnh hưởng:** inline editor

**Cách dùng:** Tạo record trong DocType `Formula Variable Binding`:

```
Desk → Formula Builder → Formula Variable Binding → New:

  Variable Name: VL_NHOM
  Variable Label: VL Nhôm
  Source Type: constant
  Source Config: {"value": 0}
  Applies To Doctype: AL Cost Template
  Applies To Field: calc_formula
  Is Global: ✅
  Data Type: Float
```

**Khi nào dùng:** Khi muốn dialog toàn màn hình (dblclick) có autocomplete đầy đủ.

---

## 3. CẤU HÌNH CHO TỪNG DOCTYPE

### 3.1 AL Bom Item (grid trong AL Bom Set)

**File:** `formula_setup.js` — section 1
**Fields công thức (8):** `width`, `height`, `qty`, `show_condition`, `item_condition_formula`, `rule_input_expr`, `panel_count_formula`, `qty_per_panel_formula`

**Context cần có:**

| Nhóm | Biến | Nguồn |
|------|------|-------|
| Kích thước | `W_mm`, `H_mm`, `n_panel`, `TransomHeight_mm`... | AL Variable Library |
| System vars | `OFFSET_FRAME`, `OFFSET_GLASS`, `OFFSET_FIXED`, `OFFSET_CROSSBAR` | AL Profile System → Variable Library |
| Cross-row | `items.khung_ngang_tren.width`, `items.kinh_tren.glass_thick`... | Các dòng khác trong grid |
| Row literals | `weight_per_unit`, `unit_price`, `calc_pattern`, `scrap_pct` | Engine inject qua `{slug}__{key}` |
| Glass data | `glass_thick`, `glass_type` | AL Glass Master |

**Cách cấu hình:**

```javascript
// Trong formula_setup.js — AL Bom Set section
frappe.ui.form.on("AL Bom Set", {
    refresh(frm) {
        // 1. Inject global context cho Bom Items
        alumglass.BomSetContext?.inject(frm);

        // 2. initGridField cho từng cột formula
        const item_grid_fields = ["width", "height", "qty", "show_condition",
                                  "item_condition_formula", "rule_input_expr"];
        item_grid_fields.forEach(fieldname => {
            formula_builder.formula.initGridField(frm, "items", fieldname, {
                language: "formula-builder",
                height: "70px",
                show_toolbar: false,
                show_preview: false,
                id_field: "slug",  // ← dùng slug cho cross-row ref
            });
        });
    },
});
```

**Tạo file riêng `bom_set_context.js`:**

```javascript
// alumglass/public/js/bom_set_context.js
// Inject AL Variable Library + Variable Set context cho AL Bom Set
frappe.provide("alumglass");

alumglass.BomSetContext = {
    _cache: null,

    fetchContext: async function(bom_set_code) {
        if (alumglass.BomSetContext._cache) return alumglass.BomSetContext._cache;
        try {
            const r = await frappe.call({
                method: "alumglass.api.get_cost_template_context",
            });
            if (r.message) {
                alumglass.BomSetContext._cache = r.message;
                return r.message;
            }
        } catch(e) { console.warn("[BomSetContext]", e); }
        return { variables: [] };
    },

    inject: async function(frm) {
        const ctx = await alumglass.BomSetContext.fetchContext();
        window._afbFieldConfig = window._afbFieldConfig || {};
        window._afbFieldConfig.global_vars = [
            // Cost Bucket codes cho reference
            ...ctx.variables.filter(v => v.source === "bucket").map(v => ({
                name: v.name, label: v.label || v.name,
                value: v.value, source: "global", doctype: "Cost Bucket",
            })),
            // System variables
            ...ctx.variables.filter(v => v.source === "system").map(v => ({
                name: v.name, label: v.label || v.name,
                value: v.value, source: "global", doctype: "Variable Library",
            })),
            // Common vars
            ...ctx.variables.filter(v => v.source === "bom" || v.source === "global").map(v => ({
                name: v.name, label: v.label || v.name,
                value: v.value, source: "global", doctype: v.source_type || "Common",
            })),
        ];
    },
};
```

### 3.2 AL Cost Template Item (grid trong AL Cost Template)

**File:** `cost_template.js` + `formula_setup.js` — section 2
**Field công thức (1):** `calc_formula`

**Context cần có:**

| Nhóm | Biến ví dụ | Nguồn |
|------|-----------|-------|
| Cost Buckets | `VL_NHOM`, `VL_KINH`, `TONG_VL`, `GIA_VAT`... | AL Cost Bucket |
| System vars | `NC_SX_PCT`, `NC_LD_PCT`, `VAT_RATE`, `PROFIT_MARGIN`... | AL Variable Library |
| Global vars | `OH_VC_PCT`, `OH_QLY_PCT`... | Formula Global Variable |
| Dimensions | `W_mm`, `H_mm`, `TONG_M2` | Common |

**Cách cấu hình:** ĐÃ TRIỂN KHAI (xem `cost_template.js` → `injectContext()`)

**Cách dùng nâng cao — tạo Formula Variable Binding cho dialog:**

```python
# Trong seed_demo_data.py hoặc script cài đặt
def create_cost_template_bindings():
    bindings = [
        ("VL_NHOM", "VL Nhôm", "constant", '{"value": 0}', "AL Cost Template", "calc_formula"),
        ("VL_KINH", "VL Kính", "constant", '{"value": 0}', "AL Cost Template", "calc_formula"),
        ("TONG_VL", "Tổng VL", "formula", '{"formula": "VL_NHOM+VL_KINH+VL_VTP+VL_PK"}', "AL Cost Template", "calc_formula"),
        # ... thêm tất cả bucket codes
    ]
    for var_name, label, src_type, src_cfg, dt, field in bindings:
        if not frappe.db.exists("Formula Variable Binding", {"variable_name": var_name, "applies_to_doctype": dt}):
            frappe.get_doc({
                "doctype": "Formula Variable Binding",
                "variable_name": var_name,
                "variable_label": label,
                "source_type": src_type,
                "source_config": src_cfg,
                "applies_to_doctype": dt,
                "applies_to_field": field,
                "is_global": 1,
                "data_type": "Float",
            }).insert()
```

### 3.3 AL Quantity Calc Method (form mẹ)

**File:** `formula_setup.js` — section 4
**Field công thức (1):** `calc_fn`

**Context cần có:** `w`, `h`, `tlr`, `**kw`

```javascript
frappe.ui.form.on("AL Quantity Calc Method", {
    refresh(frm) {
        if (frm.fields_dict["calc_fn"]) {
            formula_builder.formula.patchField(frm, "calc_fn", {
                language: "formula-builder",
                height: "80px",
                show_toolbar: false,
                show_preview: false,
                // ★ Inject biến đặc thù cho calc_fn
                extra_completions: [
                    { name: "w", label: "Width (mm)", insert: "w",
                      doc: "Chiều rộng tính bằng mm", type: "var" },
                    { name: "h", label: "Height (mm)", insert: "h",
                      doc: "Chiều cao tính bằng mm", type: "var" },
                    { name: "tlr", label: "Weight per meter (kg/m)", insert: "tlr",
                      doc: "Trọng lượng riêng (kg/m) từ Item ERPNext", type: "var" },
                    { name: "kw", label: "**kwargs (extra vars)", insert: "kw.get('",
                      doc: "Truy cập biến mở rộng: kw.get('thickness',0)", type: "var" },
                ],
            });
        }
    },
});
```

### 3.4 AL Alert Config (form mẹ)

**File:** `formula_setup.js` — section 3
**Field công thức (1):** `trigger_condition`

**Context cần có:** Các field của doctype được alert, system events.

```javascript
frappe.ui.form.on("AL Alert Config", {
    refresh(frm) {
        if (frm.fields_dict["trigger_condition"]) {
            formula_builder.formula.patchField(frm, "trigger_condition", {
                language: "formula-builder",
                height: "100px",
                show_toolbar: false,
                show_preview: false,
            });
        }
    },
});
```

### 3.5 AL Accessory Item (grid trong AL Bom Set)

**Field công thức (1):** `qty_formula`

Cùng grid với AL Bom Item, đã được config trong `formula_setup.js` section 1. Thêm fieldname vào list nếu cần:

```javascript
const accessory_grid_fields = ["qty_formula"];
accessory_grid_fields.forEach(fieldname => {
    formula_builder.formula.initGridField(frm, "accessory_items", fieldname, {
        language: "formula-builder",
        height: "70px",
        show_toolbar: false,
        show_preview: false,
        id_field: "slug",
    });
});
```

### 3.6 Formula Global Variable (FB doctype)

**File:** `formula_setup.js` — section 5
**Field công thức (1):** `formula_expr`

```javascript
frappe.ui.form.on("Formula Global Variable", {
    refresh(frm) {
        if (frm.fields_dict["formula_expr"]) {
            formula_builder.formula.patchField(frm, "formula_expr", {
                language: "formula-builder",
                height: "80px",
                show_toolbar: false,
                show_preview: false,
            });
        }
    },
});
```

---

## 4. FIX `show_preview: false` — VẪN HIỆN NÚT

### Vấn đề

`show_preview: false` chỉ hoạt động trên:
- ✅ `patchField` (form mẹ)
- ✅ `initGridField` inline cell (single click)

Không hoạt động trên:
- ❌ **Expanded row** — `formula_builder_field.js:1642` hardcode `show_preview: true`
- ❌ **DblClick dialog** — `openDialog()` default `show_toolbar: true`

### Workaround CSS

Tạo file `alumglass/public/css/formula_fix.css`:

```css
/* Ẩn nút "Chạy" + "⬡ Editor" trong expanded row của grid */
.grid-row-open .afb-fp-preview {
    display: none !important;
}

/* Ẩn toolbar trong dialog nếu muốn (chỉ giữ editor + panel) */
/* Cẩn thận: ảnh hưởng đến TẤT CẢ dialog */
/* .afb-dialog .afb-toolbar { display: none !important; } */
```

Đăng ký CSS trong `hooks.py`:

```python
app_include_css = [
    "/assets/alumglass/css/formula_fix.css?v=1.0.0",
]
```

---

## 5. DEBUG & KIỂM TRA

### 5.1 Kiểm tra context variables đã được inject

Mở Console (F12) trên trình duyệt:

```javascript
// Kiểm tra _afbFieldConfig
console.log(window._afbFieldConfig);

// Kiểm tra global vars
console.table(window._afbFieldConfig?.global_vars || []);

// Kiểm tra inline editor context (mở 1 cell rồi chạy)
const editor = Object.values(window._afbPatchedEditors || {})[0];
console.log(editor?.getValue?.());
```

### 5.2 Kiểm tra API context

```bash
bench --site <site> console
>>> from alumglass.api import get_cost_template_context
>>> ctx = get_cost_template_context()
>>> print(f"Variables: {len(ctx['variables'])}")
>>> for v in ctx['variables']:
...     print(f"  {v['name']:30s} | {v['source']:10s} | {v.get('label','')}")
```

### 5.3 Kiểm tra Formula Variable Binding

```bash
bench --site <site> console
>>> import frappe
>>> bindings = frappe.get_all("Formula Variable Binding",
...     filters={"applies_to_doctype": "AL Cost Template"},
...     fields=["variable_name", "source_type"])
>>> for b in bindings:
...     print(f"  {b['variable_name']} ({b['source_type']})")
```

### 5.4 Checklist cho mỗi doctype

| # | Kiểm tra | AL Bom Item | AL Cost Template | AL Qty Calc | AL Alert | AL Accessory |
|---|----------|:---:|:---:|:---:|:---:|:---:|
| 1 | `initGridField`/`patchField` đã gọi | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| 2 | `show_preview: false` đã set | ✅ | ✅ | ✅ | ✅ | — |
| 3 | `_afbFieldConfig.global_vars` có dữ liệu | ⚠️ | ✅ | — | — | — |
| 4 | `extra_completions` nếu cần biến đặc thù | — | — | ✅ | — | — |
| 5 | `Formula Variable Binding` records (dialog) | — | ⚠️ | — | — | — |
| 6 | CSS hide expanded row buttons | ⚠️ | ⚠️ | — | — | — |
| 7 | Test: gõ 1 ký tự → có autocomplete? | ⚠️ | ⚠️ | ✅ | ✅ | — |

> ✅ = Done | ⚠️ = Cần làm thêm | — = Không áp dụng

---

## PHỤ LỤC: Cấu trúc file JS khuyến nghị

```
alumglass/public/js/
├── formula_setup.js          ← File CHÍNH: gọi initGridField/patchField
├── cost_template.js          ← Context injector cho Cost Template
├── bom_set_context.js        ← [CẦN TẠO] Context injector cho Bom Set
├── bom_dialog.js             ← Dialog kết quả tính BOM
├── quotation_item_dialog.js  ← Dialog tham số BOM
├── formula_fix.css           ← [CẦN TẠO] CSS fix expanded row buttons
└── doctype/overrides/
    ├── quotation.js           ← Nút Tham số BOM, Tính giá
    └── sales_order.js         ← FB integration cho Sales Order
```

Mỗi file JS của 1 doctype nên có pattern:

```javascript
// 1. Provide namespace
frappe.provide("alumglass");

// 2. Define context injector (nếu cần)
alumglass.MyDoctype = {
    _cache: null,
    fetchContext: async function() { /* gọi API */ },
    inject: async function(frm) { /* set _afbFieldConfig.global_vars */ },
};

// 3. Form events
frappe.ui.form.on("My Doctype", {
    refresh(frm) {
        alumglass.MyDoctype.inject(frm);  // inject context
        // ... initGridField/patchField calls ...
    },
});
```
