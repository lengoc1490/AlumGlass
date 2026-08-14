# Hướng dẫn Custom & Kế thừa JavaScript trong ERPNext / Frappe

> Phiên bản: ERPNext v15 / Frappe v15  
> Tác giả: eupapp internal  
> Mục đích: Tài liệu tổng quát để custom JS một cách an toàn, tránh lỗi loop trigger, race condition khi kế thừa Controller

---

## 1. Kiến trúc chuỗi kế thừa trong ERPNext

### 1.1 Chuỗi kế thừa của Sales Invoice

```
erpnext.payments                       (payments.js)
    └─ erpnext.taxes_and_totals        (taxes_and_totals.js)
           └─ erpnext.TransactionController  (transaction.js)
                  └─ erpnext.selling.SellingController  (sales_common.js)
                         └─ erpnext.accounts.SalesInvoiceController  (sales_invoice.js)
                                └─ CustomSalesInvoiceController  (eupapp custom)
```

### 1.2 Hai loại event handler song song

ERPNext có **2 hệ thống** trigger JS chạy **đồng thời** — đây là nguồn gốc chính của mọi bug loop:

**Loại 1: Controller method (class method)**
```javascript
// Được gọi khi field thay đổi, theo tên method == tên field
class MyController {
    posting_date() { ... }   // trigger khi posting_date thay đổi
    currency() { ... }       // trigger khi currency thay đổi
    conversion_rate() { ... }
}
```

**Loại 2: frappe.ui.form.on (event handler)**
```javascript
frappe.ui.form.on('Sales Invoice', {
    posting_date: function(frm) { ... },  // cùng trigger với trên
    currency: function(frm) { ... },
});
```

> **QUAN TRỌNG**: Nếu một field có cả Controller method LÀ CẢ `frappe.ui.form.on` handler, **cả hai đều chạy**. Đây là nguyên nhân phổ biến nhất gây double-trigger.

### 1.3 Luồng trigger chính gây loop trong Sales Invoice

```
posting_date đổi
    │
    ├─► Controller.posting_date()
    │       └─► super.posting_date() [transaction.js]
    │               └─► frappe.ui.form.trigger("currency")  ← gọi currency trigger
    │                       │
    │                       └─► Controller.currency() [SalesInvoiceController]
    │                               └─► super.currency() [transaction.js]
    │                                       └─► get_exchange_rate()
    │                                               └─► set_value("conversion_rate")
    │                                                       │
    │                                                       └─► Controller.conversion_rate()
    │                                                               └─► apply_price_list()
    │                                                                       └─► plc_conversion_rate()
    │                                                                               └─► set_value("conversion_rate") ← LOOP
    │
    └─► frappe.ui.form.on posting_date handler (nếu có)
            └─► fetch_exchange_rate() ← chạy SONG SONG với trên
```

---

## 2. Nguyên tắc nền tảng khi custom

### Nguyên tắc 1: Hiểu rõ method nào gọi gì trước khi override

Trước khi override bất kỳ method nào, phải trace đọc:
- Method đó ở class cha gọi gì
- Những gì nó gọi có gọi lại field trigger không
- Chuỗi `set_value` → trigger nào sẽ kích hoạt

### Nguyên tắc 2: Phân loại method trước khi quyết định override

| Loại | Ví dụ | Chiến lược |
|------|-------|------------|
| Method có logic phức tạp ở core, chỉ cần thêm 1 chút | `onload`, `refresh`, `item_code` | Gọi `super`, thêm logic sau |
| Method có logic core gây conflict với custom | `currency`, `posting_date` | Override hoàn toàn, KHÔNG gọi super |
| Method hoàn toàn mới không có ở core | `fetch_exchange_rate`, `update_all_price_list_rate` | Thêm mới, không super |
| Method core gọi cascade trigger gây loop | `plc_conversion_rate`, `conversion_rate` | Override + thêm guard |

### Nguyên tắc 3: Guard pattern — mọi method set_value đều cần guard

```javascript
// PATTERN CHUẨN cho bất kỳ method nào có thể bị gọi lại
methodName() {
    if (this._in_methodName) return;   // early return nếu đang chạy
    this._in_methodName = true;
    try {
        // logic thực sự
    } finally {
        this._in_methodName = false;   // đảm bảo luôn reset dù có lỗi
    }
}
```

### Nguyên tắc 4: Tránh dùng `.then()` để reset flag

```javascript
// SAI — race condition: flag reset trước khi side-effect hoàn tất
this._flag = true;
this.frm.set_value("field", value).then(() => {
    this._flag = false; // có thể reset quá sớm
});

// ĐÚNG — dùng try/finally trong synchronous context
// Hoặc nếu cần async: dùng counter version thay vì boolean flag
this._version = (this._version || 0) + 1;
const v = this._version;
this.frm.set_value("field", value).then(() => {
    if (this._version === v) {
        // chỉ xử lý nếu không có request mới hơn
    }
});
```

### Nguyên tắc 5: Đừng để hai nơi cùng set một field

```javascript
// NGUY HIỂM: cả Controller method VÀ frappe.ui.form.on cùng set conversion_rate
// → double set → double trigger

// Chọn MỘT nơi để set, nơi còn lại để trống hoặc delegate
```

---

## 3. Các pattern cụ thể

### 3.1 Pattern: Override method + gọi super an toàn

Dùng khi: cần thêm logic trước/sau method cha, method cha không gây conflict.

```javascript
item_code(doc, cdt, cdn) {
    let item = frappe.get_doc(cdt, cdn);
    
    // Guard tránh gọi lại chính mình
    if (item._processing_item_code) return;
    item._processing_item_code = true;
    
    try {
        super.item_code(doc, cdt, cdn);        // gọi logic core
        get_price_list_rate(doc, cdt, cdn);    // thêm logic custom
    } finally {
        // Dùng setTimeout thay vì reset ngay
        // vì super.item_code có callback async bên trong
        setTimeout(() => { delete item._processing_item_code; }, 500);
    }
}
```

### 3.2 Pattern: Override hoàn toàn — không gọi super

Dùng khi: logic core gây conflict trực tiếp với custom logic.

```javascript
currency() {
    // Lý do không gọi super: super.currency() của transaction.js
    // sẽ gọi get_exchange_rate() từ core, chạy song song với
    // fetch_exchange_rate() custom → double set conversion_rate

    if (this._updating_currency) return;
    this._updating_currency = true;
    try {
        this.set_dynamic_labels();    // an toàn, không trigger field
        
        let company_currency = this.get_company_currency();
        if (this.frm.doc.currency === company_currency) {
            this.frm.set_value("conversion_rate", 1.0);
        } else if (this.frm.doc.currency) {
            this.fetch_exchange_rate();
        }
        this.update_all_price_list_rate();
    } finally {
        this._updating_currency = false;
    }
}
```

> **Khi không gọi super**: phải tự đảm bảo các side-effect cần thiết của super vẫn được thực hiện. Đọc kỹ core source để biết super làm gì.

### 3.3 Pattern: Guard đơn giản cho method không async

```javascript
plc_conversion_rate() {
    if (this.frm.doc.price_list_currency === this.get_company_currency()) {
        this.frm.set_value("plc_conversion_rate", 1.0);
    } else if (
        this.frm.doc.price_list_currency === this.frm.doc.currency &&
        this.frm.doc.plc_conversion_rate &&
        flt(this.frm.doc.plc_conversion_rate) != 1 &&
        flt(this.frm.doc.plc_conversion_rate) != flt(this.frm.doc.conversion_rate) &&
        flt(this.frm.doc.custom_is_manual_exchange_rate) == 0
    ) {
        // Guard: tránh trigger lại conversion_rate → plc_conversion_rate loop
        if (!this._setting_plc_rate) {
            this._setting_plc_rate = true;
            // frm.set_value là async, nhưng trigger sẽ chạy synchronous
            // trước khi Promise resolve, nên try/finally không bắt được
            // → dùng flag + reset trong frappe.run_serially hoặc setTimeout
            this.frm.set_value("conversion_rate", this.frm.doc.plc_conversion_rate);
            // Reset ngay sau — trigger đã được enqueue rồi, flag chỉ cần
            // bảo vệ trong stack hiện tại
            this._setting_plc_rate = false;
        }
    }

    if (!this.in_apply_price_list) {
        this.apply_price_list(null, true);
    }
}
```

### 3.4 Pattern: Debounce cho operation tốn kém

```javascript
update_all_price_list_rate() {
    const me = this;
    if (me.frm.doc.docstatus) return;
    if (!me.frm.doc.items?.length) return;
    
    // Hủy timer cũ nếu có
    if (me._rate_debounce_timer) clearTimeout(me._rate_debounce_timer);
    
    me._rate_debounce_timer = setTimeout(() => {
        // Version counter: nếu có request mới hơn, bỏ qua kết quả cũ
        me._rate_request_version = (me._rate_request_version || 0) + 1;
        const current_version = me._rate_request_version;
        
        const doc_copy = JSON.parse(JSON.stringify(me.frm.doc));
        
        frappe.call({
            method: "update_all_price_list_rate",
            doc: doc_copy,
            freeze: false,
            callback: function(r) {
                // Bỏ qua nếu có request mới hơn đã được gửi đi
                if (current_version !== me._rate_request_version) return;
                
                if (r.message?.items) {
                    me._ignore_rate_trigger = true;
                    for (let row of r.message.items) {
                        let item = locals[row.doctype]?.[row.name];
                        if (!item) continue;
                        frappe.model.set_value(row.doctype, row.name, "rate", flt(row.rate));
                    }
                    me._ignore_rate_trigger = false;
                    me.calculate_taxes_and_totals();
                    me.frm.refresh_field("items");
                }
            },
            error: function() {}
        });
    }, 300); // 300ms debounce — đủ để gom nhiều trigger liên tiếp
}
```

### 3.5 Pattern: Cache key để tránh fetch lặp

```javascript
fetch_exchange_rate() {
    if (this.frm.doc.custom_is_manual_exchange_rate) return;
    if (this._fetching_rate) return;  // đang fetch rồi, bỏ qua

    let me = this;
    let company_currency = frappe.get_doc(":Company", this.frm.doc.company).default_currency;
    let from_currency = this.frm.doc.currency;
    let posting_date = this.frm.doc.posting_date;
    let bank = this.frm.doc.custom_bank || "";

    if (!from_currency || !posting_date) return;

    // Cache key bao gồm TẤT CẢ các tham số ảnh hưởng đến kết quả
    let key = `${from_currency}|${posting_date}|${bank}`;
    if (this._last_fetch_key === key) return;  // kết quả không đổi, bỏ qua
    this._last_fetch_key = key;

    if (from_currency === company_currency) {
        if (flt(this.frm.doc.conversion_rate) !== 1) {
            this.frm.set_value("conversion_rate", 1);
        }
        return;
    }

    this._fetching_rate = true;
    this.get_exchange_rate(posting_date, from_currency, company_currency, function(res) {
        try {
            if (res) {
                if (flt(me.frm.doc.conversion_rate) !== flt(res.rate)) {
                    me.frm.set_value("conversion_rate", res.rate);
                }
                if (res.date && me.frm.doc.custom_exchange_rate_date !== res.date) {
                    me.frm.set_value("custom_exchange_rate_date", res.date);
                }
            } else {
                me.frm.set_value("conversion_rate", 0);
                me.frm.set_value("custom_exchange_rate_date", null);
            }
        } finally {
            me._fetching_rate = false;
            // KHÔNG reset _last_fetch_key ở đây
            // → nếu trigger lại ngay sau, cache vẫn bảo vệ
        }
    });
}
```

### 3.6 Pattern: Reset cache khi tham số thay đổi

```javascript
company() {
    this._last_fetch_key = null;  // company đổi → exchange rate có thể đổi
    super.company();
    this.trigger_price_update();
}

// Tương tự với các field ảnh hưởng đến fetch
custom_bank() {
    this._last_fetch_key = null;  // bank đổi → lấy rate theo bank mới
    this.fetch_exchange_rate();
}
```

---

## 4. Fix chuẩn cho sales_invoice.js eupapp

Dưới đây là toàn bộ CustomController với các fix đã review:

```javascript
erpnext.accounts.CustomSalesInvoiceController = class CustomSalesInvoiceController
        extends erpnext.accounts.SalesInvoiceController {

    // ─────────────────────────────────────────────
    // LIFECYCLE
    // ─────────────────────────────────────────────

    onload() {
        super.onload();
        let me = this;
        this.frm.before_unload = () => {
            if (me._rate_debounce_timer) {
                clearTimeout(me._rate_debounce_timer);
                me._rate_debounce_timer = null;
            }
        };
        this.frm.set_query('selling_price_list', function() {
            return {
                filters: {
                    "selling": 1,
                    "currency": cur_frm.doc.currency,
                    "enabled": 1,
                }
            };
        });
    }

    // ─────────────────────────────────────────────
    // PRICING RULE
    // ─────────────────────────────────────────────

    price_list_rate(doc, cdt, cdn) {
        var item = frappe.get_doc(cdt, cdn);
        frappe.model.round_floats_in(item, ["price_list_rate", "discount_percentage"]);

        // Custom: không lấy price_list_rate từ Item Price cho Sales Invoice Item
        if (cdt == "Sales Invoice Item") {
            item.price_list_rate = 0.0;
        }

        if (in_list([
            "Quotation Item", "Sales Order Item", "Delivery Note Item",
            "Sales Invoice Item", "POS Invoice Item",
            "Purchase Invoice Item", "Purchase Order Item", "Purchase Receipt Item"
        ], cdt))
            this.apply_pricing_rule_on_item(item);
        else
            item.rate = flt(
                item.price_list_rate * (1 - item.discount_percentage / 100.0),
                precision("rate", item)
            );

        this.calculate_taxes_and_totals();
    }

    apply_pricing_rule_on_item(item) {
        let effective_item_rate = item.price_list_rate;
        let item_rate = item.rate;

        if (in_list(["Sales Order", "Quotation"], item.parenttype) && item.blanket_order_rate) {
            effective_item_rate = item.blanket_order_rate;
        }

        if (item.margin_type == "Percentage") {
            item.rate_with_margin = flt(effective_item_rate)
                + flt(effective_item_rate) * (flt(item.margin_rate_or_amount) / 100);
        } else {
            item.rate_with_margin = flt(effective_item_rate) + flt(item.margin_rate_or_amount);
        }
        item.base_rate_with_margin = flt(item.rate_with_margin) * flt(this.frm.doc.conversion_rate);

        item_rate = item.rate_with_margin
            ? flt(item.rate_with_margin, precision("rate", item))
            : item_rate;

        if (item.discount_percentage && !item.discount_amount) {
            item.discount_amount = flt(item.rate_with_margin) * flt(item.discount_percentage) / 100;
        }

        if (item.discount_amount) {
            item_rate = flt(item.rate_with_margin - item.discount_amount, precision('rate', item));
            item.discount_percentage = 100 * flt(item.discount_amount) / flt(item.rate_with_margin);
        }

        frappe.model.set_value(item.doctype, item.name, "rate", item_rate);
    }

    _set_values_for_item_list(children) {
        const items_rule_dict = {};

        for (const child of children) {
            const existing_pricing_rule = frappe.model.get_value(
                child.doctype, child.name, "pricing_rules"
            );

            for (let [key, value] of Object.entries(child)) {
                if (["doctype", "name"].includes(key)) continue;

                if (key === "price_list_rate") {
                    // Custom: ép về 0
                    value = 0.0;
                    frappe.model.set_value(child.doctype, child.name, "base_price_list_rate", 0.0);
                }

                if (key === "pricing_rules") {
                    frappe.model.set_value(child.doctype, child.name, key, value);
                }

                if (key !== "free_item_data") {
                    if (child.apply_rule_on_other_items &&
                        JSON.parse(child.apply_rule_on_other_items).length) {
                        if (!in_list(JSON.parse(child.apply_rule_on_other_items), child.item_code)) {
                            continue;
                        }
                    }
                    frappe.model.set_value(child.doctype, child.name, key, value);
                }
            }

            frappe.model.round_floats_in(
                frappe.get_doc(child.doctype, child.name),
                ["price_list_rate", "discount_percentage"]
            );

            if (!this.frm.doc.ignore_pricing_rule && existing_pricing_rule && !child.pricing_rules) {
                this.apply_price_list(frappe.get_doc(child.doctype, child.name));
            } else if (!child.pricing_rules) {
                this.remove_pricing_rule(frappe.get_doc(child.doctype, child.name));
            }

            if (child.free_item_data && child.free_item_data.length > 0) {
                this.apply_product_discount(child);
            }

            if (child.apply_rule_on_other_items &&
                JSON.parse(child.apply_rule_on_other_items).length) {
                items_rule_dict[child.name] = child;
            }
        }

        this.apply_rule_on_other_items(items_rule_dict);
        this.calculate_taxes_and_totals();
    }

    // ─────────────────────────────────────────────
    // EXCHANGE RATE — CUSTOM BANK LOGIC
    // ─────────────────────────────────────────────

    /**
     * Override get_exchange_rate để fetch theo custom_bank.
     * Không gọi super vì core dùng endpoint khác (erpnext.setup.utils.get_exchange_rate).
     */
    get_exchange_rate(transaction_date, from_currency, to_currency, callback) {
        if (this.frm.doc.custom_is_manual_exchange_rate) return;

        var args = ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"]
            .includes(this.frm.doctype) ? "for_selling" : "for_buying";

        if (!transaction_date || !from_currency || !to_currency) return;

        let company_currency = frappe.get_doc(":Company", this.frm.doc.company).default_currency;
        let bank = this.frm.doc.custom_bank;

        if (from_currency === company_currency) {
            callback({ rate: 1, date: null });
            return;
        }

        let filters = [
            ['from_currency', '=', from_currency],
            ['to_currency', '=', to_currency],
            ['date', '<=', transaction_date],
            [args, '=', 1],
        ];
        if (bank) filters.push(['bank', '=', bank]);

        frappe.call({
            method: 'eupapp.utils.get_data',
            args: {
                doctype: 'Currency Exchange',
                filters: filters,
                fields: ['exchange_rate', 'date'],
                order_by: 'date desc',
                limit: 1,
            },
            async: false,
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    callback({ rate: flt(r.message[0].exchange_rate), date: r.message[0].date });
                } else {
                    callback(null);
                }
            }
        });
    }

    /**
     * Fetch và set conversion_rate theo custom bank.
     * Có cache key để tránh fetch lặp khi trigger liên tiếp.
     */
    fetch_exchange_rate() {
        if (this.frm.doc.custom_is_manual_exchange_rate) return;
        if (this._fetching_rate) return;

        let me = this;
        let company_currency = frappe.get_doc(":Company", this.frm.doc.company).default_currency;
        let from_currency = this.frm.doc.currency;
        let posting_date = this.frm.doc.posting_date;
        let bank = this.frm.doc.custom_bank || "";

        if (!from_currency || !posting_date) return;

        let key = `${from_currency}|${posting_date}|${bank}`;
        if (this._last_fetch_key === key) return;
        this._last_fetch_key = key;

        if (from_currency === company_currency) {
            if (flt(this.frm.doc.conversion_rate) !== 1) {
                this.frm.set_value("conversion_rate", 1);
            }
            return;
        }

        this._fetching_rate = true;
        this.get_exchange_rate(posting_date, from_currency, company_currency, function(res) {
            try {
                if (res) {
                    if (flt(me.frm.doc.conversion_rate) !== flt(res.rate)) {
                        me.frm.set_value("conversion_rate", res.rate);
                    }
                    if (res.date && me.frm.doc.custom_exchange_rate_date !== res.date) {
                        me.frm.set_value("custom_exchange_rate_date", res.date);
                    }
                } else {
                    me.frm.set_value("conversion_rate", 0);
                    me.frm.set_value("custom_exchange_rate_date", null);
                }
            } finally {
                me._fetching_rate = false;
            }
        });
    }

    // ─────────────────────────────────────────────
    // CURRENCY TRIGGERS — OVERRIDE HOÀN TOÀN
    // ─────────────────────────────────────────────

    /**
     * Override hoàn toàn — KHÔNG gọi super.
     *
     * Lý do: super.currency() của SalesInvoiceController gọi super() tiếp
     * lên transaction.js, ở đó sẽ gọi get_exchange_rate() của CORE chạy
     * song song với fetch_exchange_rate() custom → double set conversion_rate.
     *
     * Các side-effect cần thiết được thực hiện thủ công bên dưới.
     */
    currency() {
        if (this._updating_currency) return;
        this._updating_currency = true;
        try {
            this.set_dynamic_labels();  // từ TransactionController, an toàn

            let company_currency = this.get_company_currency();

            if (this.frm.doc.currency === company_currency) {
                this.frm.set_value("conversion_rate", 1.0);
                // KHÔNG cần fetch, cũng không cần update price list với rate=1
            } else if (this.frm.doc.currency) {
                this.fetch_exchange_rate();
            }

            this.update_all_price_list_rate();
        } finally {
            this._updating_currency = false;
        }
    }

    /**
     * Override plc_conversion_rate — thêm guard custom_is_manual_exchange_rate
     * và guard chống loop khi set conversion_rate.
     */
    plc_conversion_rate() {
        if (this.frm.doc.price_list_currency === this.get_company_currency()) {
            this.frm.set_value("plc_conversion_rate", 1.0);
        } else if (
            this.frm.doc.price_list_currency === this.frm.doc.currency &&
            this.frm.doc.plc_conversion_rate &&
            flt(this.frm.doc.plc_conversion_rate) != 1 &&
            flt(this.frm.doc.plc_conversion_rate) != flt(this.frm.doc.conversion_rate) &&
            flt(this.frm.doc.custom_is_manual_exchange_rate) == 0 &&
            !this._setting_plc_rate  // guard chống loop
        ) {
            this._setting_plc_rate = true;
            this.frm.set_value("conversion_rate", this.frm.doc.plc_conversion_rate);
            this._setting_plc_rate = false;
        }

        if (!this.in_apply_price_list) {
            this.apply_price_list(null, true);
        }
    }

    // ─────────────────────────────────────────────
    // FIELD TRIGGERS — GỌI SUPER + RESET CACHE
    // ─────────────────────────────────────────────

    /**
     * posting_date: gọi super (để core xử lý due_date, recalculate_terms)
     * sau đó fetch exchange rate custom.
     *
     * Lưu ý: super.posting_date() của transaction.js ở cuối gọi
     * frappe.ui.form.trigger("currency") → sẽ chạy currency() của chúng ta.
     * Đó là đúng — chúng ta đã override currency() an toàn rồi.
     */
    posting_date() {
        this._last_fetch_key = null;  // reset cache, ngày đổi → cần fetch lại
        super.posting_date();         // xử lý due_date + recalculate_terms + trigger currency
        // Sau khi super xong, currency() đã fetch rồi, không cần gọi thêm
        // Chỉ cần update price list
        this.trigger_price_update();
    }

    /**
     * company: reset cache + gọi super + update price
     */
    company() {
        this._last_fetch_key = null;
        super.company();
        this.trigger_price_update();
    }

    /**
     * selling_price_list: gọi super + update price
     */
    selling_price_list() {
        super.selling_price_list();
        this.trigger_price_update();
    }

    // ─────────────────────────────────────────────
    // ITEM TRIGGERS
    // ─────────────────────────────────────────────

    item_code(doc, cdt, cdn) {
        let item = frappe.get_doc(cdt, cdn);
        if (item._processing_item_code) return;
        item._processing_item_code = true;
        try {
            super.item_code(doc, cdt, cdn);
            get_price_list_rate(doc, cdt, cdn);
        } finally {
            setTimeout(() => { delete item._processing_item_code; }, 500);
        }
    }

    batch_no(doc, cdt, cdn) {
        let item = frappe.get_doc(cdt, cdn);
        if (item._processing_batch_no) return;
        item._processing_batch_no = true;
        try {
            super.batch_no(doc, cdt, cdn);
            if (typeof get_price_list_rate === 'function') {
                get_price_list_rate(doc, cdt, cdn);
            }
        } finally {
            setTimeout(() => { delete item._processing_batch_no; }, 500);
        }
    }

    // ─────────────────────────────────────────────
    // PRICE UPDATE
    // ─────────────────────────────────────────────

    trigger_price_update() {
        if (this.frm.doc.docstatus) return;
        this.update_all_price_list_rate();
    }

    update_all_price_list_rate() {
        const me = this;
        if (me.frm.doc.docstatus) return;
        if (!me.frm.doc.items?.length) return;

        if (me._rate_debounce_timer) clearTimeout(me._rate_debounce_timer);
        me._rate_debounce_timer = setTimeout(() => {
            me._rate_request_version = (me._rate_request_version || 0) + 1;
            const current_version = me._rate_request_version;
            const doc_copy = JSON.parse(JSON.stringify(me.frm.doc));

            frappe.call({
                method: "update_all_price_list_rate",
                doc: doc_copy,
                freeze: false,
                callback: function(r) {
                    if (current_version !== me._rate_request_version) return;
                    if (r.message?.items) {
                        me._ignore_rate_trigger = true;
                        for (let row of r.message.items) {
                            let item = locals[row.doctype]?.[row.name];
                            if (!item) continue;
                            frappe.model.set_value(row.doctype, row.name, "rate", flt(row.rate));
                        }
                        me._ignore_rate_trigger = false;
                        me.calculate_taxes_and_totals();
                        me.frm.refresh_field("items");
                    }
                },
                error: function() {}
            });
        }, 300);
    }

    // ─────────────────────────────────────────────
    // VALIDATION
    // ─────────────────────────────────────────────

    _get_args(item) {
        if (!this.frm.doc.conversion_rate) this.frm.doc.conversion_rate = 1.0;
        return super._get_args(item);
    }

    validate_conversion_rate() {
        let company_currency = this.get_company_currency();
        let current_currency = this.frm.doc.currency;

        if (this._last_error_currency !== current_currency) {
            this._conversion_rate_error_thrown = false;
            this._last_error_currency = null;
        }
        if (this._conversion_rate_error_thrown) return;

        this.frm.doc.conversion_rate = flt(
            this.frm.doc.conversion_rate,
            cur_frm ? precision("conversion_rate") : 9
        );

        var conversion_rate_label = frappe.meta.get_label(
            this.frm.doc.doctype, "conversion_rate", this.frm.doc.name
        );

        if (!this.frm.doc.conversion_rate) {
            if (this.frm.doc.currency == company_currency) {
                this.frm.set_value("conversion_rate", 1);
            } else {
                $.each(this.frm.doc.items || [], function(i, row) { row.rate = 0.0; });
                this.frm.refresh_field("items");
                this._conversion_rate_error_thrown = true;
                this._last_error_currency = current_currency;
                frappe.throw(__('{0} is mandatory. Maybe Currency Exchange record is not created for {1} to {2}',
                    [conversion_rate_label, this.frm.doc.currency, company_currency]
                ));
            }
        } else {
            this._conversion_rate_error_thrown = false;
            this._last_error_currency = null;
        }
    }
};
```

---

## 5. Checklist trước khi viết custom JS

### 5.1 Phân tích

- [ ] Field nào sẽ bị ảnh hưởng?
- [ ] Method nào trong chuỗi kế thừa xử lý field đó?
- [ ] Method đó có gọi `set_value` cho field khác không? Field nào?
- [ ] Field được set đó có trigger method nào khác không?
- [ ] Có vòng lặp tiềm năng nào không? (A set B → B set A)

### 5.2 Quyết định override strategy

| Câu hỏi | Nếu Có | Nếu Không |
|---------|--------|-----------|
| Core method có logic cần giữ lại? | Gọi super, thêm logic trước/sau | Override hoàn toàn |
| Core method gọi fetch/set field gây conflict? | Override hoàn toàn | Gọi super an toàn |
| Method bị trigger liên tiếp từ nhiều nơi? | Thêm guard + debounce | Không cần guard |
| Kết quả method phụ thuộc tham số có thể cache? | Dùng cache key | Không cần cache |

### 5.3 Kiểm tra sau khi viết

- [ ] Mọi method có `set_value` đều có guard (hoặc đã chắc chắn không loop)
- [ ] Không có 2 nơi cùng set một field (Controller method + frappe.ui.form.on)
- [ ] Method async sử dụng version counter thay vì boolean flag với `.then()`
- [ ] Các method "tốn kém" (gọi server) có debounce
- [ ] Cache key bao gồm ĐẦY ĐỦ các tham số ảnh hưởng kết quả
- [ ] Cache bị reset khi tham số thay đổi

---

## 6. Các lỗi phổ biến và cách nhận biết

### Lỗi: Field "nhảy loạn" liên tục khi load form

**Nguyên nhân thường gặp**: Hai method cùng set field A → B → A.

**Cách debug**:
```javascript
// Thêm tạm vào method nghi ngờ để trace call stack
methodName() {
    console.trace('methodName called');
    // ... logic
}
```

### Lỗi: Field bị reset về giá trị cũ sau khi người dùng nhập

**Nguyên nhân**: Có debounced timer hoặc async callback đang chạy ngầm, khi resolve nó ghi đè giá trị mới.

**Fix**: Dùng version counter — nếu giá trị đã thay đổi (version mới hơn), bỏ qua kết quả cũ.

### Lỗi: Exchange rate không cập nhật khi đổi bank

**Nguyên nhân**: `_last_fetch_key` chưa bao gồm `bank` trong key, hoặc key không bị reset khi bank thay đổi.

**Fix**: Đảm bảo `frappe.ui.form.on` handler của `custom_bank` gọi `reset key + fetch`.

### Lỗi: `super.methodName is not a function`

**Nguyên nhân**: Gọi `super` bên trong arrow function `() => {}` — `super` không hoạt động trong arrow function.

**Fix**: Dùng regular function hoặc lưu reference trước.
```javascript
// SAI
someMethod() {
    setTimeout(() => { super.someMethod(); }, 0);  // lỗi
}

// ĐÚNG
someMethod() {
    const superMethod = super.someMethod.bind(this);
    setTimeout(() => { superMethod(); }, 0);
}
```

### Lỗi: Guard `_flag` không hoạt động với `frappe.run_serially`

**Nguyên nhân**: `frappe.run_serially` chạy mỗi step trong một microtask riêng — flag bị reset giữa các step.

**Fix**: Đặt flag bên ngoài `run_serially`, reset ở step cuối cùng.

---

## 7. Tham khảo nhanh

### Các method hay bị override sai

| Method | Vấn đề thường gặp | Best practice |
|--------|------------------|---------------|
| `currency()` | Core gọi get_exchange_rate song song | Override hoàn toàn nếu custom exchange rate logic |
| `posting_date()` | Trigger currency → cascade | Gọi super (an toàn), thêm reset cache trước |
| `conversion_rate()` | apply_price_list → plc_conversion_rate → loop | Override + guard `_setting_plc_rate` |
| `plc_conversion_rate()` | Set conversion_rate → conversion_rate() → loop | Override + guard |
| `item_code()` | Async callback, có thể gọi lại chính nó | Guard trên item, setTimeout reset |
| `company()` | Reset nhiều thứ, dễ miss | Gọi super, reset cache key sau |

### Các flag nội bộ của core cần biết

| Flag | Ý nghĩa |
|------|---------|
| `this.in_apply_price_list` | Đang trong `apply_price_list()` — dùng để tránh reenter |
| `this.frm.updating_party_details` | Đang cập nhật party — một số method bỏ qua khi flag này bật |
| `this.frm.doc.__onload.load_after_mapping` | Doc được load từ mapped doc — skip một số triggers |
| `frappe.flags.dont_fetch_price_list_rate` | Tắt auto-fetch price list rate |
| `frappe.flags.hide_serial_batch_dialog` | Tắt dialog chọn batch/serial khi add item |
