# HƯỚNG DẪN TOÀN DIỆN: FORMULA BUILDER TRONG ALUMGLASS

> **Từ A-Z: Cấu hình, Autocomplete, Nguồn biến động, Cross-row, Ẩn/Hiện, Debug**

---

## MỤC LỤC

1. [Kiến trúc — Cách hoạt động](#1-kiến-trúc--cách-hoạt-động)
2. [Bắt đầu — Setup cơ bản](#2-bắt-đầu--setup-cơ-bản)
3. [Nguồn biến — Data-driven, zero hardcode](#3-nguồn-biến--data-driven-zero-hardcode)
4. [Ví dụ A-Z](#4-ví-dụ-a-z)
5. [Cấu hình giao diện — Ẩn/Hiện](#5-cấu-hình-giao-diện--ẩnhiện)
6. [Cross-row Reference](#6-cross-row-reference)
7. [Tooltip & Hover](#7-tooltip--hover)
8. [Debug & Troubleshooting](#8-debug--troubleshooting)

---

## 1. KIẾN TRÚC — CÁCH HOẠT ĐỘNG

```
┌──────────────────────────────────────────────────────────────────┐
│  NGƯỜI DÙNG THÊM BIẾN MỚI (QUA UI, KHÔNG CODE)                   │
│                                                                  │
│  AL Cost Bucket → record mới → tự động có trong autocomplete     │
│  AL Variable Library → record mới → tự động có                   │
│  Formula Global Variable → record mới → tự động có               │
│  Formula Variable Binding → record mới → tự động có              │
│  AL Slug Library → record mới → tự động có cross-row ref         │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  API: alumglass.api.get_formula_context(doctype)                 │
│  ★ Đọc TẤT CẢ các bảng trên, trả về variables + references       │
│  ★ 0 hardcode — mọi biến đến từ DB                               │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  JS: alumglass.FormulaContext.fetch(doctype)                     │
│  ★ Gọi API 1 lần khi form load, cache 5 phút                     │
│  ★ Monkey-patch _ContextBuilder.build() → inject vào liveCtx     │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  MONACO EDITOR                                                   │
│  ★ Autocomplete: gợi ý biến khi gõ                               │
│  ★ Hover tooltip: thông tin biến khi rê chuột                    │
│  ★ Cross-row: items.khung_tren.width                             │
└──────────────────────────────────────────────────────────────────┘
```

### Các file liên quan

| File | Vai trò |
|------|---------|
| `api/__init__.py::get_formula_context()` | API Python — đọc tất cả nguồn biến từ DB |
| `formula_setup.js` | JS — cache context + monkey-patch + default config |
| `cost_template.js` | JS — per-doctype: validate + preview |
| `HUONG_DAN_FORMULA.md` | Tài liệu này |

---

## 2. BẮT ĐẦU — SETUP CƠ BẢN

### 2.1 Thêm field công thức cho 1 doctype

**Bước 1:** Trong doctype JSON, thêm field kiểu `Small Text`:

```json
{
    "fieldname": "calc_formula",
    "fieldtype": "Small Text",
    "label": "Công thức"
}
```

**Bước 2:** Trong JS (formula_setup.js hoặc file riêng), gọi `initGridField` hoặc `patchField`:

```javascript
// Cho child table grid
frappe.ui.form.on("My Doctype", {
    refresh(frm) {
        // Pre-fetch context từ DB
        alumglass.FormulaContext.fetch("My Doctype");

        // Setup field công thức
        formula_builder.formula.initGridField(frm, "items", "my_formula",
            ALUMGLASS_OPTS({ height: "70px" }));
    },
});
```

**Bước 3:** `bench build` → Done.

### 2.2 `ALUMGLASS_OPTS()` helper

```javascript
// Mặc định toàn cục
var ALUMGLASS_FORMULA_DEFAULTS = {
    show_toolbar: false,   // Ẩn toolbar
    show_preview: false,   // Ẩn nút Chạy + Editor
};

// Helper: merge defaults với override
function ALUMGLASS_OPTS(overrides) {
    return Object.assign({}, ALUMGLASS_FORMULA_DEFAULTS, overrides || {});
}

// Dùng:
ALUMGLASS_OPTS({ height: "80px", float_popup: true })
// → { show_toolbar: false, show_preview: false, height: "80px", float_popup: true }
```

---

## 3. NGUỒN BIẾN — DATA-DRIVEN, ZERO HARDCODE

### 3.1 Nguyên tắc

**KHÔNG hardcode biến trong JS.** Mọi biến đến từ DB. Muốn thêm biến mới → thêm record vào bảng tương ứng qua UI.

API `get_formula_context(doctype)` tự động đọc **8 nguồn** sau:

| # | Nguồn | Bảng DB | Cách thêm biến mới |
|---|-------|---------|-------------------|
| 1 | **Cost Bucket codes** | `AL Cost Bucket` | Thêm record Cost Bucket mới |
| 2 | **System Variables** | `AL Variable Library` (is_system=1) | Thêm record Variable Library, check `is_system` |
| 3 | **User Variables** | `AL Variable Library` (is_system=0) | Thêm record Variable Library |
| 4 | **Global Constants** | `Formula Global Variable` | Thêm record Formula Global Variable |
| 5 | **Row Literals** | (fixed set) | Engine tự inject per-row |
| 6 | **Common BOM Vars** | (fixed set) | W_mm, H_mm, n_panel... |
| 7 | **Formula Bindings** | `Formula Variable Binding` | Thêm record Binding, set `applies_to_doctype` |
| 8 | **Slug Library** | `AL Slug Library` | Thêm record Slug → tự động có cross-row ref |

### 3.2 Cách thêm biến mới (người dùng nghiệp vụ)

**Ví dụ 1: Thêm Cost Bucket mới `VL_THEP`**

```
Desk → AL Bom Engine → AL Cost Bucket → New:
  Bucket Code: VL_THEP
  Bucket Name: VL Thép
  Bucket Role: LEAF
  Parent Bucket: TONG_VL
  → Save

→ Tự động có trong autocomplete của mọi doctype. Không cần code.
```

**Ví dụ 2: Thêm System Variable `HE_SO_MUA`**

```
Desk → AL Master Data → AL Variable Library → New:
  Var Name: HE_SO_MUA
  Var Label: Hệ số mùa vụ
  Var Type: Float
  Default Value: 1.0
  Is System: ✅
  → Save

→ Tự động có trong autocomplete. Không cần code.
```

**Ví dụ 3: Thêm Formula Variable Binding cho dialog dblclick**

```
Desk → Formula Builder → Formula Variable Binding → New:
  Variable Name: CHIET_KHAU
  Variable Label: % Chiết khấu
  Source Type: constant
  Source Config: {"value": 0.05}
  Applies To Doctype: AL Cost Template
  Is Global: ✅
  Data Type: Float
  → Save

→ Có trong autocomplete VÀ sidebar Global tab của dialog dblclick.
```

**Ví dụ 4: Thêm Slug cho cross-row reference**

```
Desk → AL Master Data → AL Slug Library → New:
  Slug: thanh_chong_gio
  Label: Thanh chống gió
  Category: NHOM
  Group Tag: KHUNG
  → Save

→ Khi gõ items. → autocomplete gợi ý thanh_chong_gio
→ Khi gõ items.thanh_chong_gio. → gợi ý width, height, qty...
```

### 3.3 Phân loại biến trong autocomplete

Khi gõ trong editor, biến được nhóm theo `group`:

| Group | Biến ví dụ | Màu sắc |
|-------|-----------|---------|
| **Cost Bucket** | VL_NHOM, TONG_VL, GIA_VAT | 📊 Xanh dương |
| **System Variables** | OFFSET_FRAME, NC_SX_PCT | ⚙️ Tím |
| **User Variables** | aluminum_color, installation_height_m | 📄 Xanh lá |
| **Formula Global Variables** | VAT_RATE, PROFIT_MARGIN | 🌍 Cam |
| **BOM Input Variables** | W_mm, H_mm, n_panel | 📐 Đỏ |
| **Row Literals** | weight_per_unit, unit_price | 📋 Xám |

### 3.4 Lọc biến theo doctype (nâng cao)

Mặc định, TẤT CẢ biến từ 8 nguồn đều có sẵn cho mọi doctype. Nếu muốn giới hạn:

**Cách 1: Dùng Formula Variable Binding với `applies_to_doctype`**

Chỉ những binding có `applies_to_doctype = "AL Cost Template"` mới hiển thị cho doctype đó.

**Cách 2: Tạo script JS per-doctype bổ sung context**

```javascript
// file: my_doctype.js
frappe.ui.form.on("My Doctype", {
    refresh(frm) {
        alumglass.FormulaContext.fetch("My Doctype").then(function(ctx) {
            // Lọc chỉ giữ Cost Bucket + System vars
            ctx.variables = ctx.variables.filter(function(v) {
                return v.source_type === "cost_bucket" || v.source_type === "variable_library";
            });
            alumglass.FormulaContext._cache["My Doctype"] = { data: ctx, ts: Date.now() };
        });
    },
});
```

---

## 4. VÍ DỤ A-Z

### Ví dụ 1: Cost Template — Công thức giá thành

**Mục tiêu:** Người dùng nhập công thức `calc_formula = VL_NHOM + VL_KINH + VL_VTP + VL_PK`

**Setup:**
```javascript
// formula_setup.js — đã setup sẵn
frappe.ui.form.on("AL Cost Template", {
    refresh(frm) {
        alumglass.FormulaContext.fetch("AL Cost Template");
        formula_builder.formula.initGridField(frm, "items", "calc_formula",
            ALUMGLASS_OPTS({ height: "80px", float_popup: true,
                             float_width: "600px", float_height: "150px" }));
    },
});
```

**Trải nghiệm người dùng:**
1. Mở AL Cost Template → click vào cell `calc_formula`
2. Gõ `VL_` → autocomplete: `VL_NHOM`, `VL_KINH`, `VL_VTP`, `VL_PK`
3. Gõ `TONG_` → autocomplete: `TONG_VL`, `TONG_NC`, `TONG_OH`
4. Gõ `GIA_` → autocomplete: `GIA_THANH`, `GIA_BAN`, `GIA_VAT`
5. Gõ `NC_SX_PCT` → gợi ý system variable
6. Rê chuột vào `VL_NHOM` → tooltip: "VL_NHOM — VL Nhôm | Float | Cost Bucket"
7. Công thức hoàn chỉnh: `VL_NHOM + VL_KINH + VL_VTP + VL_PK`

### Ví dụ 2: Bom Item — Công thức kích thước

**Mục tiêu:** `width = W_mm - 2 * OFFSET_FRAME`

**Setup:**
```javascript
frappe.ui.form.on("AL Bom Set", {
    refresh(frm) {
        alumglass.FormulaContext.fetch("AL Bom Set");
        ["width", "height", "qty"].forEach(function(fn) {
            formula_builder.formula.initGridField(frm, "items", fn,
                ALUMGLASS_OPTS({ height: "70px", id_field: "slug" }));
        });
    },
});
```

**Trải nghiệm:**
1. Mở AL Bom Set → click cell `width` dòng `khung_ngang_tren`
2. Gõ `W_` → autocomplete: `W_mm`
3. Gõ `OFFSET_` → autocomplete: `OFFSET_FRAME`, `OFFSET_GLASS`, `OFFSET_FIXED`
4. Gõ `items.` → autocomplete gợi ý tất cả slug: `khung_ngang_tren`, `kinh_tren`...
5. Gõ `items.kinh_tren.glass_thick` → tham chiếu độ dày kính của dòng khác
6. Rê chuột vào `items.kinh_tren.glass_thick` → tooltip: giá trị, kiểu, vị trí row

### Ví dụ 3: Quantity Calc Method — Lambda function

**Mục tiêu:** `calc_fn = lambda w, h, tlr, **kw: (w/1000) * tlr`

**Setup:**
```javascript
frappe.ui.form.on("AL Quantity Calc Method", {
    refresh(frm) {
        alumglass.FormulaContext.fetch("AL Quantity Calc Method");
        if (frm.fields_dict["calc_fn"]) {
            formula_builder.formula.patchField(frm, "calc_fn",
                ALUMGLASS_OPTS({ height: "80px" }));
        }
    },
});
```

### Ví dụ 4: Custom doctype — File JS riêng

**Mục tiêu:** Tạo doctype mới `AL Steel Pricing` với field `price_formula`

**Bước 1:** Tạo file `alumglass/public/js/steel_pricing.js`:

```javascript
frappe.provide("alumglass");

alumglass.SteelPricing = {
    validateFormula: function(formula) {
        if (!formula || !formula.trim()) return { valid: false, message: "Empty" };
        var open = (formula.match(/\(/g) || []).length;
        var close = (formula.match(/\)/g) || []).length;
        return open === close ? { valid: true } : { valid: false, message: "Unbalanced ()" };
    },
};

frappe.ui.form.on("AL Steel Pricing", {
    refresh(frm) {
        // 1. Load context từ DB
        alumglass.FormulaContext.fetch("AL Steel Pricing");

        // 2. Grid formula field — popup nổi
        formula_builder.formula.initGridField(frm, "items", "price_formula",
            ALUMGLASS_OPTS({ height: "80px", float_popup: true,
                             float_width: "500px", float_height: "160px" }));

        // 3. Parent form — bật preview để test
        if (frm.fields_dict["overhead_formula"]) {
            formula_builder.formula.patchField(frm, "overhead_formula",
                ALUMGLASS_OPTS({ height: "100px", show_preview: true }));
        }
    },

    validate(frm) {
        if (frm.doc.items) {
            frm.doc.items.forEach(function(row) {
                var result = alumglass.SteelPricing.validateFormula(row.price_formula);
                if (!result.valid) {
                    frappe.msgprint("Lỗi dòng " + row.idx + ": " + result.message);
                }
            });
        }
    },
});
```

**Bước 2:** Đăng ký trong `hooks.py`:

```python
app_include_js = [
    "/assets/alumglass/js/formula_setup.js?v=1.0.9",
    "/assets/alumglass/js/steel_pricing.js?v=1.0.0",   # ← thêm
    ...
]
```

**Bước 3:** `bench build`

### Ví dụ 5: BOM Dialog — Tính giá từ Quotation

```javascript
// quotation_item_dialog.js — dialog nhập tham số BOM
alumglass.quotation.ItemParamDialog = class ItemParamDialog {
    async _load_variable_set() {
        // Gọi API lấy Variable Set của BOM
        const r = await frappe.call({
            method: "alumglass.api.get_variable_set_for_bom",
            args: { bom_code: this.child_doc.al_bom },
        });
        return r.message?.variables || [];
    }

    _build_dynamic_fields(vars) {
        // Sinh form fields ĐỘNG từ Variable Set items
        // Không hardcode field nào — mọi thứ từ DB
        const fields = [];
        vars.filter(v => !v.is_system).forEach(v => {
            fields.push(this._var_to_field(v, existing[v.var_name]));
        });
        return fields;
    }
};
```

### Ví dụ 6: Thêm nguồn biến hoàn toàn mới từ 1 bảng khác

**Yêu cầu:** Lấy danh sách Supplier làm biến cho công thức mua hàng.

```python
# Trong api/__init__.py — thêm vào get_formula_context()
# Section: Supplier codes
if doctype in ("AL Buying", "AL Material Plan"):
    suppliers = frappe.get_all("Supplier",
                               fields=["name", "supplier_name"],
                               order_by="name")
    for s in suppliers:
        variables.append({
            "name": f"SUPPLIER_{s['name'].replace(' ', '_').upper()}",
            "label": f"NCC: {s.get('supplier_name') or s['name']}",
            "value": None,
            "type": "Data",
            "source": "local",
            "source_type": "supplier",
            "group": "Suppliers",
            "description": f"Supplier: {s['name']}",
        })
```

→ Không cần sửa JS. Biến mới tự động có trong autocomplete cho `AL Buying` và `AL Material Plan`.

---

## 5. CẤU HÌNH GIAO DIỆN — ẨN/HIỆN

### 5.1 Các option

| Option | Kiểu | Mặc định | Mô tả |
|--------|------|:---:|-------|
| `show_toolbar` | Boolean | false | Toolbar (chỉ có nút Copy) |
| `show_preview` | Boolean | false | Preview bar (▶ kết quả + nút Chạy + Editor) |
| `float_popup` | Boolean | false | Cell mở popup nổi thay vì inline |
| `float_width` | String | "480px" | Rộng popup |
| `float_height` | String | "160px" | Cao popup |
| `id_field` | String | null | Field slug cho cross-row |
| `height` | String | "70px" | Chiều cao editor |

### 5.2 Kịch bản

```javascript
// A: Editor thuần, không nút bấm (MẶC ĐỊNH)
ALUMGLASS_OPTS({ height: "70px" })

// B: Có nút Chạy + kết quả preview (cho field cần test)
ALUMGLASS_OPTS({ height: "80px", show_preview: true })

// C: Popup nổi to (cho công thức dài)
ALUMGLASS_OPTS({ height: "80px", float_popup: true, float_width: "600px" })

// D: Đầy đủ toolbar + preview (cho admin)
ALUMGLASS_OPTS({ height: "100px", show_toolbar: true, show_preview: true })

// E: Grid với cross-row reference
ALUMGLASS_OPTS({ height: "70px", id_field: "slug" })
```

### 5.3 Thay đổi mặc định toàn cục

Sửa `ALUMGLASS_FORMULA_DEFAULTS` trong `formula_setup.js`:

```javascript
var ALUMGLASS_FORMULA_DEFAULTS = {
    language    : "formula-builder",
    show_toolbar: true,      // ← đổi thành true → tất cả field có toolbar
    show_preview: true,      // ← đổi thành true → tất cả field có nút Chạy
};
```

---

## 6. CROSS-ROW REFERENCE

### 6.1 Cú pháp

```
items.{slug}.{field}       ← Dùng slug (ổn định, khuyến nghị)
items[{index}].{field}     ← Dùng index
```

### 6.2 Điều kiện

- Phải set `id_field: "slug"` trong `initGridField`
- Slug phải tồn tại trong `AL Slug Library`
- Các dòng trong grid phải có field `slug` được điền

### 6.3 Cách hoạt động

1. `id_field: "slug"` → đăng ký mapping doctype→field trong `_afbSlugFieldMap`
2. Khi user gõ `items.` → CompletionProvider duyệt tất cả rows, tìm field `slug`
3. Hiển thị danh sách slug làm gợi ý
4. Khi user chọn slug + `.` → hiển thị tất cả fields của dòng đó

### 6.4 Ví dụ thực tế

```
# Trong Bom Item "nep_kinh_tren" — width phụ thuộc vào kính:
width = 2 * (items.kinh_tren.width + items.kinh_tren.height)

# Trong Bom Item "keo_tren" — item_code phụ thuộc vào glass_type:
rule_input_expr = items.kinh_tren.glass_type
```

---

## 7. TOOLTIP & HOVER

### 7.1 Cách dùng

Rê chuột vào bất kỳ biến/hàm nào → tooltip tự động hiển thị.

### 7.2 Thông tin hiển thị

```
┌──────────────────────────────────────────┐
│ VL_NHOM  📄 Cục bộ                       │
│                                          │
│ | Thuộc tính  | Giá trị            |     │
│ |-------------|--------------------|     │
│ | Giá trị     | 0                  |     │
│ | Kiểu        | Float              |     │
│ | Doctype     | Cost Bucket        |     │
└──────────────────────────────────────────┘
```

Đối với hàm:
```
┌──────────────────────────────────────────┐
│ round(number, decimals)                   │
│ Làm tròn số                              │
│ Ví dụ: round(3.14159,2) → 3.14           │
└──────────────────────────────────────────┘
```

Đối với cross-row:
```
┌──────────────────────────────────────────┐
│ items.kinh_tren.glass_thick  ↔ Sibling   │
│                                          │
│ | Thuộc tính  | Giá trị            |     │
│ |-------------|--------------------|     │
│ | Giá trị     | 24                 |     │
│ | Kiểu        | Float              |     │
│ | Doctype     | AL Bom Item        |     │
└──────────────────────────────────────────┘
```

---

## 8. DEBUG & TROUBLESHOOTING

### 8.1 Kiểm tra context đã load

```javascript
// Browser console
alumglass.FormulaContext.getSync("AL Cost Template")
// → { variables: [...], references: [...], total_variables: 45 }

// Xem danh sách biến
alumglass.FormulaContext.getSync("AL Cost Template").variables
    .map(v => v.name)
// → ["VL_NHOM", "VL_KINH", ..., "OFFSET_FRAME", ...]
```

### 8.2 Kiểm tra monkey-patch

```javascript
formula_builder.formula._ContextBuilder.__alumglassPatched
// → true (nếu patch đã chạy)
```

### 8.3 Kiểm tra API

```bash
bench --site erpapp.com console
>>> from alumglass.api import get_formula_context
>>> ctx = get_formula_context("AL Cost Template")
>>> ctx["total_variables"]  # → ~45
>>> ctx["total_sources"]    # → ~7
```

### 8.4 Lỗi thường gặp

| Lỗi | Nguyên nhân | Fix |
|-----|------------|-----|
| Không có autocomplete | Context chưa load | `alumglass.FormulaContext.fetch("Doctype")` chưa được gọi |
| Thiếu biến | Biến chưa có trong DB | Thêm record vào bảng tương ứng |
| Cache cũ | Đã thêm biến nhưng chưa thấy | `alumglass.FormulaContext.invalidate("Doctype")` |
| Cross-row không gợi ý slug | Thiếu `id_field` | Set `id_field: "slug"` |
| Tooltip không hiện | Monaco hover provider lỗi | Reload trang, check console |
| JS không cập nhật | Cache browser | `bench build` + Ctrl+Shift+R |

### 8.5 Flow debug hoàn chỉnh

```
1. Kiểm tra API có trả về biến không:
   $ bench console
   >>> from alumglass.api import get_formula_context
   >>> ctx = get_formula_context("AL Cost Template")
   >>> print(len(ctx["variables"]))  # Phải > 0

2. Kiểm tra context đã cache trong browser chưa:
   > alumglass.FormulaContext.getSync("AL Cost Template").total_variables

3. Kiểm tra monkey-patch đã chạy:
   > formula_builder.formula._ContextBuilder.__alumglassPatched

4. Mở editor → gõ VL_ → phải thấy suggestions
   Nếu không: gõ Ctrl+Space để mở tất cả suggestions

5. Rê chuột vào biến → phải thấy tooltip
   Nếu không: F12 → Console → tìm lỗi
```

---

## PHỤ LỤC: So sánh Trước ⇨ Sau

| Khía cạnh | Trước (hardcode) | Sau (data-driven) |
|-----------|-----------------|-------------------|
| Thêm Cost Bucket mới | Sửa JS | Thêm record DB ✅ |
| Thêm System Variable | Sửa JS | Thêm record DB ✅ |
| Thêm biến custom | Sửa JS | Thêm record DB ✅ |
| Thêm slug mới | Sửa JS | Thêm record DB ✅ |
| Phân loại biến | Cố định trong code | Theo `group` trong DB ✅ |
| Lọc biến theo doctype | Không có | `applies_to_doctype` ✅ |
| Số dòng JS hardcode biến | ~80 dòng | **0 dòng** ✅ |
| Người dùng tự thêm biến | ❌ Cần dev | ✅ Qua UI |

---

*Cập nhật: 2026-08-05 | AlumGlass v28.8 | Data-driven, zero hardcode*


1. Giải thích chi tiết kiến trúc AL Bom Engine
Tổng quan
Hệ thống AL Bom Engine là module lõi của dự án AlumGlass, quản lý toàn bộ cấu trúc Bill of Materials (BOM) cho sản phẩm nhôm kính. Kiến trúc tuân theo mô hình data-driven với 0 hardcode — mọi thứ đều lấy từ DB.

Sơ đồ quan hệ các Doctype

┌─────────────────────────────────────────────────────────────────┐
│                        AL BOM (bom_code)                        │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │ Bom Set      │  │ Accessory Set    │  │ Cost Template     │  │
│  │ (bom_set)    │  │ (pk_set, opt)    │  │ (default_cost_..) │  │
│  └──────┬───────┘  └────────┬─────────┘  └────────┬──────────┘  │
│         │                   │                     │             │
└─────────┼───────────────────┼─────────────────────┼─────────────┘
          │                   │                     │
          ▼                   ▼                     ▼
┌──────────────────┐  ┌────────────────┐  ┌──────────────────────┐
│   AL BOM SET     │  │AL ACCESSORY SET│  │  AL COST TEMPLATE    │
│  (set_code)      │  │ (set_code)     │  │  (template_code)     │
│                  │  │                │  │                      │
│ ┌──────────────┐ │  │ ┌────────────┐ │  │ ┌──────────────────┐ │
│ │ AL Bom Item  │ │  │ │AL Acc. Item│ │  │ │AL Cost Template  │ │
│ │ (child table)│ │  │ │(child tbl) │ │  │ │Item (child tbl)  │ │
│ └──────────────┘ │  │ └────────────┘ │  │ └──────────────────┘ │
└──────────────────┘  └────────────────┘  └──────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│                     AL BOM VERSION (snapshot)                    │
│  workflow_state: Draft → Pending → Approved → Published → Retired│
│  bom_set_snapshot (JSON)    cost_template_snapshot (JSON)        │
│  ┌──────────────────────┐                                        │
│  │ AL BOM Change Log    │ (child table - track changes)          │
│  └──────────────────────┘                                        │
└──────────────────────────────────────────────────────────────────┘
Chi tiết từng doctype
AL BOM (al_bom)
Vai trò: Header BOM, liên kết các thành phần cấu trúc sản phẩm
Fields chính:
bom_code (unique, autoname) — mã BOM
bom_set → link đến AL Bom Set (bắt buộc)
pk_set → link đến AL Accessory Set (optional, nhãn "Accessory Set")
default_cost_template → link đến AL Cost Template (bắt buộc)
representative_item → Item đại diện để tra composite key price, KHÔNG phải mã sản phẩm bán ra
current_version → link đến AL BOM Version (read-only, tự động set)
requires_approval_for_new_version — yêu cầu approval khi tạo version mới
Python: get_bom_structure(bom_code) API trả về toàn bộ cấu trúc: BOM + Bom Set + Items
AL Bom Set (al_bom_set)
Vai trò: Tập hợp các dòng vật tư (Bom Items) — định nghĩa cấu trúc sản phẩm
Fields chính:
set_code (unique, autoname), set_name
product_type, brand, profile_system — phân loại sản phẩm
variable_set → link đến AL Variable Set — tập biến đầu vào cho công thức
default_accessory_set → link đến AL Accessory Set
formula_fieldnames — JSON array các field của Bom Item cần evaluate như formula (default: ["width","height","qty","show_condition","item_condition_formula","rule_input_expr"])
items → Table chứa AL Bom Item rows
Python: _validate_slug_uniqueness() đảm bảo slug không trùng; clone_bom_set() API
AL Bom Item (al_bom_item) — TRUNG TÂM của hệ thống
Vai trò: Mỗi dòng đại diện 1 thành phần vật tư trong BOM (NHOM, KINH, THEP, INOX, VTP, PK...). Là child table (istable: 1).
Các section fields:
Section	Field	Mô tả
Basic	slug	Link đến AL Slug Library - định danh dòng duy nhất
category	Link đến AL Material Category (read-only, auto-fill từ slug)
line_name	Tên hiển thị (auto-fill từ slug)
cost_bucket	Link đến AL Cost Bucket - nhóm chi phí
Item Selection	item_selection_mode	Fixed / Rule / Formula
item_code	Item cụ thể (hiện khi mode=Fixed)
item_rule	Link đến AL Dynamic Item Rule (hiện khi mode=Rule)
item_condition_formula	Công thức FB (hiện khi mode=Formula)
rule_input_expr	Biểu thức input cho Rule (hiện khi mode=Rule)
Dimensions	width, height, qty	Công thức FB syntax cho kích thước & số lượng
Pricing	price_type	Item Price / Rule / Fixed
price_base_item	Item đại diện để tra giá composite key
Glass	default_glass_master	Glass Master cho dòng KINH
panel_count_formula, qty_per_panel_formula	Công thức panel
3 chế độ Item Selection:

Fixed: Dùng item_code cố định — validation data-driven dựa trên AL Material Category.requires_item_code
Rule: Dùng item_rule (AL Dynamic Item Rule) với rule_input_expr làm input — rule resolve ra Item dựa trên THRESHOLD hoặc LOOKUP
Formula: Dùng item_condition_formula (FB formula) — kết quả formula quyết định Item được chọn
Python validation (data-driven từ AL Material Category flags):

requires_item_code → bắt buộc item_code khi mode=Fixed
requires_price_base_item → bắt buộc price_base_item khi price_type=Item Price
requires_glass_master → bắt buộc default_glass_master cho dòng KINH
qty luôn bắt buộc
Rule mode: bắt buộc item_rule + rule_input_expr
Formula mode: bắt buộc item_condition_formula
AL Accessory Set (al_accessory_set)
Vai trò: Bộ phụ kiện (bản lề, keo, vít, gioăng...) cho sản phẩm
Fields: set_code, set_name, product_type, variable_set
Child table: AL Accessory Item với slug, item_code, qty (cố định), qty_formula (FB syntax), unit_price
AL BOM Version (al_bom_version)
Vai trò: Snapshot bất biến (immutable) của BOM — mỗi lần tạo version là 1 bản chụp toàn bộ cấu trúc
Workflow: Draft → Pending Approval → Approved → Published → Retired
Snapshot: bom_set_snapshot + cost_template_snapshot (JSON) — tự động chụp khi before_insert
Immutable guard: Sau khi Published, không được sửa snapshot — phải tạo version mới
AL Cost Template (al_cost_template)
Vai trò: Master công thức tính giá thành từ Cost Buckets (14 dòng chuẩn: TONG_VL → GIA_VAT)
Child table: AL Cost Template Item với line_code, calc_formula (FB formula), cost_bucket, is_subtotal
Luồng hoạt động (Runtime Engine)

B0: Pin version (resolve BOM version đang active)
  ↓
B1: Gather inputs (W_mm, H_mm, n_panel, variables từ Variable Set)
  ↓
B2: Prefetch master data (glass specs, item prices, rules)
  ↓
B3: Build formulas (compile công thức từ Bom Items, normalize cross-refs items.xxx.field → xxx__field)
  ↓
B4: Calculate via FormulaEngine (evaluate từng dòng)
  ↓
B5: Aggregate cost buckets
  ↓
B6: Calculate via FlexibleFormulaEngine (cost template)
  ↓
B7: Save results → Quotation Item + ConfigSnapshot