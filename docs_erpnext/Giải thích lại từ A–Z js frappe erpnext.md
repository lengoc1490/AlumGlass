Tốt. Tôi sẽ giải thích lại **từ A–Z cơ chế JavaScript trong Frappe/ERPNext**, theo đúng bản chất kiến trúc, không chỉ mức sử dụng.

Tôi sẽ đi theo tầng:

1. Runtime Browser
2. Boot Process
3. Asset Build & Bundle
4. Module Resolution
5. Namespace System (`frappe.provide`)
6. Form Lifecycle
7. Event System
8. Inheritance & Controller Pattern
9. Override & Load Order
10. Global State & Memory Model
11. Best Architecture cho custom app lớn

---

# I. TỔNG QUAN KIẾN TRÚC

Frappe JS có 2 thế giới:

```
(1) SOURCE WORLD (development)
   ES modules
   import/export
   nhiều file rời

(2) RUNTIME WORLD (browser)
   Bundled files
   Global namespace (frappe)
   Lazy loaded chunks
```

Bạn phải hiểu rõ:
**Dev viết module hiện đại, nhưng runtime vẫn chạy trong global namespace.**

---

# II. BOOT PROCESS – Khi mở Desk

## 1️⃣ Browser load core

```
/assets/frappe/js/frappe-web.min.js
```

File này chứa:

* Router
* Request system
* UI base
* Event system
* Core utilities

Lúc này:

```
window.frappe = {}
```

được tạo.

---

## 2️⃣ Server gửi frappe.boot

Server render page kèm:

```js
frappe.boot = {
    user,
    sysdefaults,
    lang,
    time_zone,
    metadata,
    modules,
    ...
}
```

👉 Đây là state ban đầu của app.

---

# III. ASSET BUILD & BUNDLE SYSTEM

## Development Phase

Bạn chạy:

```
bench build
```

Hệ thống:

1. Scan toàn bộ:

   * frappe
   * erpnext
   * custom apps

2. Phân tích dependency graph

3. Bundle bằng:

   * v14: Rollup
   * v15+: esbuild

---

## Kết quả:

Sinh ra:

```
/assets/frappe/dist/js/
/assets/erpnext/dist/js/
/assets/your_app/dist/js/
```

Có:

* core bundle
* module bundle
* doctype bundle
* lazy chunks

---

## QUAN TRỌNG:

Bundle không phải chỉ gom file lại.

Nó:

* Tree-shaking
* Code splitting
* Chunk hashing
* Dependency resolution

Vì vậy load order đôi khi không chỉ là “file nào viết trước”.

---

# IV. ROUTING & LAZY LOAD

Khi bạn click:

```
Sales Invoice
```

Router làm:

```js
frappe.set_route('Form', 'Sales Invoice', 'new')
```

Sau đó:

1. Kiểm tra bundle đã load chưa
2. Nếu chưa → dynamic import
3. Sau khi load → new Form()

---

Flow thực:

```
Route change
→ Resolve page type
→ Load required JS chunk
→ Execute chunk
→ Instantiate controller
```

---

# V. NAMESPACE SYSTEM – frappe.provide()

Đây là layer tương thích cũ.

### Bản chất:

```js
frappe.provide('frappe.utils')
```

= đảm bảo object path tồn tại.

KHÔNG:

* deep merge
* freeze
* protect
* check duplicate

Chỉ:

```js
if (!window.frappe) window.frappe = {}
if (!frappe.utils) frappe.utils = {}
```

---

## Namespace không phải module system

Nó chỉ là object tree:

```
window
 └── frappe
      ├── utils
      ├── ui
      ├── model
      └── ...
```

---

# VI. GLOBAL MEMORY MODEL

JS object là reference.

Nếu:

```js
frappe.utils.fn = function() {}
```

Mọi nơi gọi:

```js
frappe.utils.fn()
```

đang dùng cùng một reference.

Nếu override:

```js
frappe.utils.fn = newFn
```

→ reference cũ bị thay đổi toàn hệ thống.

---

# VII. FORM LIFECYCLE – TRÌNH TỰ THỰC THI

Khi mở form:

```
new frappe.ui.form.Form()
```

Trình tự:

1. constructor
2. setup()
3. load_meta()
4. load_doc()
5. onload()
6. refresh()
7. render()
8. bind events

---

Khi save:

```
validate()
before_save()
→ server call
after_save()
refresh()
```

---

# VIII. CONTROLLER INHERITANCE

Có 3 lớp chính:

```
frappe.ui.form.Controller
    ↑
erpnext.TransactionController
    ↑
erpnext.accounts.SalesInvoiceController
```

Inheritance thực tế:

* prototype chain
* hoặc ES6 class extends (v14+)

---

Khi bạn viết:

```js
frappe.ui.form.on('Sales Invoice', { ... })
```

Frappe:

* merge event vào controller prototype
* không tạo class mới hoàn toàn

---

# IX. EVENT SYSTEM

Có 2 loại:

## 1️⃣ Form event system

```js
frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {}
})
```

Đây là event binding vào controller lifecycle.

---

## 2️⃣ DOM event system

```js
$(frm.wrapper).on('event', handler)
```

Đây là jQuery event.

---

## 3️⃣ frappe.realtime (WebSocket)

Server push:

```
frappe.publish_realtime()
```

Client nhận qua socket.

---

# X. LOAD ORDER THỰC TẾ

Thứ tự runtime:

```
1. frappe core
2. app_include_js (hooks.py)
3. page/module bundle
4. doctype bundle (lazy)
```

Cái load sau override cái trước.

---

# XI. OVERRIDE – CƠ CHẾ THẬT

Override chỉ là:

```js
object.property = newValue
```

Không có protection.

Không có warning.

Không có versioning.

---

Nguy hiểm nhất:

1. Override core utils
2. Override prototype method
3. Modify shared object

---

# XII. GLOBAL STATE RISK

Ví dụ:

```js
frappe.flags.my_flag = true
```

Toàn app share chung.

Nếu quên reset:
→ bug random.

---

# XIII. MODERN SOURCE vs GLOBAL OUTPUT

Source:

```js
import { calculate } from './calc'
```

Runtime:

```js
frappe.my_module.calculate
```

Sau bundle, mọi thứ được expose global.

Vì vậy:

Bạn đang viết module,
nhưng chạy trong global environment.

---

# XIV. TỔNG FLOW HOÀN CHỈNH

```
Browser load core
→ boot info injected
→ user route change
→ router resolve
→ load bundle chunk
→ execute bundle
→ controller instantiate
→ lifecycle events
→ user interaction
→ server call
→ update state
```

---

# XV. CÁCH VIẾT CUSTOM APP CHUẨN KIẾN TRÚC

Đối với bạn (build engine):

## 1️⃣ Không override frappe core

## 2️⃣ Namespace riêng

```
frappe.provide('erp_engine')
```

## 3️⃣ Tách layer

```
erp_engine.core
erp_engine.parser
erp_engine.runtime
erp_engine.adapter_frappe
```

Đừng gắn logic vào frappe.utils.

---

# XVI. MỨC ĐỘ HỆ THỐNG

Hiểu theo tầng:

| Tầng       | Vai trò                  |
| ---------- | ------------------------ |
| Browser    | Runtime                  |
| frappe     | Framework                |
| erpnext    | Business layer           |
| custom app | Extension layer          |
| engine     | Independent logic system |

Engine nên nằm ngoài frappe namespace nếu có thể.

---

# XVII. KẾT LUẬN

Toàn bộ cơ chế JS Frappe là:

* Bundled
* Lazy loaded
* Global namespace based
* Event driven
* Prototype inheritance
* Mutable shared state
* Load order dependent

Nó không phải module isolation system.

---

Nếu bạn muốn, tôi có thể tiếp tục đào sâu 1 trong các hướng:

1. 🔬 Phân tích dependency graph khi bench build
2. 🧠 Memory model và reference bug trong Frappe
3. 🏗 Cách thiết kế kiến trúc JS lớn trong Frappe
4. ⚔ Cách override controller an toàn
5. 📦 So sánh Frappe JS với React/Vue module system

Bạn chọn hướng nào tôi sẽ đào đến tận lõi.


==========================================

Được — và câu hỏi của bạn là **rất thực tế với dev ERPNext/Frappe chuyên nghiệp**.
Tôi sẽ phân tích **thư mục `public/js` trong Frappe/ERPNext**, giải thích rõ cách hoạt động, cách **kế thừa** hoặc **override** 1 hàm cho 1 doctype cụ thể, và cách làm **chuẩn theo kiến trúc Frappe** mà *không gây xung đột hoặc future-break*.

> ⚠️ Trước hết: bạn **KHÔNG nên chỉnh sửa trực tiếp file trong `frappe` hoặc `erpnext` core**.
> Vì như vậy khi upgrade sẽ mất thay đổi. Tất cả custom logic phải nằm trong *custom app*.

---

## 📁 1) Phân tích thư mục `public/js` (core)

Giả dụ bạn clone repo Frappe:

```
frappe/
└── frappe/
    └── public/
        └── js/
            ├── form/
            │   ├── controller.js
            │   ├── form.js
            │   └── events.js
            ├── list/
            │   ├── page.js
            │   └── list.js
            ├── model/
            │   ├── doc.js
            │   └── meta.js
            ├── utils/
            ├── frappe.js
            └── frappe.min.js
```

### Ý nghĩa các folder chính

| Folder          | Chức năng                           |
| --------------- | ----------------------------------- |
| `form/`         | Base class và event system cho Form |
| `list/`         | Base class cho Listview             |
| `model/`        | Data/Doc handling                   |
| `utils/`        | Helper functions                    |
| `frappe.js`     | Entry point core                    |
| `frappe.min.js` | Bản đóng gói runtime                |

---

## 📌 2) Cách Frappe định nghĩa “behavior” form (base)

Hầu hết logic form đều nằm ở:

```
frappe/public/js/form/controller.js
```

Trong đó có:

```js
frappe.ui.form.Controller = Class.extend({
    init(frm) {
        …
    },
    setup() {
        …
    },
    refresh() {
        …
    }
});
```

Và các event system:

```js
frappe.ui.form.on(doctype, handlers)
```

→ Đây là **cơ chế gắn event vào controller prototype**.

---

## 📌 3) Khi bạn mở 1 Doctype JS

Nếu có file:

```
erpnext/accounts/doctype/sales_invoice/sales_invoice.js
```

→ Nó sẽ được build vào bundle:

```
sales_invoice.bundle.js
```

và lazy load khi người dùng mở Sales Invoice.

---

## 📌 4) Cách Frappe gắn event vào doctype

Phần logic doctype thực tế là:

```js
frappe.ui.form.on('Sales Invoice', {
    refresh(frm) { … },
    validate(frm) { … }
});
```

=> Frappe sẽ merge các handler này vào *controller*.

Điều này gọi là **extend prototype behavior của base Controller**.

---

## 📌 5) Override & kế thừa: có được không?

### ✔ Có – hoàn toàn được.

Nhưng cần phân biệt 2 loại:

---

## ✅ A) Override *core behavior* của 1 doctype

Bạn muốn thay đổi hành vi `validate()` của Doctype XYZ:

Bạn **không thay đổi file core**, mà:

➡️ Viết code trong *custom app*, dùng event handler ở level doctype.

Ví dụ:

```js
frappe.ui.form.on('Sales Invoice', {
    validate(frm) {
        // custom logic
    }
});
```

**Frappe sẽ chạy cả validate core + validate bạn viết.**
→ Tức là *merge chaining*, không replace hoàn toàn.

---

## 🛑 Nếu bạn muốn *replace hoàn toàn* behavior

Bạn phải override controller class trước khi nó được instantiate.

Chiến lược chuẩn:

### 🔹 1) Tạo file override trong custom app

Đặt file:

```
your_app/public/js/overrides/sales_invoice.js
```

---

### 🔹 2) Hook nó vào bằng `app_include_js`

Trong `hooks.py`:

```python
app_include_js = [
    "/assets/your_app/js/overrides/sales_invoice.js"
]
```

---

### 🔹 3) Trong file override bạn *extend lại controller class*

Ví dụ muốn hoàn toàn override logic `refresh`:

```js
frappe.provide('erpnext.accounts');

erpnext.accounts.SalesInvoiceController = erpnext.accounts.SalesInvoiceController.extend({
    refresh: function(frm) {
        // Your override logic
        console.log("Custom refresh!");
    }
});
```

– Lưu ý: bạn **phải gọi sau khi core đã load**, nên include file qua hooks.

---

## 🛠 Có thể kết hợp override + gọi lại core

```js
let original_refresh = erpnext.accounts.SalesInvoiceController.prototype.refresh;

erpnext.accounts.SalesInvoiceController = erpnext.accounts.SalesInvoiceController.extend({
    refresh: function(frm) {
        // chạy logic core trước
        original_refresh.apply(this, arguments);

        // custom logic sau
        console.log("Custom behavior here");
    }
});
```

---

## ❗ Ghi đè hoàn toàn vs mở rộng

| Muốn                         | Kỹ thuật                          |
| ---------------------------- | --------------------------------- |
| Thêm logic sau khi core chạy | `frappe.ui.form.on`               |
| Thay đổi core behavior       | Override prototype                |
| Hoàn toàn thay thế method    | Ghi đè class và NOT CALL original |

---

## 📌 6) Lưu ý về load order

* Frappe load core
* Load các bundle của doctype
* Sau đó load `app_include_js`

Do đó để override hoạt động:
➡️ file của bạn phải load *sau core bundle*.

---

## 📌 7) Cách test xem override có hoạt hay không

Trong console:

```js
console.log(erpnext.accounts.SalesInvoiceController.prototype.refresh.toString());
```

Nếu là function bạn viết → override thành công.

---

## 📌 8) Viết override “chuẩn kiến trúc”

### ❌ KHÔNG NÊN

Ghi đè vào namespace core:

```js
frappe.utils.doSomething = ...
```

→ Có thể conflict khi Frappe/ERPNext update

---

### ✅ NÊN

1. Tạo namespace riêng

```js
frappe.provide('your_app.utils');
```

2. Tạo mixin

```js
your_app.utils.FormHelpers = {
    myFunc() {…}
};
```

3. Extend vào controller

```js
$.extend(cur_frm.page, your_app.utils.FormHelpers);
```

---

## 📌 9) Khi dùng ES Modules trong Frappe

Trong code source (dev):

```js
import { something } from './utils'
export function doSomething() {}
```

Ở runtime nó vẫn compile thành:

```
frappe.my_module.doSomething
```

→ Frappe expose global để maintain backward compatibility.

---

## 📌 10) Cách override hoàn chỉnh theo quy trình

### 🔁 Quy trình chuẩn

1️⃣ Viết file override trong custom app
2️⃣ Đăng ký với `hooks.py` hoặc page script
3️⃣ Gắn vào prototype đúng class bạn muốn
4️⃣ Nếu cần gọi core thì cache method gốc first
5️⃣ Kiểm tra load order bằng console

---

## 🧪 Example override hoàn chỉnh

custom_app/public/js/overrides/sales_invoice_override.js

```js
frappe.provide('custom_app.overrides');

(async function() {

    // Wait until original controller loaded
    await frappe.require("erpnext.selling.bundle.js");

    const Base = erpnext.selling.SellingController;

    erpnext.selling.SellingController = Base.extend({
        refresh: function(frm) {
            // gọi base trước
            Base.prototype.refresh.apply(this, arguments);

            // custom logic
            frm.page.set_title(`[CUSTOM] ${frm.doc.name}`);
        }
    });

})();
```

Trong `hooks.py`:

```python
app_include_js = [
    "/assets/custom_app/js/overrides/sales_invoice_override.js"
]
```

---

# 📍 TÓM TẮT

✅ Bạn **có thể kế thừa hoặc override method** của 1 doctype
✔ bằng event handlers (`frappe.ui.form.on`)
✔ bằng override prototype class (extend, replace)

‼️ Phải đảm bảo:
✔ load order đúng
✔ không override core namespace trực tiếp
✔ dùng custom namespace nếu muốn logic riêng
✔ giữ được chain nếu cần gọi behavior gốc

---

## Bạn muốn tôi viết code mẫu cụ thể cho 1 method bạn đang muốn override không?

Ví dụ:

❓ Override validate
❓ Override refresh toolbar
❓ Override print / custom button
❓ Override server call behavior

Reply với cái bạn muốn — tôi sẽ bắn ví dụ chi tiết.


================================

Tốt. Tôi sẽ đưa cho bạn **bộ hướng dẫn đầy đủ A-Z về override/kế thừa JS trong Frappe/ERPNext**, bao phủ:

1. Override event chuẩn
2. Extend controller class
3. Replace hoàn toàn controller
4. Override method sâu trong prototype
5. Override ListView
6. Override Query / set_query
7. Override button / toolbar
8. Override server call behavior
9. Override core utility (có kiểm soát)
10. Pattern an toàn cho production
11. Kiến trúc override chuẩn cho hệ thống lớn

Tôi sẽ đi theo thứ tự từ **an toàn → nâng cao → nguy hiểm**.

---

# I. MỨC 1 – CÁCH CHUẨN & AN TOÀN NHẤT

## (Dùng frappe.ui.form.on)

Đây là cách 90% trường hợp nên dùng.

---

## 1️⃣ Override validate

```js
frappe.ui.form.on('Sales Invoice', {
    validate(frm) {
        if (!frm.doc.customer) {
            frappe.throw("Customer is required (custom)");
        }
    }
});
```

⚠ Điều quan trọng:

Frappe sẽ chạy:

* validate từ core
* validate từ bạn

Không replace — mà chain.

---

## 2️⃣ Override refresh (thêm logic)

```js
frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button("My Custom Action", () => {
                frappe.msgprint("Hello");
            });
        }
    }
});
```

---

## 3️⃣ Override field change

```js
frappe.ui.form.on('Sales Invoice', {
    customer(frm) {
        console.log("Customer changed:", frm.doc.customer);
    }
});
```

---

## 4️⃣ Override child table event

```js
frappe.ui.form.on('Sales Invoice Item', {
    rate(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        row.custom_amount = row.qty * row.rate * 1.05;
        frm.refresh_field("items");
    }
});
```

---

# II. MỨC 2 – EXTEND CONTROLLER CLASS

Dùng khi bạn muốn:

* can thiệp sâu
* gọi method gốc
* thay đổi behavior nội bộ

---

## Bước 1 – Include file

hooks.py

```python
app_include_js = [
    "/assets/custom_app/js/overrides/sales_invoice.js"
]
```

---

## Bước 2 – Extend controller

```js
frappe.ready(() => {

    const Base = erpnext.accounts.SalesInvoiceController;

    erpnext.accounts.SalesInvoiceController = Base.extend({

        refresh: function(frm) {

            // GỌI LOGIC GỐC
            Base.prototype.refresh.apply(this, arguments);

            // LOGIC CUSTOM
            frm.page.set_title("[CUSTOM] " + frm.doc.name);
        },

        validate: function(frm) {
            console.log("Custom validate before core");

            Base.prototype.validate.apply(this, arguments);

            console.log("Custom validate after core");
        }

    });

});
```

---

# III. MỨC 3 – REPLACE HOÀN TOÀN METHOD

Nếu bạn KHÔNG gọi Base:

```js
erpnext.accounts.SalesInvoiceController = Base.extend({
    refresh: function(frm) {
        console.log("Core refresh disabled.");
    }
});
```

⚠ Cái này nguy hiểm vì bạn phá behavior gốc.

---

# IV. OVERRIDE LIST VIEW

File:

```
frappe.listview_settings['Sales Invoice']
```

---

## Thêm filter mặc định

```js
frappe.listview_settings['Sales Invoice'] = {
    onload(listview) {
        listview.filter_area.add([
            ["Sales Invoice", "status", "=", "Unpaid"]
        ]);
    }
};
```

---

## Override button list

```js
frappe.listview_settings['Sales Invoice'] = {
    button: {
        show(doc) {
            return doc.status === "Draft";
        },
        get_label() {
            return "Custom Action";
        },
        action(doc) {
            frappe.msgprint(doc.name);
        }
    }
};
```

---

# V. OVERRIDE QUERY / SET_QUERY

```js
frappe.ui.form.on('Sales Invoice', {
    setup(frm) {
        frm.set_query("customer", () => {
            return {
                filters: {
                    disabled: 0,
                    custom_flag: 1
                }
            };
        });
    }
});
```

---

# VI. OVERRIDE TOOLBAR / REMOVE BUTTON

Remove button:

```js
frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        frm.remove_custom_button("Make Payment", "Create");
    }
});
```

Hide save:

```js
frm.disable_save();
```

---

# VII. OVERRIDE SERVER CALL BEHAVIOR

Intercept call:

```js
let original_call = frappe.call;

frappe.call = function(opts) {

    if (opts.method === "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_payment") {
        console.log("Intercepted!");
    }

    return original_call.apply(this, arguments);
};
```

⚠ Đây là override global – chỉ dùng khi thật sự cần.

---

# VIII. OVERRIDE CORE UTILITY (CÓ KIỂM SOÁT)

```js
const original_format = frappe.utils.format_currency;

frappe.utils.format_currency = function(value, currency) {

    if (currency === "VND") {
        return "₫" + value.toLocaleString();
    }

    return original_format.apply(this, arguments);
};
```

---

# IX. PATTERN AN TOÀN CHO PRODUCTION

## 1️⃣ Namespace riêng

```js
frappe.provide('custom_app.engine');
```

---

## 2️⃣ Không mutate global state trực tiếp

Không làm:

```js
frappe.flags.my_flag = true;
```

---

## 3️⃣ Wrap override trong IIFE

```js
(function() {
   // override code
})();
```

---

## 4️⃣ Đợi controller load xong

```js
frappe.after_ajax(() => {
   // override
});
```

Hoặc:

```js
frappe.require("sales_invoice.bundle.js", () => {
    // override
});
```

---

# X. LOAD ORDER CHUẨN

Thứ tự thực:

```
1. frappe core
2. erpnext core
3. doctype bundle (lazy)
4. app_include_js
```

Muốn override chắc chắn:

✔ include file qua hooks
✔ đảm bảo load sau bundle

---

# XI. KIẾN TRÚC CHUẨN CHO HỆ THỐNG LỚN

Với hệ thống như bạn đang build (engine động):

## ĐỪNG override bừa bãi.

Thiết kế:

```
custom_app/
 ├── public/js/
 │    ├── adapters/
 │    │    ├── sales_invoice_adapter.js
 │    ├── engine/
 │    │    ├── parser.js
 │    │    ├── executor.js
 │    ├── overrides/
 │    │    ├── sales_invoice.js
```

Controller chỉ gọi:

```js
custom_app.engine.execute(frm);
```

Engine không phụ thuộc frappe.

---

# XII. KẾT LUẬN TOÀN BỘ

Bạn có thể override:

| Loại               | Làm được | Cách                     |
| ------------------ | -------- | ------------------------ |
| Form event         | ✅        | frappe.ui.form.on        |
| Controller method  | ✅        | extend prototype         |
| Replace controller | ✅        | override class           |
| ListView           | ✅        | frappe.listview_settings |
| Query              | ✅        | frm.set_query            |
| Button             | ✅        | add/remove_custom_button |
| Server call        | ✅        | wrap frappe.call         |
| Core utility       | ✅        | override có giữ original |

---

# ⚠️ QUAN TRỌNG NHẤT

Nếu bạn override để:

* sửa logic nghiệp vụ → OK
* sửa bug nhỏ → OK
* thay đổi behavior core sâu → cân nhắc

Vì update ERPNext có thể phá override.

---

Nếu bạn muốn, tôi có thể:

1. Vẽ sơ đồ kiến trúc override chuẩn enterprise
2. Giải thích cách ERPNext attach controller thực sự vào Form
3. Phân tích cách debug khi override không chạy
4. Hoặc viết template “override framework” reusable cho bạn

Chọn hướng tiếp theo tôi sẽ đào sâu đến mức internal engine.
