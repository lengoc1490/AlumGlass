# Grid Placeholder — hiển thị placeholder mờ trong ô grid chưa click

## Vấn đề

Trong grid (bảng con doctype hoặc Table field trong dialog), `description` của field chỉ
hiển thị chữ mờ **bên dưới** ô khi field được focus/click — người dùng phải click vào từng
row mới đọc được diễn giải. Muốn chữ mờ hiển thị **ngay trong ô** (dù row chưa click), Frappe
native chỉ hỗ trợ `placeholder` cho ô đang editable (`ControlData.set_input_attributes` →
`data.js:234`; `ControlSelect.set_placeholder` → `select.js:8`). Khi row collapsed, cell render
`<div class="static-area ellipsis">` rỗng (`grid_row.js:1029-1030`) — không có placeholder.

## Giải pháp

Module JS dùng chung `alumglass.grid_placeholder` — **tự đọc `df.placeholder` của từng cột**,
không hardcode fieldname.

### Cơ chế

1. **CSS 1 quy tắc chung** dùng `attr()`:
   ```css
   .alumglass-grid-ph .grid-static-col .static-area:empty::before {
       content: attr(data-grid-placeholder);
       color: var(--text-muted);
       font-weight: 400;
       pointer-events: none;
   }
   ```
   `:empty` → chỉ hiển thị khi cell chưa có giá trị; có giá trị là biến mất.
   `attr()` đọc `data-grid-placeholder` gắn trên chính `.static-area` → không cần
   rule riêng từng field.

2. **Wrap `grid.render_result_rows`** — điểm duy nhất render mọi row trong Frappe v14:
   cả `Grid.refresh()` (`grid.js:438`) lẫn pagination `go_to_page()` (`grid_pagination.js`)
   đều đi qua nó. Sau mỗi lần render, quét `row.columns_list` → cột nào có `df.placeholder`
   thì gắn `data-grid-placeholder` lên `static_area`. `.static-area` tồn tại lâu dài
   (chỉ đổi nội dung qua `.html()`), nên gắn lại là idempotent, không cần re-apply thủ công.

3. **Scope per-grid**: add class `alumglass-grid-ph` lên `grid.wrapper` (`.form-grid-container`)
   → không ảnh hưởng grid khác dùng chung fieldname.

4. **Global auto**: patch `ControlTable.prototype.make` 1 lần (`enable_global()`) → mọi
   grid tạo sau đó (dialog, doctype bảng con, web form) đều tự wrap. File gọi
   `enable_global()` ngay khi load.

### Field defs lấy từ đâu

| Nguồn | Field defs |
| --- | --- |
| Dialog Table field | `grid.df.fields` (inline array) |
| Doctype bảng con | `grid.meta.fields` (child doctype) |

→ `_apply` đọc `col.df.placeholder` (col đã là cột hiển thị), nên tự dùng chung cả 2 loại.

## API

```js
alumglass.grid_placeholder.setup(grid)                    // 1 grid / 1 control table
alumglass.grid_placeholder.setup_dialog(dialog)           // toàn bộ Table field trong dialog
alumglass.grid_placeholder.setup_form(frm)                // toàn bộ bảng con trong form
alumglass.grid_placeholder.enable_global()                // auto cho MỌI grid (gọi 1 lần)
alumglass.grid_placeholder.set_column(grid, 'col', text)  // set/đổi placeholder 1 cột runtime
alumglass.grid_placeholder.set_columns(grid, {a: 'x', b: 'y'}) // set nhiều cột cùng lúc
```

- `set_column`/`set_columns` dùng cho placeholder **động** hoặc placeholder đặt qua JS (bảng con
  doctype v14 không lưu placeholder trong schema). `scope` nhận: `grid` instance, Table control,
  hoặc `{ frm, parentfield }`.

File `alumglass/public/js/grid_placeholder.js` tự gọi `enable_global()` khi load
(đăng ký trong `hooks.py app_include_js`, load trước các `public/overrides/*.js`).
Muốn tắt global → xóa dòng `enable_global()` cuối file, dùng `setup*` theo từng nơi.

## Ví dụ theo tình huống

> Nguyên tắc chung: **chỉ cần đưa `placeholder` vào `df` của cột** (bất kỳ cách nào dưới đây)
> là module tự hiển thị — row chưa click (collapsed) hiện chữ mờ trong ô, row đã click hiện
> placeholder native từ control. Không cần gọi thêm API ở từng nơi nếu đang dùng `enable_global()`.

### A. Dialog

#### A1. Dialog đơn giản — `frappe.prompt` + khai báo `placeholder` inline (cách thường dùng nhất)

```js
let dialog = frappe.prompt([
    {
        fieldname: 'items',
        fieldtype: 'Table',
        label: __('Items'),
        description: __('Chọn danh sách các Item để tạo Asset'), // chú thích dưới grid
        cannot_delete_rows: true,
        cannot_add_rows: true,
        fields: [
            { fieldname: 'item', fieldtype: 'Data', label: __('Item Code'),
              in_list_view: 1, read_only: 1, columns: 2 },
            { fieldname: 'asset_category', fieldtype: 'Link', label: __('Asset Category'),
              options: "Asset Category", in_list_view: 1, read_only: 0, reqd: 1, columns: 2,
              placeholder: __('Chọn Asset Category') },
            { fieldname: 'asset_group', fieldtype: 'Select', label: __('Asset Group'),
              options: ["", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], in_list_view: 1, columns: 2,
              placeholder: __('Chọn nhóm cho các item. Các mã cùng nhóm sẽ tạo chung 1 Item Asset') },
            { fieldname: 'asset_name', fieldtype: 'Data', label: __('Asset Name'),
              in_list_view: 1, columns: 2,
              placeholder: __('Đặt tên Asset cho các item cùng nhóm. Mỗi nhóm chỉ đặt một tên duy nhất') },
        ],
    }
], function (values) {
    // xử lý values.items
}, __('Create Asset Items'));
```

→ Không cần gọi gì thêm: `enable_global()` đã patch mọi ControlTable, dialog này tự hiển thị.

#### A2. Dialog dùng class `frappe.ui.form.Dialog` (không phải `prompt`)

```js
let dialog = new frappe.ui.form.Dialog({
    title: __('Chọn hàng'),
    fields: [
        {
            fieldname: 'items', fieldtype: 'Table', label: __('Items'),
            cannot_delete_rows: true, cannot_add_rows: true,
            fields: [
                { fieldname: 'item_code', fieldtype: 'Link', label: __('Item'),
                  options: 'Item', in_list_view: 1, columns: 4,
                  placeholder: __('Nhập hoặc chọn Item...') },
                { fieldname: 'qty', fieldtype: 'Float', label: __('Qty'),
                  in_list_view: 1, columns: 2, placeholder: __('Số lượng') },
            ],
        },
    ],
    primary_action: function (values) { /* ... */ },
});
dialog.show();
```

→ Như A1, tự động. `setup_dialog(dialog)` chỉ cần thiết khi **đã tắt `enable_global()`**.

#### A3. Một dialog chứa NHIỀU Table field

`setup_dialog(dialog)` (hoặc global auto) quét **toàn bộ** `fields_dict` → mọi Table field
trong dialog đều được áp dụng, không cần liệt kê từng cái:

```js
let dialog = frappe.prompt([
    { fieldname: 'in_items',  fieldtype: 'Table', label: __('Nhập'),
      fields: [ { fieldname: 'item_code', ... placeholder: __('Chọn Item') } ] },
    { fieldname: 'out_items', fieldtype: 'Table', label: __('Xuất'),
      fields: [ { fieldname: 'warehouse', ... placeholder: __('Chọn kho') } ] },
], cb);

// Nếu không dùng global:
alumglass.grid_placeholder.setup_dialog(dialog); // áp dụng cả in_items + out_items
```

#### A4. Table field trỏ tới một child doctype (qua `options`) — vẫn khai báo inline `fields`

Trong dialog, Frappe dùng `grid.df.fields` (mảng inline) làm field defs cho grid, kể cả khi
`options` trỏ tới một child doctype. Do đó `placeholder` phải khai báo **trong `fields`**,
không đọc từ child doctype:

```js
{
    fieldname: 'items', fieldtype: 'Table', label: __('Items'),
    options: 'Stock Entry Detail',          // chỉ để khớp schema, không cung cấp field defs
    fields: [
        { fieldname: 'item_code', fieldtype: 'Link', options: 'Item', in_list_view: 1,
          placeholder: __('Chọn Item') },   // ← bắt buộc khai báo ở đây
        // ...
    ],
}
```

#### A5. Cột Link có `get_query` + placeholder (như dialog Create Asset Items thực tế)

```js
{ fieldname: 'asset_category', fieldtype: 'Link', label: __('Asset Category'),
  options: "Asset Category", in_list_view: 1, read_only: 0, reqd: 1, columns: 2,
  get_query: () => {
      return {
          query: "alumglass.alumglass.doctype.overrides.asset_category.category_query",
          filters: { company: frm.doc.company },
      };
  },
  placeholder: __('Chọn Asset Category') },
```

→ `placeholder` song song với `get_query`, không xung đột.

#### A6. Cột Select + placeholder

Select hiển thị overlay mờ riêng (`.`placeholder` trong `ControlSelect`), module dùng chung
vẫn vẽ `::before` cho collapsed; khi click row → control Select hiện placeholder native:

```js
{ fieldname: 'asset_group', fieldtype: 'Select', label: __('Asset Group'),
  options: ["", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], in_list_view: 1, columns: 2,
  placeholder: __('Chọn nhóm cho các item. Các mã cùng nhóm sẽ tạo chung 1 Item Asset') },
```

#### A7. Placeholder ĐỘNG (đổi text theo thời điểm / theo dữ liệu chọn trước)

Cách 1 — dùng helper `set_column` (khuyên dùng, nhất quán cả dialog lẫn bảng con):

```js
let dialog = frappe.prompt([{ fieldname: 'items', fieldtype: 'Table', label: __('Items'),
    fields: [ { fieldname: 'item_code', fieldtype: 'Link', options: 'Item',
        in_list_view: 1, placeholder: '' } ] }], cb);

// sau khi biết company / trạng thái:
alumglass.grid_placeholder.set_column(dialog.fields_dict.items, 'item_code',
    __('Chọn Item thuộc công ty {0}', [frm.doc.company]));
```

Cách 2 — mutate `df.fields` trực tiếp rồi `grid.refresh()` (dialog: `grid.docfields` chính là
mảng inline `df.fields` — cùng object, nên mutate là col.df thấy ngay):

```js
let table_df = dialog.fields_dict.items.df.fields.find(f => f.fieldname === 'item_code');
table_df.placeholder = __('Chọn Item thuộc công ty {0}', [frm.doc.company]);
dialog.fields_dict.items.grid.refresh();   // _apply gắn lại data-grid-placeholder
```

#### A8. Setup có chọn lọc: 1 grid vs tất cả

```js
// chỉ 1 Table field cụ thể trong dialog
alumglass.grid_placeholder.setup(dialog.fields_dict.items);

// toàn bộ Table field trong dialog
alumglass.grid_placeholder.setup_dialog(dialog);
```

### B. Bảng con (child table) trong form doctype

> ⚠️ **Frappe v14 không lưu `placeholder` trong schema DocField/CustomField**
> (`docfield.json` không có cột `placeholder`). Khai báo `placeholder` trong doctype JSON
> child sẽ bị bỏ khi sync. Vì vậy với bảng con doctype phải **set placeholder qua JS runtime**
> bằng `set_column`/`set_columns`. (Dialog không bị hạn chế này — vì dùng mảng inline `df.fields`.)
>
> ⚠️ **Không dùng `frm.set_df_property('<table>', 'placeholder', ..., null, '<col>')` cho mục đích
> này.** Trace Frappe v14 `form.js:1510`:
> - Không truyền `docname` → nhánh `!docname` chạy, set placeholder lên **df của TABLE field**
>   (cấp grid, không phải cột) — không hiển thị ở cột.
> - Truyền `docname` (row name) → mutate object copy keyed theo row-name, khác object
>   `col.df` đang giữ (copy keyed theo parent docname) → không hiển thị.
> `set_column` mutate đúng `grid.docfields` + `row.docfields`/`col.df` nên chắc chắn hiển thị.

#### B1. Cách chuẩn — set placeholder cho cột bảng con ở `refresh` form script

```js
frappe.ui.form.on('Stock Entry', {
    refresh: function(frm) {
        // scope { frm, parentfield } — không cần biết grid instance
        alumglass.grid_placeholder.set_column({ frm, parentfield: 'items' },
            'custom_asset_category', __('Chọn Asset Category'));
        alumglass.grid_placeholder.set_column({ frm, parentfield: 'items' },
            'custom_asset_name', __('Đặt tên Asset cùng nhóm'));
    },
});
```

Hoặc gom nhiều cột 1 lần:

```js
alumglass.grid_placeholder.set_columns({ frm, parentfield: 'items' }, {
    custom_asset_category: __('Chọn Asset Category'),
    custom_asset_name:     __('Đặt tên Asset cùng nhóm'),
    custom_asset_group:    __('Chọn nhóm — cùng nhóm tạo chung 1 Item Asset'),
});
```

→ Không cần gọi `setup_form`/`setup`; global auto đã bao. `refresh` chạy lại là idempotent.

#### B2. Setup 1 bảng con cụ thể (khi đã tắt global)

```js
// cách 1 — truyền control table
alumglass.grid_placeholder.setup(frm.fields_dict['items']);

// cách 2 — truyền { frm, parentfield }
alumglass.grid_placeholder.setup({ frm: frm, parentfield: 'items' });

// cách 3 — toàn bộ bảng con trong form
alumglass.grid_placeholder.setup_form(frm);
```

#### B3. Placeholder động theo dữ liệu trong bảng con

Cột đổi gợi ý tuỳ theo `purpose` của Stock Entry, khi user đổi `purpose`:

```js
frappe.ui.form.on('Stock Entry', {
    purpose: function(frm) {
        let hint = frm.doc.purpose === 'Material Transfer'
            ? __('Nhập kho đích')
            : __('Nhập kho nhận hàng');
        alumglass.grid_placeholder.set_column({ frm, parentfield: 'items' },
            't_warehouse', hint);
    },
});
```

#### B4. Bảng con LỒNG nhau (nested child table — Table bên trong grid form)

Khi mở row của bảng cha (grid form), Frappe dựng các Table field bên trong bằng
`ControlTable.make` → `enable_global()` cũng patch được → nested grid tự áp dụng. Set
placeholder cho cột nested bằng `set_column` với scope là grid con:

```js
// giả sử: Stock Entry > items (Stock Entry Detail) > mở row > bảng con custom_sub_items
frappe.ui.form.on('Stock Entry', {
    refresh: function(frm) {
        // grid con chưa tồn tại cho tới khi row được mở → set khi mở row (grid_row_form / after_load)
        frm.fields_dict.items.grid.grid_rows.forEach(row => {
            if (row.grid_form && row.grid_form.fields_dict) {
                alumglass.grid_placeholder.set_column(row.grid_form.fields_dict['custom_sub_items'],
                    'sub_item_type', __('Chọn loại phụ liệu'));
            }
        });
    },
});
```

Hoặc nếu tắt global: `setup_form(frm)` không quét nested; cần `setup` trực tiếp grid con
khi nó được dựng (hook `grid_row_form` / `form_render` của child). Global auto vẫn là cách
đơn giản nhất — nó patch mọi ControlTable kể cả nested.

> Lưu ý: bảng con lồng chỉ tồn tại khi row cha đang mở (grid form) — placeholder hiện khi
> đó. Sau khi đóng row, grid con biến mất theo, không cần cleanup.

### C. Kết hợp & tinh chỉnh

#### C1. Bật/tắt global

```js
// Mặc định: file grid_placeholder.js gọi enable_global() khi load → toàn app tự động.
// Muốn chỉ áp dụng ở một số nơi: xóa dòng enable_global() cuối file, dùng setup*/setup_form*.
```

#### C2. Đổi placeholder SAU khi đã render

`set_column`/`set_columns` tự gọi `grid.refresh()` bên trong nên chỉ cần 1 lần gọi:

```js
alumglass.grid_placeholder.set_column(dialog.fields_dict.items, 'item_code', __('Mới'));
```

(Nếu tự mutate `df.placeholder` bằng tay thì phải nhớ gọi `grid.refresh()` để
`render_result_rows` chạy lại → `_apply` gắn `data-grid-placeholder` mới.)

#### C3. Đã có placeholder trong repo hiện tại

- `stock_entry.js` → dialog **Create Asset Items** (`make_asset_items`): các cột
  `asset_category`, `asset_group`, `asset_name`. Trước đây hardcode CSS per-field
  (`asset-items-dialog ...::before`) — đã thay bằng module dùng chung.

## Ghi chú

- Chỉ ảnh hưởng cột nào có `df.placeholder` trong `in_list_view` — các placeholder hiện có
  trong alumglass (filter report, list page, dynamic_table custom) không phải ControlTable grid
  nên không bị đổi hành vi.
- Cell `reqd` vẫn giữ viền đỏ error khi trống; placeholder mờ hiển thị bên trong không bị che.
- Chưa click + giá trị trống → hiển thị; có giá trị → tự mất. Khi edit rồi blur về collapsed,
  `static_area.html(txt)` cập nhật → placeholder tự quay lại nếu trống.
