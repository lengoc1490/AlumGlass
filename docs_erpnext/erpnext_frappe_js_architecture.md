# ERPNext / Frappe — Kiến trúc JavaScript & Hệ thống Kế thừa

> Tài liệu kỹ thuật toàn diện: nguyên lý thiết kế, chuỗi kế thừa class, cách ghi đè method, và cách tự tạo class tái sử dụng cho nhiều Doctype.

---

## 1. Tổng quan kiến trúc

### 1.1 Cây kế thừa (Inheritance Chain)

```
frappe.ui.form.Controller          ← Base class của Frappe (form.js)
    └── erpnext.stock.StockController    ← stock_controller.js
            └── erpnext.payments             ← payments.js
                    └── erpnext.taxes_and_totals     ← taxes_and_totals.js
                            └── erpnext.TransactionController    ← transaction.js
                                    └── erpnext.selling.SellingController    ← sales_common.js
                                            └── erpnext.accounts.SalesInvoiceController  ← sales_invoice.js
```

**Nguyên lý cốt lõi:** Mỗi lớp con **mở rộng** lớp cha bằng `extends`, và gọi `super.method()` để giữ lại hành vi cha trước khi thêm logic riêng.

---

### 1.2 Hai hệ thống song song

Frappe/ERPNext dùng **hai cơ chế đăng ký event** song song nhau:

| Cơ chế | Cú pháp | Dùng cho |
|--------|---------|---------|
| **Class method** | `method_name() { ... }` trong class | Logic được kế thừa, override |
| **frappe.ui.form.on()** | `frappe.ui.form.on('Doctype', { event })` | Event handlers đơn giản, không cần kế thừa |

Cả hai đều được Frappe's `ScriptManager` gọi khi một field thay đổi hoặc một event xảy ra.

---

## 2. Nguyên lý hoạt động chi tiết

### 2.1 Vòng đời (Lifecycle) của một Form

```
1. frappe.set_route('Form', doctype, docname)
        ↓
2. frappe.ui.form.Form.refresh()      ← form.js
        ↓
3. trigger_onload() → script_manager.trigger('onload')
        ↓
4. Controller.onload()               ← class method
        ↓
5. render_form()
        ↓
6. script_manager.trigger('refresh')
        ↓
7. Controller.refresh()              ← class method
        ↓
8. [User interaction] → field change
        ↓
9. frappe.model.on(doctype, '*', callback)   ← form.js watch_model_updates()
        ↓
10. script_manager.trigger(fieldname)
        ↓
11. Controller.fieldname()           ← class method tương ứng tên field
```

### 2.2 ScriptManager — Cơ chế dispatch event

`ScriptManager` là trung tâm điều phối. Khi `trigger('customer')` được gọi:

1. Tìm method `customer()` trong **Controller class** → gọi nếu tồn tại
2. Tìm handler `customer` trong **frappe.ui.form.on()** → gọi nếu tồn tại
3. Xử lý các **fetch** được đăng ký bằng `frm.add_fetch()`

### 2.3 Cách field name map vào method name

```javascript
// Khi user thay đổi field "customer" trên form
// Frappe tự động gọi:
controller.customer(doc, dt, dn)

// Khi user thay đổi field "tax_id" trong child table "items"
controller.tax_id(doc, cdt, cdn)

// Event đặc biệt:
controller.onload()
controller.refresh()
controller.validate()
controller.on_submit()
controller.before_save()
```

---

## 3. Kế thừa và Ghi đè — Hướng dẫn chuẩn

### 3.1 Ghi đè hoàn toàn (Full Override)

```javascript
// Ghi đè method mà KHÔNG giữ lại hành vi cha
erpnext.accounts.SalesInvoiceController = class SalesInvoiceController 
    extends erpnext.selling.SellingController {

    refresh(doc, dt, dn) {
        // Không gọi super.refresh() → bỏ qua toàn bộ logic của cha
        // Chỉ chạy code của riêng mình
        this.show_general_ledger();
    }
};
```

### 3.2 Mở rộng (Extension — Best Practice)

```javascript
refresh(doc, dt, dn) {
    super.refresh();          // ← Luôn gọi super trước
    // Sau đó thêm logic riêng
    this.my_custom_logic();
}
```

### 3.3 Ghi đè một phần với điều kiện

```javascript
customer() {
    // Kiểm tra điều kiện trước
    if (this.frm.updating_party_details) return;

    // Gọi super để giữ logic chuẩn
    super.customer();          // từ SellingController

    // Thêm logic riêng sau
    if (this.frm.doc.customer) {
        this.load_loyalty_programs();
    }
}
```

### 3.4 Đăng ký Controller vào Form

```javascript
// Bắt buộc ở cuối file — kết nối class với form hiện tại
extend_cscript(cur_frm.cscript, 
    new erpnext.accounts.SalesInvoiceController({ frm: cur_frm })
);
```

`extend_cscript` merge tất cả method từ class instance vào `cur_frm.cscript` (backward compatibility).

---

## 4. Các Method quan trọng và thời điểm gọi

### 4.1 Lifecycle Methods

```javascript
class MyController extends erpnext.TransactionController {

    setup(doc) {
        // Gọi khi form được khởi tạo lần đầu
        // Dùng để: setup frm.make_methods, bind global events
        super.setup(doc);
    }

    onload() {
        // Gọi một lần khi document được load lần đầu
        // Dùng để: setup queries, set default values, load config
        super.onload();
    }

    refresh(doc, dt, dn) {
        // Gọi mỗi lần form được render lại
        // Dùng để: show/hide buttons, set field properties
        super.refresh();
    }

    validate() {
        // Gọi trước khi Save/Submit
        // Dùng để: validate custom rules
        this.calculate_taxes_and_totals(false);
    }

    on_submit(doc, dt, dn) {
        // Gọi sau khi Submit thành công
    }

    before_save() {
        // Gọi trước khi Save
    }
}
```

### 4.2 Field Trigger Methods

Mỗi field name trong Doctype có thể có method tương ứng:

```javascript
class MyController extends erpnext.TransactionController {

    // Trigger khi field "customer" thay đổi
    customer() {
        super.customer();
        // custom logic...
    }

    // Trigger khi field "posting_date" thay đổi
    posting_date() {
        super.posting_date();
    }

    // Trigger khi field "qty" trong child table thay đổi
    // doc = parent doc, cdt = child doctype, cdn = child docname
    qty(doc, cdt, cdn) {
        super.qty(doc, cdt, cdn);
        let item = frappe.get_doc(cdt, cdn);
        // xử lý item...
    }

    // Trigger khi thêm row vào child table "items"
    items_add(doc, cdt, cdn) {
        super.items_add(doc, cdt, cdn);
    }

    // Trigger khi xóa row khỏi child table "items"
    items_remove(doc, cdt, cdn) {
        this.calculate_taxes_and_totals();
    }
}
```

---

## 5. Tạo Class tái sử dụng cho nhiều Doctype

### 5.1 Class cho một nhóm Doctype liên quan

Ví dụ: Tạo một class custom cho tất cả các Sales documents.

```javascript
// File: custom_selling_controller.js
// Áp dụng cho: Sales Order, Sales Invoice, Delivery Note

frappe.provide("myapp.selling");

myapp.selling.CustomSellingController = class CustomSellingController 
    extends erpnext.selling.SellingController {

    setup(doc) {
        super.setup(doc);
        // Logic chung cho tất cả Sales docs
        this.setup_custom_queries();
    }

    onload() {
        super.onload();
        this.load_custom_config();
    }

    refresh(doc, dt, dn) {
        super.refresh();
        // Hiển thị button tùy theo loại doctype
        if (this.frm.doc.docstatus === 1) {
            this.add_common_custom_button();
        }
        // Logic riêng theo doctype
        if (doc.doctype === 'Sales Invoice') {
            this.show_invoice_specific_buttons();
        }
    }

    // Method chung — dùng cho mọi doctype kế thừa
    add_common_custom_button() {
        this.frm.add_custom_button(__('Custom Action'), () => {
            this.execute_custom_action();
        }, __('Custom'));
    }

    execute_custom_action() {
        frappe.call({
            method: 'myapp.api.custom_action',
            args: {
                doctype: this.frm.doc.doctype,
                docname: this.frm.doc.name
            },
            callback: (r) => {
                if (!r.exc) {
                    this.frm.reload_doc();
                }
            }
        });
    }

    setup_custom_queries() {
        // Query chung cho nhiều doctype
        if (this.frm.fields_dict['custom_field']) {
            this.frm.set_query('custom_field', () => ({
                filters: { company: this.frm.doc.company }
            }));
        }
    }

    load_custom_config() {
        // Load config từ server một lần khi onload
        frappe.call({
            method: 'myapp.api.get_config',
            callback: (r) => {
                if (r.message) {
                    this.custom_config = r.message;
                }
            }
        });
    }
};
```

```javascript
// File: sales_invoice.js (custom override)
// Kế thừa từ class custom của bạn thay vì ERPNext gốc

myapp.accounts.MySalesInvoiceController = class MySalesInvoiceController
    extends myapp.selling.CustomSellingController {

    refresh(doc, dt, dn) {
        super.refresh();          // gọi CustomSellingController.refresh()
        // Logic riêng chỉ cho Sales Invoice
        this.show_invoice_specific_ui();
    }

    show_invoice_buttons_specific_ui() {
        if (this.frm.doc.outstanding_amount > 0) {
            // ...
        }
    }
};

extend_cscript(cur_frm.cscript,
    new myapp.accounts.MySalesInvoiceController({ frm: cur_frm })
);
```

### 5.2 Mixin Pattern — Class không kế thừa trực tiếp

Khi muốn thêm behavior cho nhiều doctype không liên quan nhau:

```javascript
// Định nghĩa mixin (object chứa các method)
const ApprovalMixin = {

    setup_approval_workflow(frm) {
        this._approval_frm = frm;
    },

    show_approval_button() {
        if (this.frm.doc.docstatus === 0 && this.frm.doc.status === 'Pending Approval') {
            this.frm.add_custom_button(__('Approve'), () => {
                this.approve_document();
            });
        }
    },

    approve_document() {
        frappe.call({
            method: 'myapp.approval.approve',
            args: { doctype: this.frm.doc.doctype, name: this.frm.doc.name },
            callback: (r) => { if (!r.exc) this.frm.reload_doc(); }
        });
    }
};

// Áp dụng mixin vào bất kỳ Controller nào
class MyPurchaseController extends erpnext.buying.BuyingController {
    constructor(opts) {
        super(opts);
        // Inject các method của mixin
        Object.assign(this, ApprovalMixin);
    }

    refresh() {
        super.refresh();
        this.show_approval_button();   // method từ mixin
    }
}
```

### 5.3 Shared Module Pattern — Utility class độc lập

```javascript
frappe.provide("myapp.utils");

myapp.utils.DocumentHelper = class DocumentHelper {
    constructor(frm) {
        this.frm = frm;
    }

    // Có thể được gọi từ bất kỳ controller nào
    static validate_fiscal_year(posting_date, company) {
        return frappe.call({
            method: 'myapp.utils.validate_fiscal_year',
            args: { posting_date, company }
        });
    }

    get_custom_print_formats() {
        return frappe.call({
            method: 'myapp.utils.get_print_formats',
            args: { doctype: this.frm.doctype }
        });
    }
};

// Sử dụng trong bất kỳ controller nào:
class MyController extends erpnext.TransactionController {
    async refresh() {
        super.refresh();
        const helper = new myapp.utils.DocumentHelper(this.frm);
        const formats = await helper.get_custom_print_formats();
        // ...
    }
}
```

---

## 6. frappe.ui.form.on() — Khi nào dùng thay class?

### 6.1 Quy tắc lựa chọn

| Tình huống | Dùng |
|-----------|------|
| Logic cần kế thừa / override | **Class method** |
| Logic đơn giản, chỉ cho 1 doctype | **frappe.ui.form.on()** |
| Thêm event sau khi class đã được init | **frappe.ui.form.on()** |
| Child table events (items_add, v.v.) | **Cả hai đều được** |

### 6.2 Cú pháp frappe.ui.form.on()

```javascript
frappe.ui.form.on('Sales Invoice', {
    // Lifecycle events
    setup(frm) { },
    onload(frm) { },
    refresh(frm) { },

    // Field triggers
    customer(frm) {
        // frm.doc.customer đã được cập nhật
    },

    // Child table field trigger
    items_add(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
    },

    // Child table row field trigger
    qty(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
    }
});

// Cho child table doctype
frappe.ui.form.on('Sales Invoice Item', {
    qty(frm, cdt, cdn) { }
});
```

### 6.3 Thứ tự thực thi khi cả hai cùng tồn tại

```
1. Class method (Controller instance) được gọi trước
2. frappe.ui.form.on() handler được gọi sau
```

---

## 7. Các Pattern quan trọng trong ERPNext

### 7.1 Query Filter Pattern

```javascript
onload() {
    super.onload();

    // Filter cho Link field đơn
    this.frm.set_query('warehouse', () => ({
        filters: {
            company: this.frm.doc.company,
            is_group: 0
        }
    }));

    // Filter cho Link field trong child table
    this.frm.set_query('income_account', 'items', () => ({
        query: 'erpnext.controllers.queries.get_income_account',
        filters: { company: this.frm.doc.company }
    }));

    // Filter phức tạp dạng array
    this.frm.set_query('asset', 'items', (doc, cdt, cdn) => {
        let row = locals[cdt][cdn];
        return {
            filters: [
                ['Asset', 'item_code', '=', row.item_code],
                ['Asset', 'docstatus', '=', 1],
                ['Asset', 'company', '=', doc.company]
            ]
        };
    });
}
```

### 7.2 Custom Button Pattern

```javascript
refresh(doc) {
    super.refresh();

    // Button đơn
    if (doc.docstatus === 1 && doc.outstanding_amount > 0) {
        this.frm.add_custom_button(
            __('Payment'),           // label
            () => this.make_payment_entry(),  // action
            __('Create')             // group (optional)
        );
        // Set group button là primary
        this.frm.page.set_inner_btn_group_as_primary(__('Create'));
    }

    // Button dạng menu
    this.frm.add_custom_button(__('View Report'), () => {
        frappe.route_options = { voucher_no: doc.name };
        frappe.set_route('query-report', 'General Ledger');
    }, __('View'));
}
```

### 7.3 Mapped Document Pattern (Make từ doc khác)

```javascript
make_delivery_note() {
    frappe.model.open_mapped_doc({
        method: 'erpnext.accounts.doctype.sales_invoice.sales_invoice.make_delivery_note',
        frm: this.frm
    });
}

// Hoặc map từ nhiều source documents
make_from_sales_order() {
    erpnext.utils.map_current_doc({
        method: 'erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice',
        source_doctype: 'Sales Order',
        target: this.frm,
        setters: {
            customer: this.frm.doc.customer || undefined,
        },
        get_query_filters: {
            docstatus: 1,
            status: ['not in', ['Closed', 'On Hold']],
            per_billed: ['<', 99.99],
            company: this.frm.doc.company
        }
    });
}
```

### 7.4 frappe.call Pattern

```javascript
// Call server method với callback
frappe.call({
    method: 'erpnext.accounts.party.get_party_details',
    args: {
        party: this.frm.doc.customer,
        party_type: 'Customer',
        posting_date: this.frm.doc.posting_date
    },
    callback: (r) => {
        if (!r.exc && r.message) {
            this.frm.set_value('customer_name', r.message.customer_name);
        }
    }
});

// Call method trên document hiện tại
this.frm.call({
    doc: this.frm.doc,
    method: 'set_missing_values',
    args: { for_validate: false },
    callback: (r) => {
        if (!r.exc) this.calculate_taxes_and_totals();
    }
});
```

### 7.5 Child Table Pattern

```javascript
// Lấy data từ child table row
qty(doc, cdt, cdn) {
    let item = frappe.get_doc(cdt, cdn);   // lấy child row document
    let row = locals[cdt][cdn];             // cách khác — tương đương

    // Set value trên child row
    frappe.model.set_value(cdt, cdn, 'amount', item.qty * item.rate);

    // Refresh field trên child row
    refresh_field('amount', item.name, item.parentfield);
}

// Lặp qua tất cả items
calculate_total() {
    let total = 0;
    (this.frm.doc.items || []).forEach(item => {
        total += flt(item.amount);
    });
    this.frm.set_value('total', total);
}

// Add child row
add_item() {
    let row = frappe.model.add_child(this.frm.doc, 'Sales Invoice Item', 'items');
    row.item_code = 'ITEM-001';
    row.qty = 1;
    this.frm.fields_dict.items.grid.refresh();
}
```

---

## 8. Tạo Custom Controller hoàn chỉnh — Template

```javascript
// File: my_custom_app/public/js/my_controller.js
// Áp dụng cho: Purchase Invoice (ví dụ)

frappe.provide("myapp.accounts");

myapp.accounts.MyPurchaseInvoiceController = class MyPurchaseInvoiceController
    extends erpnext.buying.BuyingController {

    // ─── LIFECYCLE ─────────────────────────────────────────────────────────

    setup(doc) {
        super.setup(doc);
        // Thêm make_methods (buttons từ frm.make_new())
        this.frm.make_methods = {
            'Custom Document': this.make_custom_doc.bind(this),
        };
    }

    onload() {
        super.onload();
        this._setup_queries();
        this._load_initial_data();
    }

    refresh(doc, dt, dn) {
        super.refresh();
        this._setup_buttons(doc);
        this._setup_field_visibility(doc);
    }

    validate() {
        super.validate();
        this._custom_validations();
    }

    on_submit(doc, dt, dn) {
        this._post_submit_actions(doc);
    }

    // ─── FIELD TRIGGERS ────────────────────────────────────────────────────

    supplier() {
        super.supplier();   // giữ logic chuẩn (get_party_details, v.v.)
        this._load_supplier_specific_data();
    }

    posting_date() {
        super.posting_date();
        this._recalculate_based_on_date();
    }

    // Child table field
    qty(doc, cdt, cdn) {
        super.qty(doc, cdt, cdn);
        this._apply_custom_pricing(doc, cdt, cdn);
    }

    // ─── PRIVATE METHODS ───────────────────────────────────────────────────

    _setup_queries() {
        // Custom warehouse query
        this.frm.set_query('set_warehouse', () => ({
            filters: {
                company: this.frm.doc.company,
                warehouse_type: 'Custom Type',
                is_group: 0
            }
        }));
    }

    _load_initial_data() {
        if (this.frm.doc.__islocal) return;  // bỏ qua khi tạo mới
        frappe.call({
            method: 'myapp.api.get_initial_data',
            args: { name: this.frm.doc.name },
            callback: (r) => {
                if (r.message) {
                    this.initial_data = r.message;
                }
            }
        });
    }

    _setup_buttons(doc) {
        // Chỉ hiện khi submitted và điều kiện thỏa mãn
        if (doc.docstatus === 1 && doc.custom_field === 'Ready') {
            this.frm.add_custom_button(__('Process'), () => {
                this._process_document();
            }, __('Actions'));
        }

        // Always show (when submitted)
        if (doc.docstatus === 1) {
            this.frm.add_custom_button(__('Custom Report'), () => {
                frappe.route_options = { reference: doc.name };
                frappe.set_route('query-report', 'My Custom Report');
            }, __('View'));
        }
    }

    _setup_field_visibility(doc) {
        // Hide/show fields based on conditions
        this.frm.toggle_display('custom_section',
            doc.custom_type === 'Special');

        this.frm.toggle_reqd('custom_mandatory_field',
            doc.custom_type === 'Special');
    }

    _custom_validations() {
        let doc = this.frm.doc;

        if (doc.custom_amount > doc.grand_total) {
            frappe.throw(__('Custom Amount cannot exceed Grand Total'));
        }

        // Validate child table
        (doc.items || []).forEach((item, i) => {
            if (!item.custom_required_field) {
                frappe.throw(__(
                    'Row {0}: Custom Required Field is mandatory', [i + 1]
                ));
            }
        });
    }

    _load_supplier_specific_data() {
        if (!this.frm.doc.supplier) return;
        frappe.call({
            method: 'myapp.api.get_supplier_data',
            args: { supplier: this.frm.doc.supplier },
            callback: (r) => {
                if (r.message) {
                    this.frm.set_value('custom_credit_limit', r.message.credit_limit);
                }
            }
        });
    }

    _recalculate_based_on_date() {
        // Custom date-based calculation
    }

    _apply_custom_pricing(doc, cdt, cdn) {
        let item = frappe.get_doc(cdt, cdn);
        // Custom pricing logic
    }

    _process_document() {
        frappe.confirm(
            __('Are you sure you want to process this document?'),
            () => {
                frappe.call({
                    method: 'myapp.api.process_document',
                    args: {
                        doctype: this.frm.doctype,
                        docname: this.frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __('Processing...'),
                    callback: (r) => {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: __('Document processed successfully'),
                                indicator: 'green'
                            });
                            this.frm.reload_doc();
                        }
                    }
                });
            }
        );
    }

    _post_submit_actions(doc) {
        // Notify, create linked docs, etc.
    }

    // ─── PUBLIC MAPPED DOC METHODS ─────────────────────────────────────────

    make_custom_doc() {
        frappe.model.open_mapped_doc({
            method: 'myapp.doctype.custom_doc.custom_doc.make_from_purchase_invoice',
            frm: this.frm
        });
    }
};

// ─── ĐĂNG KÝ VÀO FORM ──────────────────────────────────────────────────────
extend_cscript(cur_frm.cscript,
    new myapp.accounts.MyPurchaseInvoiceController({ frm: cur_frm })
);

// ─── SUPPLEMENTARY EVENT HANDLERS (optional) ───────────────────────────────
frappe.ui.form.on('Purchase Invoice', {
    // Handlers không cần kế thừa đặt ở đây
    before_submit(frm) {
        // frm.doc available
    }
});

frappe.ui.form.on('Purchase Invoice Item', {
    // Child table specific handlers
    custom_child_field(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
    }
});
```

---

## 9. Thiết kế hệ thống — Các lưu ý quan trọng

### 9.1 Thứ tự gọi `super` — Quy tắc vàng

```javascript
// ✅ ĐÚNG — gọi super TRƯỚC khi thêm logic
refresh(doc) {
    super.refresh();        // setup base buttons, queries, labels
    this.my_button();      // thêm custom button sau
}

// ✅ ĐÚNG — gọi super SAU khi cần override trước
customer() {
    this.pre_customer_logic();    // chạy trước
    super.customer();              // sau đó gọi chuẩn
    this.post_customer_logic();   // sau đó thêm
}

// ❌ SAI — quên gọi super → mất toàn bộ logic cha
refresh(doc) {
    this.my_button();      // cha không được gọi → thiếu buttons
}
```

### 9.2 Tránh race condition với frappe.run_serially

```javascript
customer() {
    frappe.run_serially([
        () => erpnext.utils.get_party_details(this.frm, ...),
        () => this.apply_pricing_rule(),
        () => this.load_custom_data(),
        () => this.frm.refresh_fields()
    ]);
}
```

### 9.3 Kiểm tra điều kiện trước khi gọi

```javascript
refresh(doc) {
    super.refresh();

    // Luôn kiểm tra điều kiện — docstatus, fields tồn tại, v.v.
    if (doc.docstatus === 1 && !doc.is_return && doc.outstanding_amount > 0) {
        this.show_payment_button();
    }

    // Kiểm tra field tồn tại trước khi dùng
    if (this.frm.fields_dict['custom_field']) {
        this.setup_custom_query();
    }
}
```

### 9.4 frappe.provide — Namespace management

```javascript
// Luôn khai báo namespace trước khi dùng
frappe.provide("myapp.accounts");
frappe.provide("myapp.selling");
frappe.provide("myapp.utils");

// frappe.provide tạo nested object nếu chưa tồn tại:
// window.myapp = window.myapp || {};
// window.myapp.accounts = window.myapp.accounts || {};
```

---

## 10. Tóm tắt nhanh — Decision Guide

```
Muốn làm gì?                           Dùng gì?
─────────────────────────────────────────────────────────────────
Thêm logic khi field thay đổi          Class method: fieldname()
Thêm/ẩn button theo điều kiện          Class method: refresh()
Giữ logic cũ + thêm mới                super.method() + logic
Bỏ hoàn toàn logic cũ                  Override không gọi super
Filter cho Link field                   frm.set_query() trong onload()
Gọi Python API                          frappe.call({ method, args, callback })
Tạo doc từ doc khác                     frappe.model.open_mapped_doc()
Validate trước khi save                 Class method: validate()
Logic chạy sau khi submit               Class method: on_submit()
Tái sử dụng cho nhiều doctype          Class trung gian extends base class
Behavior không liên quan kế thừa       Mixin pattern (Object.assign)
Utility functions độc lập              Static class / module
```

---

*Tài liệu này tổng hợp từ: sales_invoice.js, sales_common.js, transaction.js, taxes_and_totals.js, payments.js, stock_controller.js, form.js trong ERPNext/Frappe source code.*
