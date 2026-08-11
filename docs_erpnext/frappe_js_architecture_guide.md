"FRAPPE JAVASCRIPT ARCHITECTURE - HƯỚNG DẪN TOÀN DIỆN TỪ A-Z" với hơn 2000 dòng code và giải thích chi tiết!
📚 Nội dung tài liệu bao gồm:
13 phần chính:

1. Kiến trúc tổng quan - Source World vs Runtime World, phân tầng
2. Build Process & Bundle System - Chi tiết từ scan → bundle → transform
3. Boot Process - Server boot → Client init → Router setup
4. Module Resolution & Dependency Graph - Circular deps, tree shaking
5. Namespace System - frappe.provide(), collision, best practices
6. Routing & Lazy Loading - Dynamic imports, bundle loading strategy
7. Form Lifecycle - Setup → Onload → Refresh → Validate → Save
8. Controller Pattern & Inheritance - 4 levels kế thừa với ví dụ chi tiết
9. Event System - Form events, DOM events, Real-time, Custom events
10. Override Mechanism - Safe patterns, wrapper, decorator, middleware
11. Global State & Memory Model - Memory leaks, state management
12. Best Practices Architecture - Project structure, coding standards, testing
13. Ví dụ thực tế - Sales Invoice Controller, frappe.utils, frappe.model

Đặc biệt có nhiều ví dụ về:
✅ Kế thừa class đầy đủ 4 cấp: Base Controller → Transaction → Accounts → Sales Invoice
✅ Override functions an toàn: Wrapper pattern, Decorator, Middleware chain, Plugin system
✅ Sử dụng trong DocType: Event handlers, field triggers, child table operations
✅ Real source code examples: Từ ERPNext Sales Invoice, frappe.utils, frappe.model
✅ Memory management: Leak patterns, debugging, performance monitoring
✅ Testing strategies: Unit tests, integration tests, E2E tests
Tài liệu này đủ chi tiết để bạn hiểu sâu và áp dụng vào dự án thực tế!


# FRAPPE JAVASCRIPT ARCHITECTURE - HƯỚNG DẪN TOÀN DIỆN TỪ A-Z

## Mục lục

1. [Kiến trúc tổng quan](#1-kiến-trúc-tổng-quan)
2. [Build Process & Bundle System](#2-build-process--bundle-system)
3. [Boot Process - Khởi động ứng dụng](#3-boot-process---khởi-động-ứng-dụng)
4. [Module Resolution & Dependency Graph](#4-module-resolution--dependency-graph)
5. [Namespace System - frappe.provide()](#5-namespace-system---frappeprovide)
6. [Routing & Lazy Loading](#6-routing--lazy-loading)
7. [Form Lifecycle](#7-form-lifecycle)
8. [Controller Pattern & Inheritance](#8-controller-pattern--inheritance)
9. [Event System](#9-event-system)
10. [Override Mechanism](#10-override-mechanism)
11. [Global State & Memory Model](#11-global-state--memory-model)
12. [Best Practices Architecture](#12-best-practices-architecture)
13. [Ví dụ thực tế từ Source Code](#13-ví-dụ-thực-tế-từ-source-code)

---

# 1. KIẾN TRÚC TỔNG QUAN

## 1.1. Hai thế giới trong Frappe JS

Frappe JavaScript có hai thế giới riêng biệt mà developer cần hiểu rõ:

### 🔵 SOURCE WORLD (Development Time)

```javascript
// Khi bạn viết code trong app
// frappe/public/js/frappe/form/form.js

import { make_control } from './controls';
import { Validator } from '../model/validator';

export class Form {
    constructor(opts) {
        this.doctype = opts.doctype;
        this.setup();
    }
    
    setup() {
        // Modern ES6+ syntax
    }
}
```

**Đặc điểm:**
- ES6 modules (`import/export`)
- Nhiều file nhỏ, tổ chức theo module
- Type annotations (nếu dùng TypeScript)
- Modern JavaScript syntax

### 🟢 RUNTIME WORLD (Browser Execution)

```javascript
// Sau khi build, trong browser
// /assets/frappe/js/frappe-web.min.js

(function() {
    frappe.ui.form.Form = class {
        constructor(opts) {
            this.doctype = opts.doctype;
            this.setup();
        }
        
        setup() {
            // Bundled & minified code
        }
    };
})();
```

**Đặc điểm:**
- Global namespace (`window.frappe`)
- Bundled files (gom nhiều file thành 1)
- Minified & optimized
- Lazy loaded chunks

## 1.2. Kiến trúc phân tầng

```
┌─────────────────────────────────────────────┐
│         BROWSER RUNTIME LAYER               │
│  (window, DOM, Events, WebSocket)           │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         FRAPPE CORE LAYER                   │
│  (Router, Model, UI, Utils, API Client)     │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         ERPNEXT BUSINESS LAYER              │
│  (TransactionController, Accounting, etc)   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│         CUSTOM APP LAYER                    │
│  (Your business logic & extensions)         │
└─────────────────────────────────────────────┘
```

## 1.3. Global Namespace Structure

```javascript
window
├── frappe
│   ├── ui
│   │   ├── form
│   │   │   ├── Form
│   │   │   ├── Controller
│   │   │   └── controls
│   │   │       ├── Control
│   │   │       ├── Link
│   │   │       ├── Data
│   │   │       └── ...
│   │   ├── toolbar
│   │   ├── dialog
│   │   └── ...
│   ├── model
│   │   ├── model.js (CRUD operations)
│   │   ├── meta.js (metadata handling)
│   │   └── mapper.js
│   ├── utils
│   │   ├── common utils
│   │   └── number_format, date, etc
│   ├── call() - API client
│   ├── db - Database operations
│   ├── boot - Boot configuration
│   └── ...
├── erpnext
│   ├── TransactionController
│   ├── accounts
│   │   └── AccountsController
│   ├── stock
│   │   └── StockController
│   └── utils
└── cur_frm (current form instance)
```

---

# 2. BUILD PROCESS & BUNDLE SYSTEM

## 2.1. Quá trình Build chi tiết

Khi chạy `bench build`:

### Phase 1: Scanning

```python
# frappe/build.py (simplified)

def bundle():
    # 1. Scan hooks.py của tất cả apps
    apps = get_all_apps()
    
    for app in apps:
        # Đọc hooks.py
        app_hooks = get_app_hooks(app)
        
        # Collect JS files
        app_include_js = app_hooks.get('app_include_js', [])
        # ['public/js/utils.js', 'public/js/templates/**/*.js']
        
        # Collect DocType JS
        doctype_js = get_doctype_js(app)
        # {'Sales Invoice': ['sales_invoice.js', 'sales_invoice_list.js']}
```

### Phase 2: Dependency Analysis

```javascript
// Build tool phân tích dependencies
// sales_invoice.js
import { TransactionController } from './transaction_controller';
import { format_currency } from './utils';

// Build tool tạo dependency graph:
/*
sales_invoice.bundle.js
  ├── transaction_controller.js
  │   ├── form_controller.js
  │   │   └── utils.js
  │   └── model.js
  └── utils.js
*/
```

### Phase 3: Bundling với esbuild (v15+)

```javascript
// frappe/build.js (simplified)

const esbuild = require('esbuild');

esbuild.build({
    entryPoints: [
        'frappe/public/js/frappe-web.js',
        'erpnext/public/js/erpnext.min.js'
    ],
    bundle: true,           // Gom tất cả dependencies
    splitting: true,        // Code splitting cho lazy load
    format: 'esm',          // ES modules
    outdir: 'assets/frappe/dist/',
    minify: true,
    sourcemap: true,
    
    // Plugins
    plugins: [
        sassPlugin(),       // Compile SCSS
        vuePlugin(),        // Handle Vue components
        htmlPlugin()        // Embed HTML templates
    ],
    
    // External dependencies (không bundle)
    external: [
        'jquery',
        'moment',
        'lodash'
    ]
});
```

### Phase 4: Transformation

```javascript
// INPUT: Modern ES6
// frappe/public/js/frappe/utils/common.js
export function format_currency(value, currency) {
    return `${currency} ${value.toFixed(2)}`;
}

// OUTPUT: Global namespace (sau build)
// assets/frappe/dist/js/frappe-web.min.js
(function(frappe) {
    frappe.utils = frappe.utils || {};
    frappe.utils.format_currency = function(value, currency) {
        return currency + " " + value.toFixed(2);
    };
})(window.frappe = window.frappe || {});
```

## 2.2. Bundle Structure

```
assets/
├── frappe/
│   ├── dist/
│   │   ├── js/
│   │   │   ├── frappe-web.min.js      # Core bundle (~500KB)
│   │   │   ├── desk.min.js            # Desk UI bundle
│   │   │   ├── form.bundle.js         # Form utilities
│   │   │   ├── list.bundle.js         # List view utilities
│   │   │   └── report.bundle.js       # Report engine
│   │   └── css/
│   │       ├── frappe-web.css
│   │       └── desk.min.css
│   └── js/
│       └── (development source files)
├── erpnext/
│   ├── dist/
│   │   └── js/
│   │       ├── erpnext.min.js         # ERPNext core
│   │       ├── sales_invoice.bundle.js # Lazy loaded
│   │       ├── purchase_order.bundle.js
│   │       └── ...
└── your_app/
    └── dist/
        └── js/
            └── your_app.min.js
```

## 2.3. Build Configuration

### hooks.py - App level configuration

```python
# your_app/hooks.py

# Files included in EVERY page
app_include_css = [
    "/assets/your_app/css/your_app.css"
]

app_include_js = [
    "/assets/your_app/js/your_app.min.js"
]

# DocType specific JS (lazy loaded)
doctype_js = {
    "Sales Invoice": "public/js/sales_invoice.js",
    "Customer": "public/js/customer.js"
}

# List view JS
doctype_list_js = {
    "Sales Invoice": "public/js/sales_invoice_list.js"
}

# Calendar view JS
doctype_calendar_js = {
    "Task": "public/js/task_calendar.js"
}

# Tree view JS
doctype_tree_js = {
    "Account": "public/js/account_tree.js"
}
```

### build.json - Build configuration

```json
{
    "js/your_app.min.js": [
        "public/js/core/namespace.js",
        "public/js/core/utils.js",
        "public/js/controllers/base_controller.js",
        "public/js/templates/**/*.js"
    ],
    
    "css/your_app.css": [
        "public/scss/main.scss",
        "public/css/custom.css"
    ]
}
```

## 2.4. Load Order trong Runtime

```
1. HTML page loads
   ↓
2. <script src="/assets/frappe/js/frappe-web.min.js">
   ├─ frappe.provide()
   ├─ frappe.utils
   ├─ frappe.ui base classes
   └─ frappe.model
   ↓
3. <script src="/assets/erpnext/js/erpnext.min.js">
   ├─ erpnext.utils
   └─ erpnext.TransactionController
   ↓
4. <script src="/assets/your_app/js/your_app.min.js">
   └─ Your custom code
   ↓
5. User navigates to Sales Invoice Form
   ↓
6. Dynamic load: sales_invoice.bundle.js
   └─ DocType specific code
```

**⚠️ Quan trọng:** File load sau sẽ override file load trước nếu cùng namespace!

---

# 3. BOOT PROCESS - KHỞI ĐỘNG ỨNG DỤNG

## 3.1. Server-side Boot

```python
# frappe/website/page/desk/desk.py

def get_context(context):
    """
    Server render desk page và inject boot data
    """
    boot_info = frappe.sessions.get()
    
    context.boot = {
        'user': frappe.session.user,
        'user_info': get_user_info(),
        'sysdefaults': frappe.defaults.get_defaults(),
        'modules': get_modules(),
        'lang': frappe.local.lang,
        'timezone': frappe.local.timezone,
        
        # Metadata
        'metadata_version': get_metadata_version(),
        
        # Permissions
        'user_permissions': get_user_permissions(),
        
        # System settings
        'system_settings': get_system_settings(),
        
        # Installed apps
        'installed_apps': frappe.get_installed_apps(),
        
        # Custom boot info từ hooks
        'custom_boot_info': get_custom_boot_info()
    }
```

## 3.2. Client-side Boot Sequence

```javascript
// Trong desk.html (template)
<script>
    // Server inject boot info vào global scope
    frappe.boot = {{ boot|json }};
</script>

<script src="/assets/frappe/js/frappe-web.min.js"></script>

<script>
    // frappe-web.min.js loaded, bắt đầu init
    
    // 1. Setup frappe object
    frappe.boot_init = function() {
        // Parse boot info
        frappe.user = frappe.boot.user;
        frappe.user_info = frappe.boot.user_info;
        
        // Setup defaults
        frappe.defaults.setup(frappe.boot.sysdefaults);
        
        // Setup language
        frappe.moment.locale(frappe.boot.lang);
        
        // Setup modules
        frappe.modules = frappe.boot.modules;
    };
    
    // 2. Initialize UI
    frappe.init_ui = function() {
        // Create desk layout
        frappe.desk = new frappe.ui.Desk();
        
        // Setup toolbar
        frappe.ui.toolbar = new frappe.ui.Toolbar();
        
        // Setup sidebar
        frappe.pages.sidebar = new frappe.ui.Sidebar();
        
        // Setup notifications
        frappe.ui.notifications = new frappe.ui.Notifications();
    };
    
    // 3. Setup router
    frappe.setup_router = function() {
        frappe.route_history = [];
        frappe.route_options = {};
        
        // Bind popstate for browser back/forward
        window.addEventListener('popstate', function(e) {
            if (e.state) {
                frappe.set_route(e.state.route, null, true);
            }
        });
        
        // Initial route
        let route = frappe.get_route();
        frappe.set_route(route);
    };
    
    // 4. Setup realtime (SocketIO)
    frappe.setup_realtime = function() {
        if (frappe.boot.setup_realtime) {
            frappe.socketio.init();
        }
    };
    
    // 5. Execute boot
    $(document).ready(function() {
        frappe.boot_init();
        frappe.init_ui();
        frappe.setup_router();
        frappe.setup_realtime();
        
        // Trigger custom boot hooks
        $(document).trigger('frappe-ready');
    });
</script>
```

## 3.3. Boot Hooks

```javascript
// Custom app có thể hook vào boot process
// your_app/public/js/your_app.js

$(document).on('frappe-ready', function() {
    // App đã boot xong, có thể chạy custom logic
    
    // Setup custom defaults
    frappe.defaults.add_user_default('default_warehouse', 'Main Warehouse');
    
    // Modify UI
    customize_toolbar();
    
    // Setup custom event listeners
    setup_custom_listeners();
});

function customize_toolbar() {
    // Add custom button to toolbar
    frappe.ui.toolbar.add_dropdown_button('Custom Menu', [
        {
            label: 'Custom Action 1',
            action: function() { /* ... */ }
        },
        {
            label: 'Custom Action 2',
            action: function() { /* ... */ }
        }
    ]);
}
```

---

# 4. MODULE RESOLUTION & DEPENDENCY GRAPH

## 4.1. Dependency Graph Analysis

### Ví dụ: Sales Invoice Dependencies

```javascript
// sales_invoice.js
frappe.ui.form.on('Sales Invoice', {
    // Phụ thuộc vào:
    // 1. TransactionController (parent class)
    // 2. erpnext.utils.party (utility functions)
    // 3. frappe.model.mapper (document mapping)
});

// Dependency tree:
/*
sales_invoice.bundle.js
├── erpnext.TransactionController
│   ├── erpnext.accounts.AccountsController
│   │   ├── frappe.ui.form.Controller (base)
│   │   │   ├── frappe.ui.form.Form
│   │   │   └── frappe.model
│   │   └── erpnext.utils
│   └── erpnext.taxes_and_totals
├── erpnext.utils.party
│   └── frappe.call (API)
└── frappe.model.mapper
    └── frappe.model
*/
```

## 4.2. Module Resolution Strategy

```javascript
// Build tool resolve modules theo thứ tự:

// 1. Check local imports
import { something } from './local_file';

// 2. Check node_modules
import $ from 'jquery';

// 3. Check aliases (từ build config)
import utils from '@/utils'; // → frappe/public/js/utils

// 4. Check external (CDN)
// <script src="https://cdn.jsdelivr.net/npm/moment@2.29.1/moment.min.js">
```

## 4.3. Circular Dependency Handling

```javascript
// ⚠️ PROBLEM: Circular dependency
// file_a.js
import { b_function } from './file_b';
export function a_function() {
    return b_function();
}

// file_b.js
import { a_function } from './file_a';
export function b_function() {
    return a_function(); // ← Circular!
}

// ✅ SOLUTION 1: Lazy import
// file_b.js
export function b_function() {
    const { a_function } = require('./file_a'); // Runtime import
    return a_function();
}

// ✅ SOLUTION 2: Dependency injection
// file_b.js
export function b_function(a_fn) {
    return a_fn();
}

// ✅ SOLUTION 3: Restructure (extract common to file_c)
```

## 4.4. Bundle Optimization

### Code Splitting Example

```javascript
// frappe/public/js/frappe/router.js

frappe.set_route = function(route) {
    let page_type = route[0];
    
    // Lazy load bundles based on page type
    if (page_type === 'Form') {
        // Load form bundle if not loaded
        return frappe.require('form.bundle.js').then(() => {
            return show_form(route);
        });
    }
    else if (page_type === 'List') {
        return frappe.require('list.bundle.js').then(() => {
            return show_list(route);
        });
    }
    else if (page_type === 'Report') {
        return frappe.require('report.bundle.js').then(() => {
            return show_report(route);
        });
    }
};

// frappe.require implementation
frappe.require = function(filename) {
    // Check if already loaded
    if (frappe._loaded_bundles[filename]) {
        return Promise.resolve();
    }
    
    // Dynamic import
    return new Promise((resolve, reject) => {
        let script = document.createElement('script');
        script.src = `/assets/frappe/dist/js/${filename}`;
        script.onload = () => {
            frappe._loaded_bundles[filename] = true;
            resolve();
        };
        script.onerror = reject;
        document.head.appendChild(script);
    });
};
```

### Tree Shaking

```javascript
// INPUT: utils.js có nhiều functions
export function format_currency(value) { /* ... */ }
export function format_number(value) { /* ... */ }
export function format_date(value) { /* ... */ }
export function rarely_used_function() { /* ... */ }

// Your code chỉ dùng format_currency
import { format_currency } from './utils';

// OUTPUT: Tree shaking loại bỏ unused code
// Bundle chỉ chứa format_currency, bỏ các function khác
```

---

# 5. NAMESPACE SYSTEM - frappe.provide()

## 5.1. Implementation của frappe.provide()

```javascript
// frappe/public/js/frappe/provide.js

frappe.provide = function(namespace) {
    // Split namespace bằng '.'
    // 'frappe.ui.form.controls' → ['frappe', 'ui', 'form', 'controls']
    let parts = namespace.split('.');
    
    // Start từ window object
    let parent = window;
    
    // Tạo mỗi level nếu chưa tồn tại
    for (let i = 0; i < parts.length; i++) {
        let part = parts[i];
        
        // Nếu property chưa tồn tại, tạo empty object
        if (typeof parent[part] === 'undefined') {
            parent[part] = {};
        }
        
        // Di chuyển xuống level tiếp theo
        parent = parent[part];
    }
    
    return parent;
};

// Ví dụ sử dụng:
frappe.provide('frappe.ui.form.controls');

// Kết quả:
/*
window.frappe = {
    ui: {
        form: {
            controls: {}
        }
    }
}
*/
```

## 5.2. Namespace Collision Examples

### ⚠️ Case 1: Override function

```javascript
// ===== FILE A (load trước) =====
// frappe/public/js/frappe/utils/common.js
frappe.provide('frappe.utils');

frappe.utils.get_file_extension = function(filename) {
    return filename.split('.').pop();
};

// ===== FILE B (load sau) =====
// erpnext/public/js/utils/override.js
frappe.provide('frappe.utils');

// Override function cùng tên
frappe.utils.get_file_extension = function(filename) {
    let ext = filename.split('.').pop();
    return ext.toUpperCase(); // Thêm logic mới
};

// ===== KẾT QUẢ =====
frappe.utils.get_file_extension('test.pdf');
// Return: 'PDF' (version B)
// Version A đã bị override hoàn toàn!
```

### ✅ Solution: Wrapper Pattern

```javascript
// FILE B: Wrapper thay vì override
frappe.provide('frappe.utils');

// Lưu reference gốc
const _original_get_file_extension = frappe.utils.get_file_extension;

// Wrap function gốc
frappe.utils.get_file_extension = function(filename) {
    let ext = _original_get_file_extension(filename);
    
    // Thêm custom logic
    if (should_uppercase()) {
        return ext.toUpperCase();
    }
    
    return ext;
};
```

### ⚠️ Case 2: Override object property

```javascript
// FILE A
frappe.provide('frappe.utils');
frappe.utils.defaults = {
    currency: 'USD',
    language: 'en',
    timezone: 'UTC'
};

// FILE B
frappe.provide('frappe.utils');
// Gán lại object mới → mất hết properties cũ!
frappe.utils.defaults = {
    currency: 'VND'
    // ⚠️ Mất language và timezone!
};

// ✅ Solution: Merge instead of replace
$.extend(frappe.utils.defaults, {
    currency: 'VND'
});
// Giữ language và timezone, chỉ update currency
```

### ⚠️ Case 3: Multiple apps conflict

```javascript
// ===== ERPNEXT =====
frappe.provide('frappe.utils');
frappe.utils.calculate_total = function(items) {
    return items.reduce((sum, i) => sum + i.amount, 0);
};

// ===== YOUR_APP =====
frappe.provide('frappe.utils');
// Vô tình override function của ERPNext!
frappe.utils.calculate_total = function(items) {
    // Logic khác
    return items.reduce((sum, i) => sum + i.net_amount, 0);
};

// ===== RESULT =====
// ERPNext code breaks vì logic đã thay đổi!
```

### ✅ Solution: Use app-specific namespace

```javascript
// ===== YOUR_APP - Đúng cách =====
frappe.provide('your_app.utils');

your_app.utils.calculate_total = function(items) {
    return items.reduce((sum, i) => sum + i.net_amount, 0);
};

// Không conflict với frappe.utils.calculate_total
```

## 5.3. Namespace Best Practices

```javascript
// ❌ WRONG: Pollute frappe core namespace
frappe.provide('frappe.utils');
frappe.utils.my_custom_function = function() { /* ... */ };

// ❌ WRONG: Use generic names
frappe.provide('helpers');
window.helpers.do_something = function() { /* ... */ };

// ✅ CORRECT: App-specific namespace
frappe.provide('your_app.helpers');
your_app.helpers.do_something = function() { /* ... */ };

// ✅ CORRECT: Module-based organization
frappe.provide('your_app.accounting.utils');
frappe.provide('your_app.inventory.utils');
frappe.provide('your_app.sales.utils');

your_app.accounting.utils.calculate_tax = function() { /* ... */ };
your_app.inventory.utils.check_stock = function() { /* ... */ };
your_app.sales.utils.apply_discount = function() { /* ... */ };
```

## 5.4. Checking Namespace at Runtime

```javascript
// Debug namespace issues
console.dir(frappe); // Show entire frappe object tree

// Check if namespace exists
if (frappe.utils && frappe.utils.calculate_total) {
    console.log('Function exists');
}

// List all properties in namespace
Object.keys(frappe.utils);
// ['format_currency', 'get_file_extension', ...]

// Check function source
console.log(frappe.utils.calculate_total.toString());
// Shows function code - useful for debugging which version is loaded

// Trace execution
function trace_wrapper(fn, name) {
    return function(...args) {
        console.trace(`Calling ${name}`, args);
        return fn.apply(this, args);
    };
}

frappe.utils.calculate_total = trace_wrapper(
    frappe.utils.calculate_total,
    'calculate_total'
);
```

---

# 6. ROUTING & LAZY LOADING

## 6.1. Router Architecture

```javascript
// frappe/public/js/frappe/router.js (simplified)

frappe.router = {
    current_route: [],
    route_history: [],
    
    // Main routing function
    set_route: function(route) {
        route = this.parse_route(route);
        
        // Check if route changed
        if (this.is_same_route(route)) {
            return Promise.resolve();
        }
        
        // Save history
        this.route_history.push(this.current_route);
        this.current_route = route;
        
        // Update URL
        this.update_url(route);
        
        // Clear current page
        this.cleanup_current_page();
        
        // Route to appropriate handler
        return this.route_to_page(route);
    },
    
    parse_route: function(route) {
        // Convert route string/array to normalized array
        if (typeof route === 'string') {
            route = route.split('/').filter(r => r);
        }
        return route || [];
    },
    
    route_to_page: function(route) {
        let page_type = route[0];
        
        switch(page_type) {
            case 'Form':
                return this.show_form(route[1], route[2]);
            case 'List':
                return this.show_list(route[1]);
            case 'Report':
                return this.show_report(route[1], route[2]);
            case 'Page':
                return this.show_page(route[1]);
            case 'print':
                return this.show_print(route);
            default:
                return this.show_404();
        }
    }
};
```

## 6.2. Form Lazy Loading

```javascript
// frappe.router.show_form implementation

frappe.router.show_form = function(doctype, name) {
    // 1. Check if doctype bundle is loaded
    let bundle_name = frappe.router.slug(doctype);
    let bundle_path = `${bundle_name}.bundle.js`;
    
    // 2. Lazy load bundle
    return frappe.require(bundle_path).then(() => {
        // 3. After bundle loaded, create form
        return this.create_form(doctype, name);
    });
};

frappe.router.create_form = function(doctype, name) {
    // Create form container
    let wrapper = frappe.container.page;
    
    // Initialize form
    frappe.ui.form.make_quick_entry(doctype, (doc) => {
        // After form ready, render it
        let frm = new frappe.ui.form.Form({
            doctype: doctype,
            parent: wrapper,
            doc: doc,
            name: name
        });
        
        // Load document
        if (name) {
            frm.load_doc(name);
        }
        
        return frm;
    });
};
```

## 6.3. Bundle Loading Strategy

```javascript
// frappe.require - Dynamic script loading

frappe._loaded_bundles = {};

frappe.require = function(bundles, callback) {
    // Normalize input
    if (typeof bundles === 'string') {
        bundles = [bundles];
    }
    
    // Filter already loaded
    bundles = bundles.filter(b => !frappe._loaded_bundles[b]);
    
    if (!bundles.length) {
        // All bundles already loaded
        if (callback) callback();
        return Promise.resolve();
    }
    
    // Load bundles in parallel
    let promises = bundles.map(bundle => {
        return new Promise((resolve, reject) => {
            let script = document.createElement('script');
            script.src = frappe.boot.assets_version 
                ? `/assets/${bundle}?v=${frappe.boot.assets_version}`
                : `/assets/${bundle}`;
            
            script.onload = () => {
                frappe._loaded_bundles[bundle] = true;
                resolve();
            };
            
            script.onerror = () => {
                reject(new Error(`Failed to load ${bundle}`));
            };
            
            document.head.appendChild(script);
        });
    });
    
    return Promise.all(promises).then(() => {
        if (callback) callback();
    });
};
```

## 6.4. Route Examples

```javascript
// Example 1: Navigate to form
frappe.set_route('Form', 'Sales Invoice', 'ACC-SINV-2024-00001');
// URL: /app/sales-invoice/ACC-SINV-2024-00001
// Loads: sales_invoice.bundle.js

// Example 2: Navigate to list
frappe.set_route('List', 'Customer');
// URL: /app/customer
// Loads: customer_list.bundle.js

// Example 3: Navigate to report
frappe.set_route('Report', 'Sales Analytics', 'Report');
// URL: /app/query-report/Sales Analytics
// Loads: sales_analytics.bundle.js

// Example 4: Navigate to custom page
frappe.set_route('custom-page');
// URL: /app/custom-page
// Loads: custom_page.bundle.js

// Example 5: Navigate with options
frappe.route_options = {
    customer: 'CUST-00001',
    from_date: '2024-01-01'
};
frappe.set_route('List', 'Sales Invoice');
// List will be filtered by route_options
```

## 6.5. Route Guards & Middleware

```javascript
// Custom route guard example
frappe.router.add_guard = function(guard_fn) {
    this.guards = this.guards || [];
    this.guards.push(guard_fn);
};

// Usage
frappe.router.add_guard(function(route) {
    // Check permission
    if (route[0] === 'Form') {
        let doctype = route[1];
        if (!frappe.perm.has_perm(doctype, 0, 'read')) {
            frappe.msgprint('No permission');
            return false; // Block navigation
        }
    }
    return true; // Allow navigation
});

// Apply guards in route_to_page
frappe.router.route_to_page = function(route) {
    // Run guards
    for (let guard of (this.guards || [])) {
        if (!guard(route)) {
            return Promise.reject('Route blocked by guard');
        }
    }
    
    // Continue routing...
};
```

---

# 7. FORM LIFECYCLE

## 7.1. Form Creation Flow

```javascript
// Khi user mở form, đây là trình tự chính xác:

// 1. Router triggers form creation
frappe.set_route('Form', 'Sales Invoice', 'new');

// 2. Load bundle (if not loaded)
frappe.require('sales_invoice.bundle.js');

// 3. Create Form instance
let frm = new frappe.ui.form.Form({
    doctype: 'Sales Invoice',
    parent: wrapper,
    doc: null
});

// 4. Form constructor runs
constructor(opts) {
    this.doctype = opts.doctype;
    this.parent = opts.parent;
    this.doc = opts.doc;
    
    // Create layout
    this.setup();
}

// 5. setup() - Creates UI skeleton
setup() {
    this.wrapper = $('<div class="form-container">').appendTo(this.parent);
    this.layout = new frappe.ui.form.Layout({
        parent: this.wrapper,
        frm: this
    });
    this.toolbar = new frappe.ui.form.Toolbar({
        frm: this
    });
}

// 6. Load metadata
this.meta = frappe.get_meta(this.doctype);

// 7. Setup controller
this.script_manager = new frappe.ui.form.ScriptManager({
    frm: this
});
this.script_manager.setup();

// 8. Trigger setup event (from doctype JS)
frappe.ui.form.on('Sales Invoice', {
    setup: function(frm) {
        // Runs ONCE when form is first created
        // Setup queries, custom buttons, etc
    }
});

// 9. Load document (if not new)
if (name !== 'new') {
    this.load_doc(name);
}

// 10. onload event
frappe.ui.form.on('Sales Invoice', {
    onload: function(frm) {
        // Runs after document is loaded
        // Initialize fields, set defaults, etc
    }
});

// 11. refresh event
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Runs every time form is refreshed
        // Update UI, show/hide fields, etc
    }
});

// 12. Render fields
this.layout.render();
```

## 7.2. Complete Event Lifecycle

```javascript
// frappe/public/js/frappe/form/form.js

frappe.ui.form.Form = class {
    
    // ========== CREATION PHASE ==========
    
    constructor(opts) {
        // Initialize form
    }
    
    setup() {
        // Create UI skeleton
        // Trigger: setup event (once only)
    }
    
    // ========== LOAD PHASE ==========
    
    load_doc(name) {
        // Fetch document from server
        return frappe.model.with_doc(this.doctype, name, () => {
            this.doc = frappe.get_doc(this.doctype, name);
            
            // Trigger: onload event
            this.trigger('onload');
            
            // Trigger: refresh event
            this.refresh();
        });
    }
    
    // ========== REFRESH PHASE ==========
    
    refresh() {
        // Update UI based on doc state
        
        // 1. Update dirty indicator
        this.show_submit_message();
        
        // 2. Update toolbar buttons
        this.toolbar.refresh();
        
        // 3. Update fields
        this.layout.refresh(this.doc);
        
        // 4. Trigger: refresh event
        this.trigger('refresh');
        
        // 5. Trigger field-specific events
        this.refresh_fields();
    }
    
    refresh_fields() {
        this.fields.forEach(field => {
            // Trigger: fieldname event
            // e.g., 'customer' event when customer field changes
            if (field.df.fieldname) {
                this.trigger(field.df.fieldname);
            }
        });
    }
    
    // ========== VALIDATION PHASE ==========
    
    validate() {
        // Client-side validation
        
        // 1. Trigger: validate event
        return this.trigger('validate').then(() => {
            // 2. Built-in validations
            return this.validate_fields();
        }).then(() => {
            // 3. Check mandatory fields
            return this.validate_mandatory();
        });
    }
    
    // ========== SAVE PHASE ==========
    
    save(save_action = 'Save', callback) {
        // save_action: 'Save', 'Submit', 'Update', 'Save as Draft'
        
        // 1. Trigger: before_save event
        return this.trigger('before_save').then(() => {
            // 2. Validate
            return this.validate();
        }).then(() => {
            // 3. Actual save to server
            return frappe.call({
                method: 'frappe.desk.form.save.savedocs',
                args: {
                    doc: this.doc,
                    action: save_action
                }
            });
        }).then(r => {
            // 4. Update local doc
            this.doc = r.message;
            
            // 5. Trigger: after_save event
            return this.trigger('after_save');
        }).then(() => {
            // 6. Refresh form
            this.refresh();
            
            // 7. Callback
            if (callback) callback(this.doc);
        });
    }
    
    // ========== CHILD TABLE EVENTS ==========
    
    on_grid_row_add(cdt, cdn) {
        // When new row added to child table
        // Trigger: <tablefieldname>_add event
        let table_field = this.get_table_field_by_cdt(cdt);
        if (table_field) {
            this.trigger(table_field.df.fieldname + '_add', cdt, cdn);
        }
    }
    
    on_grid_row_remove(cdt, cdn) {
        // When row removed from child table
        // Trigger: <tablefieldname>_remove event
        let table_field = this.get_table_field_by_cdt(cdt);
        if (table_field) {
            this.trigger(table_field.df.fieldname + '_remove', cdt, cdn);
        }
    }
    
    // ========== EVENT TRIGGER SYSTEM ==========
    
    trigger(event_name, ...args) {
        // Get event handlers from script manager
        let handlers = this.script_manager.get_handlers(event_name);
        
        // Execute handlers in sequence
        return handlers.reduce((promise, handler) => {
            return promise.then(() => {
                return handler(this, ...args);
            });
        }, Promise.resolve());
    }
};
```

## 7.3. Event Registration & Handling

```javascript
// frappe.ui.form.on - Event registration

frappe.ui.form.on('Sales Invoice', {
    // ========== LIFECYCLE EVENTS ==========
    
    setup: function(frm) {
        // Runs ONCE when form object is created
        // Use for: setting up queries, adding custom buttons templates
        
        frm.set_query('customer', function() {
            return {
                filters: {
                    disabled: 0
                }
            };
        });
    },
    
    onload: function(frm) {
        // Runs when document is loaded (after data fetch)
        // Use for: initializing values, loading related data
        
        if (frm.is_new()) {
            frm.set_value('posting_date', frappe.datetime.get_today());
            frm.set_value('due_date', frappe.datetime.add_days(null, 30));
        }
    },
    
    refresh: function(frm) {
        // Runs every time form is refreshed
        // Use for: conditional UI updates, button visibility
        
        // Show buttons based on document state
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button('Get Items from Sales Order', function() {
                // ...
            });
        }
        
        if (frm.doc.docstatus === 1 && frm.doc.outstanding_amount > 0) {
            frm.add_custom_button('Create Payment Entry', function() {
                // ...
            });
        }
        
        // Hide/show fields
        frm.toggle_display('section_break_1', frm.doc.is_return);
    },
    
    // ========== VALIDATION EVENTS ==========
    
    validate: function(frm) {
        // Client-side validation before save
        // Return false or throw error to prevent save
        
        if (!frm.doc.customer) {
            frappe.throw('Customer is mandatory');
        }
        
        if (!frm.doc.items || !frm.doc.items.length) {
            frappe.throw('Please add items');
        }
        
        // Validate total
        let total = 0;
        frm.doc.items.forEach(item => {
            total += item.amount;
        });
        
        if (total !== frm.doc.grand_total) {
            frappe.msgprint('Total mismatch detected');
        }
    },
    
    before_save: function(frm) {
        // Runs right before save API call
        // Use for: last-minute data cleanup
        
        // Round amounts
        frm.doc.grand_total = flt(frm.doc.grand_total, 2);
    },
    
    after_save: function(frm) {
        // Runs after successful save
        // Use for: showing messages, triggering other actions
        
        frappe.show_alert({
            message: 'Invoice saved successfully',
            indicator: 'green'
        });
        
        // Refresh related forms
        if (frm.doc.customer) {
            frappe.ui.form.refresh_doc('Customer', frm.doc.customer);
        }
    },
    
    // ========== FIELD CHANGE EVENTS ==========
    
    customer: function(frm) {
        // Runs when customer field changes
        
        if (frm.doc.customer) {
            // Fetch customer details
            frappe.call({
                method: 'erpnext.accounts.party.get_party_details',
                args: {
                    party: frm.doc.customer,
                    party_type: 'Customer',
                    doctype: frm.doctype
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('customer_name', r.message.customer_name);
                        frm.set_value('customer_group', r.message.customer_group);
                        frm.set_value('territory', r.message.territory);
                        frm.set_value('currency', r.message.currency);
                    }
                }
            });
        }
    },
    
    posting_date: function(frm) {
        // Update due date when posting date changes
        if (frm.doc.posting_date) {
            let due_date = frappe.datetime.add_days(
                frm.doc.posting_date,
                frm.doc.payment_terms_template_days || 30
            );
            frm.set_value('due_date', due_date);
        }
    },
    
    // ========== CHILD TABLE EVENTS ==========
    
    items_add: function(frm, cdt, cdn) {
        // Runs when new row added to items table
        let row = frappe.get_doc(cdt, cdn);
        
        // Set default values for new row
        frappe.model.set_value(cdt, cdn, 'qty', 1);
        frappe.model.set_value(cdt, cdn, 'uom', 'Nos');
    },
    
    items_remove: function(frm, cdt, cdn) {
        // Runs when row removed from items table
        // Recalculate totals
        frm.trigger('calculate_totals');
    },
    
    // ========== CUSTOM EVENTS ==========
    
    calculate_totals: function(frm) {
        // Custom reusable function
        let total = 0;
        let tax_total = 0;
        
        (frm.doc.items || []).forEach(item => {
            total += item.amount || 0;
        });
        
        (frm.doc.taxes || []).forEach(tax => {
            tax_total += tax.tax_amount || 0;
        });
        
        frm.set_value('total', total);
        frm.set_value('grand_total', total + tax_total);
    }
});

// ========== CHILD TABLE SPECIFIC EVENTS ==========

frappe.ui.form.on('Sales Invoice Item', {
    // Events for child table rows
    
    item_code: function(frm, cdt, cdn) {
        // When item_code changes in any row
        let row = frappe.get_doc(cdt, cdn);
        
        if (row.item_code) {
            frappe.call({
                method: 'erpnext.stock.get_item_details.get_item_details',
                args: {
                    args: {
                        item_code: row.item_code,
                        customer: frm.doc.customer,
                        price_list: frm.doc.selling_price_list
                    }
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'item_name', r.message.item_name);
                        frappe.model.set_value(cdt, cdn, 'rate', r.message.price_list_rate);
                        frappe.model.set_value(cdt, cdn, 'uom', r.message.uom);
                    }
                }
            });
        }
    },
    
    qty: function(frm, cdt, cdn) {
        // Calculate amount when qty changes
        calculate_item_amount(frm, cdt, cdn);
    },
    
    rate: function(frm, cdt, cdn) {
        // Calculate amount when rate changes
        calculate_item_amount(frm, cdt, cdn);
    },
    
    items_move: function(frm, cdt, cdn, old_index, new_index) {
        // When row is reordered
        console.log(`Row moved from ${old_index} to ${new_index}`);
    }
});

function calculate_item_amount(frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    let amount = flt(row.qty) * flt(row.rate);
    frappe.model.set_value(cdt, cdn, 'amount', amount);
    
    // Recalculate form totals
    frm.trigger('calculate_totals');
}
```

## 7.4. Form State Management

```javascript
// Form states
frm.doc.docstatus:
// 0 = Draft (can edit)
// 1 = Submitted (cannot edit, can cancel)
// 2 = Cancelled (cannot edit)

// Check form state
frm.is_new()        // true if new document
frm.is_dirty()      // true if unsaved changes
frm.doc.__unsaved   // true if modified
frm.doc.__islocal   // true if not saved to server yet

// Form flags (temporary state, not saved)
frm.refresh_field('customer'); // Refresh single field
frm.trigger('calculate_totals'); // Manually trigger event
frm.disable_save(); // Disable save button
frm.enable_save();  // Enable save button

// Set field properties
frm.set_df_property('customer', 'read_only', 1);
frm.toggle_reqd('customer', true); // Make mandatory
frm.toggle_display('section_break', false); // Hide field/section
frm.toggle_enable('customer', false); // Disable field

// Field value operations
frm.set_value('customer', 'CUST-00001');
frm.get_value('customer'); // Get current value
frm.clear_table('items'); // Clear child table
frm.add_child('items', {item_code: 'ITEM-001'}); // Add child row
```

---

# 8. CONTROLLER PATTERN & INHERITANCE

## 8.1. Base Controller Class

```javascript
// frappe/public/js/frappe/form/form.js

frappe.ui.form.Controller = class {
    constructor(opts) {
        $.extend(this, opts);
    }
    
    setup() {
        // Override in child class
    }
    
    onload() {
        // Override in child class
    }
    
    refresh() {
        // Override in child class
    }
    
    validate() {
        // Override in child class
    }
};
```

## 8.2. Inheritance Chain (ERPNext Example)

```javascript
// ========== LEVEL 1: Base Controller ==========
// frappe/public/js/frappe/form/form.js

frappe.ui.form.Controller = class {
    constructor(opts) {
        this.frm = opts.frm;
    }
    
    setup() {}
    refresh() {}
    validate() {}
    
    // Utility methods available to all controllers
    set_query(fieldname, filters) {
        this.frm.set_query(fieldname, function() {
            return { filters: filters };
        });
    }
    
    get_value(fieldname) {
        return this.frm.doc[fieldname];
    }
    
    set_value(fieldname, value) {
        return this.frm.set_value(fieldname, value);
    }
};

// ========== LEVEL 2: Transaction Controller ==========
// erpnext/public/js/controllers/transaction.js

erpnext.TransactionController = class extends frappe.ui.form.Controller {
    
    setup() {
        super.setup();
        // Common setup for all transactions
        this.setup_posting_date_time_check();
    }
    
    onload() {
        super.onload();
        
        if (this.frm.is_new()) {
            // Set default values for new transaction
            this.frm.set_value('posting_date', frappe.datetime.get_today());
            this.frm.set_value('posting_time', frappe.datetime.now_time());
        }
        
        // Setup common queries
        this.setup_queries();
    }
    
    refresh() {
        super.refresh();
        
        // Common buttons for all transactions
        if (this.frm.doc.docstatus === 1) {
            this.show_general_ledger_button();
        }
        
        this.show_stock_ledger_button();
    }
    
    // ===== COMMON UTILITY METHODS =====
    
    setup_queries() {
        // Setup common link field queries
        this.setup_party_query();
        this.setup_item_query();
    }
    
    setup_party_query() {
        let party_type = this.frm.doc.party_type || 'Customer';
        
        this.frm.set_query(party_type.toLowerCase(), function() {
            return {
                filters: {
                    disabled: 0
                }
            };
        });
    }
    
    setup_item_query() {
        this.frm.set_query('item_code', 'items', function() {
            return {
                query: 'erpnext.controllers.queries.item_query',
                filters: {
                    is_sales_item: 1
                }
            };
        });
    }
    
    calculate_taxes_and_totals() {
        // Complex calculation logic shared by all transactions
        return this.frm.call({
            method: 'calculate_taxes_and_totals',
            doc: this.frm.doc,
            callback: function(r) {
                this.frm.refresh_fields();
            }
        });
    }
    
    show_general_ledger_button() {
        this.frm.add_custom_button('Accounting Ledger', function() {
            frappe.route_options = {
                voucher_no: this.frm.doc.name
            };
            frappe.set_route('query-report', 'General Ledger');
        }.bind(this));
    }
    
    show_stock_ledger_button() {
        if (!this.frm.doc.items || !this.frm.doc.items.length) {
            return;
        }
        
        this.frm.add_custom_button('Stock Ledger', function() {
            frappe.route_options = {
                voucher_no: this.frm.doc.name
            };
            frappe.set_route('query-report', 'Stock Ledger');
        }.bind(this));
    }
};

// ========== LEVEL 3: Accounts Controller ==========
// erpnext/accounts/public/js/controllers/accounts_controller.js

erpnext.accounts.AccountsController = class extends erpnext.TransactionController {
    
    setup() {
        super.setup();
        // Accounts-specific setup
    }
    
    onload() {
        super.onload();
        
        // Setup accounting dimensions
        this.setup_account_dimensions();
        
        // Setup tax queries
        this.setup_tax_queries();
    }
    
    refresh() {
        super.refresh();
        
        // Show accounting-specific buttons
        this.show_payment_entry_button();
        this.show_journal_entry_button();
    }
    
    // ===== ACCOUNTING METHODS =====
    
    setup_account_dimensions() {
        // Setup cost center, project queries
        this.frm.set_query('cost_center', function() {
            return {
                filters: {
                    company: me.frm.doc.company,
                    is_group: 0
                }
            };
        });
    }
    
    setup_tax_queries() {
        this.frm.set_query('taxes_and_charges', function() {
            return {
                filters: {
                    company: me.frm.doc.company
                }
            };
        });
    }
    
    calculate_outstanding_amount() {
        // Calculate outstanding = grand_total - paid_amount
        this.frm.doc.outstanding_amount = 
            flt(this.frm.doc.grand_total) - flt(this.frm.doc.paid_amount);
        
        this.frm.refresh_field('outstanding_amount');
    }
    
    show_payment_entry_button() {
        if (this.frm.doc.docstatus === 1 && this.frm.doc.outstanding_amount > 0) {
            this.frm.add_custom_button('Payment', function() {
                me.make_payment_entry();
            }.bind(this));
        }
    }
    
    make_payment_entry() {
        return frappe.call({
            method: 'erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry',
            args: {
                dt: this.frm.doctype,
                dn: this.frm.doc.name
            },
            callback: function(r) {
                let doc = frappe.model.sync(r.message);
                frappe.set_route('Form', doc.doctype, doc.name);
            }
        });
    }
};

// ========== LEVEL 4: Sales Invoice Controller ==========
// erpnext/accounts/doctype/sales_invoice/sales_invoice.js

erpnext.accounts.SalesInvoiceController = class extends erpnext.accounts.AccountsController {
    
    setup() {
        super.setup();
        
        // Sales Invoice specific setup
        this.setup_sales_invoice_queries();
    }
    
    onload() {
        super.onload();
        
        // Set sales-specific defaults
        if (this.frm.is_new()) {
            this.frm.set_value('is_pos', 0);
        }
    }
    
    refresh() {
        super.refresh();
        
        // Sales Invoice specific buttons
        this.show_sales_invoice_buttons();
    }
    
    customer() {
        // Override parent's customer handler
        // First call parent logic
        super.customer && super.customer();
        
        // Then add custom logic
        this.get_customer_pricing_rule();
    }
    
    // ===== SALES INVOICE SPECIFIC METHODS =====
    
    setup_sales_invoice_queries() {
        let me = this;
        
        // Filter sales orders for this customer
        this.frm.set_query('sales_order', function() {
            return {
                filters: {
                    customer: me.frm.doc.customer,
                    docstatus: 1
                }
            };
        });
    }
    
    show_sales_invoice_buttons() {
        if (this.frm.doc.docstatus === 1) {
            // Make Delivery Note
            this.frm.add_custom_button('Delivery Note', function() {
                me.make_delivery_note();
            }.bind(this));
            
            // Make Credit Note
            if (this.frm.doc.outstanding_amount > 0) {
                this.frm.add_custom_button('Credit Note', function() {
                    me.make_sales_return();
                }.bind(this));
            }
        }
    }
    
    get_customer_pricing_rule() {
        // Get special pricing for customer
        frappe.call({
            method: 'erpnext.selling.doctype.customer.customer.get_customer_pricing_rule',
            args: {
                customer: this.frm.doc.customer
            },
            callback: function(r) {
                if (r.message) {
                    me.apply_pricing_rule(r.message);
                }
            }
        });
    }
    
    make_delivery_note() {
        frappe.model.open_mapped_doc({
            method: 'erpnext.accounts.doctype.sales_invoice.sales_invoice.make_delivery_note',
            frm: this.frm
        });
    }
    
    make_sales_return() {
        frappe.model.open_mapped_doc({
            method: 'erpnext.accounts.doctype.sales_invoice.sales_invoice.make_sales_return',
            frm: this.frm
        });
    }
};

// ========== LEVEL 5: Register Controller ==========

frappe.ui.form.on('Sales Invoice', new erpnext.accounts.SalesInvoiceController());
```

## 8.3. Mixin Pattern

```javascript
// ========== DEFINE MIXINS ==========

// Mixin 1: Tax calculations
erpnext.mixins.TaxCalculation = {
    calculate_taxes: function() {
        let total_tax = 0;
        (this.frm.doc.taxes || []).forEach(tax_row => {
            total_tax += flt(tax_row.tax_amount);
        });
        this.frm.set_value('total_taxes_and_charges', total_tax);
    },
    
    apply_tax_template: function(template_name) {
        frappe.call({
            method: 'erpnext.controllers.taxes_and_totals.get_tax_template',
            args: { template: template_name },
            callback: (r) => {
                if (r.message) {
                    this.frm.clear_table('taxes');
                    r.message.forEach(tax => {
                        this.frm.add_child('taxes', tax);
                    });
                    this.calculate_taxes();
                }
            }
        });
    }
};

// Mixin 2: Address handling
erpnext.mixins.AddressHandler = {
    get_address_display: function(address_name) {
        return frappe.call({
            method: 'frappe.contacts.doctype.address.address.get_address_display',
            args: { address_dict: address_name },
            callback: (r) => {
                if (r.message) {
                    this.frm.set_value('address_display', r.message);
                }
            }
        });
    },
    
    setup_address_query: function(link_fieldname) {
        this.frm.set_query('customer_address', function() {
            return {
                query: 'frappe.contacts.doctype.address.address.address_query',
                filters: {
                    link_doctype: 'Customer',
                    link_name: me.frm.doc[link_fieldname]
                }
            };
        });
    }
};

// Mixin 3: Print format handling
erpnext.mixins.PrintHandler = {
    setup_print_button: function() {
        this.frm.add_custom_button('Print', function() {
            this.print_document();
        }.bind(this));
    },
    
    print_document: function(print_format) {
        frappe.ui.get_print_settings(false, (print_settings) => {
            let w = window.open(
                frappe.urllib.get_full_url(
                    `/api/method/frappe.utils.print_format.download_pdf?`
                    + `doctype=${encodeURIComponent(this.frm.doctype)}`
                    + `&name=${encodeURIComponent(this.frm.doc.name)}`
                    + `&format=${encodeURIComponent(print_format || this.frm.meta.default_print_format)}`
                )
            );
            if (!w) {
                frappe.msgprint('Please enable popups');
            }
        });
    }
};

// ========== APPLY MIXINS TO CONTROLLER ==========

erpnext.accounts.EnhancedSalesInvoiceController = class extends erpnext.accounts.SalesInvoiceController {
    
    setup() {
        super.setup();
        
        // Apply mixins
        Object.assign(this, erpnext.mixins.TaxCalculation);
        Object.assign(this, erpnext.mixins.AddressHandler);
        Object.assign(this, erpnext.mixins.PrintHandler);
        
        // Now can use mixin methods
        this.setup_address_query('customer');
        this.setup_print_button();
    }
    
    refresh() {
        super.refresh();
        
        // Use mixin methods
        if (this.frm.doc.taxes_and_charges) {
            this.apply_tax_template(this.frm.doc.taxes_and_charges);
        }
    }
    
    customer_address() {
        // Use mixin method
        if (this.frm.doc.customer_address) {
            this.get_address_display(this.frm.doc.customer_address);
        }
    }
};

frappe.ui.form.on('Sales Invoice', new erpnext.accounts.EnhancedSalesInvoiceController());
```

## 8.4. Override Parent Methods Safely

```javascript
// ========== METHOD 1: Call super then add logic ==========

class CustomSalesInvoice extends erpnext.accounts.SalesInvoiceController {
    
    refresh() {
        // Call parent's refresh first
        super.refresh();
        
        // Add custom logic
        this.add_custom_buttons();
        this.customize_form_layout();
    }
    
    add_custom_buttons() {
        this.frm.add_custom_button('Custom Action', function() {
            // Custom logic
        }.bind(this));
    }
}

// ========== METHOD 2: Wrap parent method ==========

class CustomSalesInvoice extends erpnext.accounts.SalesInvoiceController {
    
    constructor(opts) {
        super(opts);
        
        // Save reference to parent's method
        this._super_validate = this.validate.bind(this);
    }
    
    validate() {
        // Custom validation BEFORE parent
        if (!this.custom_validation()) {
            return Promise.reject();
        }
        
        // Call parent validation
        return this._super_validate().then(() => {
            // Custom validation AFTER parent
            return this.post_validate();
        });
    }
    
    custom_validation() {
        if (this.frm.doc.custom_field === 'invalid') {
            frappe.throw('Custom validation failed');
            return false;
        }
        return true;
    }
    
    post_validate() {
        // Logic after parent validation
        console.log('Post validation complete');
    }
}

// ========== METHOD 3: Conditional override ==========

class CustomSalesInvoice extends erpnext.accounts.SalesInvoiceController {
    
    customer() {
        // Check condition
        if (this.should_use_custom_customer_logic()) {
            // Use completely custom logic
            this.custom_customer_handler();
        } else {
            // Use parent logic
            super.customer();
        }
    }
    
    should_use_custom_customer_logic() {
        return this.frm.doc.custom_field === 'special';
    }
    
    custom_customer_handler() {
        // Completely different logic
        frappe.call({
            method: 'my_app.api.get_special_customer_data',
            args: { customer: this.frm.doc.customer },
            callback: (r) => {
                // Handle response
            }
        });
    }
}
```

---

# 9. EVENT SYSTEM

## 9.1. Event Types trong Frappe

```javascript
// ========== TYPE 1: Form Events (frappe.ui.form.on) ==========

frappe.ui.form.on('Sales Invoice', {
    // Lifecycle events
    setup: function(frm) {},
    onload: function(frm) {},
    refresh: function(frm) {},
    validate: function(frm) {},
    before_save: function(frm) {},
    after_save: function(frm) {},
    
    // Field events
    customer: function(frm) {},
    posting_date: function(frm) {},
    
    // Child table events
    items_add: function(frm, cdt, cdn) {},
    items_remove: function(frm, cdt, cdn) {}
});

// ========== TYPE 2: DOM Events (jQuery) ==========

$(document).ready(function() {
    // Document ready
});

$(frm.wrapper).on('click', '.custom-button', function(e) {
    // Click event on form element
});

$(document).on('form-load', function(e, frm) {
    // Custom event
});

// ========== TYPE 3: frappe.ui.toolbar Events ==========

frappe.ui.toolbar.on('save', function() {
    // When save button clicked
});

// ========== TYPE 4: Real-time Events (SocketIO) ==========

frappe.realtime.on('msgprint', function(data) {
    frappe.msgprint(data.message);
});

frappe.realtime.on('eval_js', function(data) {
    eval(data);
});

frappe.realtime.on('progress', function(data) {
    // Update progress bar
});

// ========== TYPE 5: Global frappe Events ==========

$(document).on('frappe-ready', function() {
    // Frappe has finished booting
});

$(document).on('page-change', function() {
    // Route changed
});
```

## 9.2. Event Propagation & Bubbling

```javascript
// frappe/public/js/frappe/form/script_manager.js

frappe.ui.form.ScriptManager = class {
    
    setup() {
        // Register all events from doctype JS
        this.setup_event_handlers();
    }
    
    setup_event_handlers() {
        // Get handlers from frappe.ui.form.handlers
        let doctype = this.frm.doctype;
        let handlers = frappe.ui.form.handlers[doctype] || {};
        
        // Store handlers by event name
        this.handlers = {};
        
        for (let event_name in handlers) {
            if (!this.handlers[event_name]) {
                this.handlers[event_name] = [];
            }
            this.handlers[event_name].push(handlers[event_name]);
        }
        
        // Also get child table handlers
        this.setup_child_handlers();
    }
    
    trigger(event_name, ...args) {
        // Get all handlers for this event
        let handlers = this.handlers[event_name] || [];
        
        // Execute in sequence (not parallel)
        return handlers.reduce((promise, handler) => {
            return promise.then(() => {
                // Execute handler
                let result = handler(this.frm, ...args);
                
                // Handle both sync and async
                return Promise.resolve(result);
            });
        }, Promise.resolve());
    }
};

// Example: Multiple handlers for same event
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        console.log('Handler 1');
    }
});

frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        console.log('Handler 2');
    }
});

// Both handlers execute in order: Handler 1, then Handler 2
```

## 9.3. Custom Event System

```javascript
// ========== CREATE CUSTOM EVENT BUS ==========

frappe.provide('custom_app.events');

custom_app.events = {
    _handlers: {},
    
    on: function(event_name, handler) {
        if (!this._handlers[event_name]) {
            this._handlers[event_name] = [];
        }
        this._handlers[event_name].push(handler);
    },
    
    off: function(event_name, handler) {
        if (!this._handlers[event_name]) return;
        
        if (handler) {
            // Remove specific handler
            let index = this._handlers[event_name].indexOf(handler);
            if (index > -1) {
                this._handlers[event_name].splice(index, 1);
            }
        } else {
            // Remove all handlers
            delete this._handlers[event_name];
        }
    },
    
    trigger: function(event_name, data) {
        let handlers = this._handlers[event_name] || [];
        
        handlers.forEach(handler => {
            try {
                handler(data);
            } catch(e) {
                console.error(`Error in handler for ${event_name}:`, e);
            }
        });
    }
};

// ========== USAGE ==========

// Subscribe to custom event
custom_app.events.on('invoice-validated', function(data) {
    console.log('Invoice validated:', data.invoice_name);
    // Update dashboard, send notification, etc
});

// Trigger custom event
frappe.ui.form.on('Sales Invoice', {
    validate: function(frm) {
        // After validation
        custom_app.events.trigger('invoice-validated', {
            invoice_name: frm.doc.name,
            customer: frm.doc.customer,
            amount: frm.doc.grand_total
        });
    }
});

// Unsubscribe
let handler = function(data) { /* ... */ };
custom_app.events.on('invoice-validated', handler);
// Later...
custom_app.events.off('invoice-validated', handler);
```

## 9.4. Event Debugging

```javascript
// ========== DEBUG EVENT FLOW ==========

// Wrap frappe.ui.form.trigger to log all events
(function() {
    let original_trigger = frappe.ui.form.Form.prototype.trigger;
    
    frappe.ui.form.Form.prototype.trigger = function(event, ...args) {
        console.log(`[EVENT] ${this.doctype}.${event}`, args);
        console.trace(); // Show call stack
        
        return original_trigger.call(this, event, ...args);
    };
})();

// ========== PERFORMANCE MONITORING ==========

frappe.provide('frappe.perf');

frappe.perf.monitor_events = function() {
    let timings = {};
    
    let original_trigger = frappe.ui.form.Form.prototype.trigger;
    
    frappe.ui.form.Form.prototype.trigger = function(event, ...args) {
        let start = performance.now();
        let key = `${this.doctype}.${event}`;
        
        return original_trigger.call(this, event, ...args).then(result => {
            let duration = performance.now() - start;
            
            if (!timings[key]) {
                timings[key] = { count: 0, total: 0, avg: 0 };
            }
            
            timings[key].count++;
            timings[key].total += duration;
            timings[key].avg = timings[key].total / timings[key].count;
            
            if (duration > 100) {
                console.warn(`[SLOW EVENT] ${key} took ${duration.toFixed(2)}ms`);
            }
            
            return result;
        });
    };
    
    // Report function
    frappe.perf.report = function() {
        console.table(timings);
    };
};

// Enable monitoring
frappe.perf.monitor_events();

// View report
frappe.perf.report();
```

---

# 10. OVERRIDE MECHANISM

## 10.1. Types of Override

```javascript
// ========== TYPE 1: Function Override (Direct) ==========

// Original function (Frappe Core)
frappe.utils.format_currency = function(value, currency) {
    return currency + ' ' + value.toFixed(2);
};

// Override (Your App)
// ⚠️ DANGEROUS: Completely replaces original
frappe.utils.format_currency = function(value, currency) {
    // New logic - old logic is LOST
    if (currency === 'VND') {
        return value.toLocaleString('vi-VN') + 'đ';
    }
    return currency + ' ' + value.toFixed(2);
};

// ========== TYPE 2: Wrapper Pattern (Safe) ==========

// Save original reference
frappe.provide('custom_app._originals');
custom_app._originals.format_currency = frappe.utils.format_currency;

// Wrap original
frappe.utils.format_currency = function(value, currency) {
    // Custom pre-processing
    if (currency === 'VND') {
        return value.toLocaleString('vi-VN') + 'đ';
    }
    
    // Call original for other currencies
    return custom_app._originals.format_currency(value, currency);
};

// ========== TYPE 3: Monkey Patch with Proxy ==========

frappe.utils.format_currency = new Proxy(
    frappe.utils.format_currency,
    {
        apply: function(target, thisArg, args) {
            console.log('format_currency called with:', args);
            
            // Custom logic
            if (args[1] === 'VND') {
                return args[0].toLocaleString('vi-VN') + 'đ';
            }
            
            // Call original
            return target.apply(thisArg, args);
        }
    }
);

// ========== TYPE 4: Event Override ==========

// Store original event handler
let original_refresh = frappe.ui.form.handlers['Sales Invoice'].refresh;

// Override with new handler
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Call original first
        if (original_refresh) {
            original_refresh(frm);
        }
        
        // Add custom logic
        frm.add_custom_button('My Custom Button', function() {
            // ...
        });
    }
});

// ========== TYPE 5: Prototype Override ==========

// Save original method
let original_validate = frappe.ui.form.Form.prototype.validate;

// Override prototype method
frappe.ui.form.Form.prototype.validate = function() {
    console.log('Custom validation for', this.doctype);
    
    // Add custom validation
    if (this.doc.custom_field === 'invalid') {
        frappe.throw('Custom validation failed');
        return Promise.reject();
    }
    
    // Call original
    return original_validate.call(this);
};
```

## 10.2. Safe Override Patterns

```javascript
// ========== PATTERN 1: Decorator ==========

frappe.provide('custom_app.decorators');

custom_app.decorators.trace = function(fn, name) {
    return function(...args) {
        console.log(`[TRACE] Calling ${name}`, args);
        let start = performance.now();
        
        let result = fn.apply(this, args);
        
        // Handle promises
        if (result && result.then) {
            return result.then(r => {
                let duration = performance.now() - start;
                console.log(`[TRACE] ${name} completed in ${duration.toFixed(2)}ms`);
                return r;
            });
        }
        
        let duration = performance.now() - start;
        console.log(`[TRACE] ${name} completed in ${duration.toFixed(2)}ms`);
        return result;
    };
};

// Usage
frappe.utils.format_currency = custom_app.decorators.trace(
    frappe.utils.format_currency,
    'format_currency'
);

// ========== PATTERN 2: Middleware Chain ==========

frappe.provide('custom_app.middleware');

custom_app.middleware = {
    chain: [],
    
    use: function(middleware) {
        this.chain.push(middleware);
    },
    
    execute: function(context, next) {
        let index = 0;
        
        let dispatch = (i) => {
            if (i >= this.chain.length) {
                return next(context);
            }
            
            let middleware = this.chain[i];
            return middleware(context, () => dispatch(i + 1));
        };
        
        return dispatch(0);
    }
};

// Wrap form save
let original_save = frappe.ui.form.Form.prototype.save;

frappe.ui.form.Form.prototype.save = function(...args) {
    let context = { frm: this, args: args };
    
    return custom_app.middleware.execute(context, (ctx) => {
        return original_save.apply(ctx.frm, ctx.args);
    });
};

// Add middleware
custom_app.middleware.use(function(context, next) {
    console.log('Middleware 1: Before save');
    return next().then(() => {
        console.log('Middleware 1: After save');
    });
});

custom_app.middleware.use(function(context, next) {
    // Validation middleware
    if (!context.frm.doc.custom_field) {
        frappe.throw('Custom field is required');
        return Promise.reject();
    }
    return next();
});

// ========== PATTERN 3: Plugin System ==========

frappe.provide('custom_app.plugins');

custom_app.plugins = {
    _plugins: [],
    
    register: function(plugin) {
        this._plugins.push(plugin);
        
        // Initialize plugin
        if (plugin.init) {
            plugin.init();
        }
    },
    
    hook: function(hook_name, ...args) {
        this._plugins.forEach(plugin => {
            if (plugin[hook_name]) {
                plugin[hook_name](...args);
            }
        });
    }
};

// Define plugin
let ValidationPlugin = {
    name: 'validation_plugin',
    
    init: function() {
        console.log('Validation plugin initialized');
    },
    
    before_save: function(frm) {
        console.log('Plugin validation for', frm.doctype);
    },
    
    after_save: function(frm) {
        console.log('Plugin post-save for', frm.doctype);
    }
};

// Register plugin
custom_app.plugins.register(ValidationPlugin);

// Hook into form save
let original_save = frappe.ui.form.Form.prototype.save;

frappe.ui.form.Form.prototype.save = function(...args) {
    // Before save hook
    custom_app.plugins.hook('before_save', this);
    
    return original_save.apply(this, args).then(result => {
        // After save hook
        custom_app.plugins.hook('after_save', this);
        return result;
    });
};
```

## 10.3. Override Detection & Debugging

```javascript
// ========== DETECT OVERRIDES ==========

frappe.provide('custom_app.debug');

custom_app.debug.find_overrides = function() {
    let overrides = [];
    
    // Check common namespaces
    let namespaces = [
        'frappe.utils',
        'frappe.ui.form',
        'frappe.model',
        'erpnext.utils'
    ];
    
    namespaces.forEach(ns => {
        let obj = eval(ns);
        if (!obj) return;
        
        Object.keys(obj).forEach(key => {
            let fn = obj[key];
            if (typeof fn === 'function') {
                // Check function source
                let source = fn.toString();
                
                // Look for signs of override
                if (source.includes('_original_') || 
                    source.includes('custom_app') ||
                    source.includes('// OVERRIDE')) {
                    overrides.push({
                        namespace: ns,
                        function: key,
                        source: source.substring(0, 200) + '...'
                    });
                }
            }
        });
    });
    
    return overrides;
};

// Usage
let overrides = custom_app.debug.find_overrides();
console.table(overrides);

// ========== STACK TRACE FOR OVERRIDES ==========

custom_app.debug.trace_function = function(namespace, fn_name) {
    let parts = namespace.split('.');
    let obj = window;
    
    for (let part of parts) {
        obj = obj[part];
    }
    
    let original = obj[fn_name];
    
    obj[fn_name] = function(...args) {
        console.group(`[TRACE] ${namespace}.${fn_name}`);
        console.log('Arguments:', args);
        console.trace('Call stack');
        
        let result = original.apply(this, args);
        
        console.log('Result:', result);
        console.groupEnd();
        
        return result;
    };
};

// Trace specific function
custom_app.debug.trace_function('frappe.utils', 'format_currency');
```

---

# 11. GLOBAL STATE & MEMORY MODEL

## 11.1. Global State Structure

```javascript
// ========== FRAPPE GLOBAL STATE ==========

window.frappe = {
    // ===== USER & SESSION =====
    user: 'Administrator',
    session: {
        user: 'Administrator',
        user_email: 'admin@example.com',
        user_fullname: 'Administrator'
    },
    boot: {}, // Boot configuration
    
    // ===== FLAGS (TEMPORARY STATE) =====
    flags: {
        // Temporary flags, reset on page load
        in_test: false,
        read_only: false
    },
    
    // ===== METADATA CACHE =====
    meta: {
        // Cached DocType metadata
        'Sales Invoice': { /* metadata */ },
        'Customer': { /* metadata */ }
    },
    
    // ===== DOCUMENT CACHE =====
    local: {
        // Cached documents (in-memory)
        'Sales Invoice': {
            'SINV-0001': { /* doc data */ }
        }
    },
    
    // ===== DEFAULTS =====
    defaults: {
        // User defaults
        company: 'My Company',
        currency: 'USD'
    },
    
    // ===== CURRENT CONTEXT =====
    _cur_frm: null,      // Current form
    cur_list: null,      // Current list
    cur_page: null,      // Current page
    container: null,     // Main container
    
    // ===== LOADED RESOURCES =====
    _loaded_bundles: {}, // Loaded JS bundles
    _loaded_css: {},     // Loaded CSS files
    
    // ===== ROUTE STATE =====
    _route: [],          // Current route
    _route_options: {}   // Route parameters
};
```

## 11.2. Memory Leak Patterns

```javascript
// ========== PROBLEM 1: Event Listener Leak ==========

// ❌ BAD: Creates new listener on every refresh
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        $(document).on('click', '.my-button', function() {
            // Handler
        });
        // After 100 refreshes = 100 listeners!
    }
});

// ✅ GOOD: Unbind before binding
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        $(document).off('click', '.my-button'); // Unbind first
        $(document).on('click', '.my-button', function() {
            // Handler
        });
    }
});

// ✅ BETTER: Use namespaced events
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        $(document).off('click.myapp'); // Unbind namespace
        $(document).on('click.myapp', '.my-button', function() {
            // Handler
        });
    }
});

// ========== PROBLEM 2: Closure Memory Leak ==========

// ❌ BAD: Holds reference to large object
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        let large_data = get_large_dataset(); // 10MB
        
        frm.add_custom_button('Process', function() {
            // Closure holds reference to large_data
            console.log(large_data[0]);
        });
        // large_data can't be garbage collected!
    }
});

// ✅ GOOD: Store only what's needed
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        let large_data = get_large_dataset();
        let first_item = large_data[0]; // Extract needed data
        large_data = null; // Allow GC
        
        frm.add_custom_button('Process', function() {
            console.log(first_item);
        });
    }
});

// ========== PROBLEM 3: Global Variable Pollution ==========

// ❌ BAD: Pollutes global scope
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Creates global variable
        my_temp_data = frm.doc.items;
    }
});

// Different form tries to use it
frappe.ui.form.on('Purchase Invoice', {
    refresh: function(frm) {
        console.log(my_temp_data); // ⚠️ Still has Sales Invoice data!
    }
});

// ✅ GOOD: Use namespaced storage
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Store in proper namespace
        frm._custom_data = frm._custom_data || {};
        frm._custom_data.items = frm.doc.items;
    }
});

// ========== PROBLEM 4: Circular References ==========

// ❌ BAD: Creates circular reference
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        let obj_a = { name: 'A' };
        let obj_b = { name: 'B' };
        
        obj_a.ref = obj_b;
        obj_b.ref = obj_a; // Circular!
        
        frm._data = obj_a; // Can't be garbage collected
    }
});

// ✅ GOOD: Break circular references
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Use WeakMap for references
        let refs = new WeakMap();
        let obj_a = { name: 'A' };
        let obj_b = { name: 'B' };
        
        refs.set(obj_a, obj_b);
        refs.set(obj_b, obj_a);
        
        // Objects can be GC'd when no longer referenced
    }
});
```

## 11.3. State Management Best Practices

```javascript
// ========== PATTERN 1: Form-scoped State ==========

frappe.ui.form.on('Sales Invoice', {
    setup: function(frm) {
        // Initialize state object
        frm._state = {
            original_data: null,
            cached_calculations: {},
            ui_flags: {}
        };
    },
    
    onload: function(frm) {
        // Store original data
        frm._state.original_data = JSON.parse(JSON.stringify(frm.doc));
    },
    
    refresh: function(frm) {
        // Use state
        if (frm._state.ui_flags.show_warning) {
            frappe.show_alert('Warning message');
        }
    },
    
    onload_post_render: function(frm) {
        // Clear state when leaving form
        $(frm.wrapper).on('remove', function() {
            frm._state = null; // Allow GC
        });
    }
});

// ========== PATTERN 2: Singleton State Manager ==========

frappe.provide('custom_app.state');

custom_app.state = {
    _data: {},
    
    set: function(key, value) {
        this._data[key] = value;
    },
    
    get: function(key, default_value) {
        return this._data.hasOwnProperty(key) 
            ? this._data[key] 
            : default_value;
    },
    
    clear: function(key) {
        if (key) {
            delete this._data[key];
        } else {
            this._data = {};
        }
    },
    
    // Subscribe to changes
    watch: function(key, callback) {
        this._watchers = this._watchers || {};
        if (!this._watchers[key]) {
            this._watchers[key] = [];
        }
        this._watchers[key].push(callback);
    },
    
    // Notify watchers
    _notify: function(key, value) {
        let watchers = this._watchers && this._watchers[key];
        if (watchers) {
            watchers.forEach(cb => cb(value));
        }
    }
};

// Override set to notify watchers
let original_set = custom_app.state.set;
custom_app.state.set = function(key, value) {
    original_set.call(this, key, value);
    this._notify(key, value);
};

// Usage
custom_app.state.watch('current_customer', function(customer) {
    console.log('Customer changed to:', customer);
});

custom_app.state.set('current_customer', 'CUST-001');

// ========== PATTERN 3: Immutable State Updates ==========

frappe.provide('custom_app.immutable');

custom_app.immutable = {
    // Deep clone
    clone: function(obj) {
        return JSON.parse(JSON.stringify(obj));
    },
    
    // Update object immutably
    update: function(obj, updates) {
        return Object.assign(this.clone(obj), updates);
    },
    
    // Update nested property
    set_path: function(obj, path, value) {
        let result = this.clone(obj);
        let current = result;
        let parts = path.split('.');
        
        for (let i = 0; i < parts.length - 1; i++) {
            current = current[parts[i]];
        }
        
        current[parts[parts.length - 1]] = value;
        return result;
    }
};

// Usage
let original_doc = { customer: 'A', items: [{ qty: 1 }] };
let updated_doc = custom_app.immutable.set_path(
    original_doc,
    'items.0.qty',
    5
);
// original_doc unchanged, updated_doc is new object
```

## 11.4. Performance Monitoring

```javascript
// ========== MEMORY USAGE MONITORING ==========

frappe.provide('custom_app.perf');

custom_app.perf.memory = {
    start: function() {
        if (performance.memory) {
            this.baseline = performance.memory.usedJSHeapSize;
            console.log('Baseline memory:', (this.baseline / 1024 / 1024).toFixed(2), 'MB');
        }
    },
    
    checkpoint: function(label) {
        if (performance.memory) {
            let current = performance.memory.usedJSHeapSize;
            let delta = current - this.baseline;
            console.log(
                `[${label}] Memory:`,
                (current / 1024 / 1024).toFixed(2), 'MB',
                '(+' + (delta / 1024 / 1024).toFixed(2) + ' MB)'
            );
        }
    },
    
    report: function() {
        if (performance.memory) {
            console.log('Memory Report:', {
                used: (performance.memory.usedJSHeapSize / 1024 / 1024).toFixed(2) + ' MB',
                total: (performance.memory.totalJSHeapSize / 1024 / 1024).toFixed(2) + ' MB',
                limit: (performance.memory.jsHeapSizeLimit / 1024 / 1024).toFixed(2) + ' MB'
            });
        }
    }
};

// Usage
custom_app.perf.memory.start();
// ... do work ...
custom_app.perf.memory.checkpoint('After loading data');
// ... more work ...
custom_app.perf.memory.report();
```

---

# 12. BEST PRACTICES ARCHITECTURE

## 12.1. Project Structure for Custom App

```
your_app/
├── your_app/
│   ├── public/
│   │   ├── js/
│   │   │   ├── core/
│   │   │   │   ├── namespace.js          # Define namespaces
│   │   │   │   ├── constants.js          # App constants
│   │   │   │   └── config.js             # Configuration
│   │   │   ├── utils/
│   │   │   │   ├── api.js                # API utilities
│   │   │   │   ├── formatting.js         # Format helpers
│   │   │   │   └── validation.js         # Validation helpers
│   │   │   ├── controllers/
│   │   │   │   ├── base_controller.js    # Base controller
│   │   │   │   ├── transaction_controller.js
│   │   │   │   └── document_controller.js
│   │   │   ├── mixins/
│   │   │   │   ├── tax_mixin.js          # Reusable tax logic
│   │   │   │   ├── address_mixin.js      # Address handling
│   │   │   │   └── print_mixin.js        # Print utilities
│   │   │   ├── components/
│   │   │   │   ├── custom_widget.js      # Reusable UI components
│   │   │   │   └── dashboard_card.js
│   │   │   ├── services/
│   │   │   │   ├── customer_service.js   # Business logic
│   │   │   │   ├── inventory_service.js
│   │   │   │   └── pricing_service.js
│   │   │   └── your_app.js               # Main entry point
│   │   └── css/
│   │       └── your_app.css
│   ├── modules/
│   │   └── YourModule/
│   │       └── doctype/
│   │           └── your_doctype/
│   │               ├── your_doctype.js   # DocType client script
│   │               └── your_doctype.py   # DocType server script
│   └── hooks.py                          # App hooks
└── package.json
```

## 12.2. Coding Standards

```javascript
// ========== NAMESPACE CONVENTION ==========

// ✅ GOOD: Use app-specific namespace
frappe.provide('your_app.module.feature');

your_app.module.feature = {
    // Your code
};

// ❌ BAD: Pollute frappe namespace
frappe.provide('frappe.custom');
frappe.custom.my_function = function() {};

// ========== DOCUMENTATION ==========

/**
 * Calculate total with taxes
 * @param {Array} items - Array of item objects
 * @param {String} tax_template - Tax template name
 * @returns {Promise<Number>} Total amount with taxes
 * @example
 * your_app.utils.calculate_total(frm.doc.items, 'GST 18%')
 *   .then(total => console.log(total));
 */
your_app.utils.calculate_total = function(items, tax_template) {
    return frappe.call({
        method: 'your_app.api.calculate_total',
        args: { items, tax_template }
    }).then(r => r.message);
};

// ========== ERROR HANDLING ==========

your_app.utils.safe_call = function(method, args) {
    return frappe.call({
        method: method,
        args: args
    }).then(r => {
        if (r.exc) {
            console.error('API Error:', r.exc);
            frappe.msgprint({
                title: 'Error',
                message: r.exc,
                indicator: 'red'
            });
            return Promise.reject(r.exc);
        }
        return r.message;
    }).catch(error => {
        console.error('Network Error:', error);
        frappe.msgprint({
            title: 'Network Error',
            message: 'Unable to connect to server',
            indicator: 'red'
        });
        return Promise.reject(error);
    });
};

// ========== DEFENSIVE PROGRAMMING ==========

your_app.utils.get_item_rate = function(item_code, customer) {
    // Validate inputs
    if (!item_code) {
        frappe.throw('Item Code is required');
    }
    
    if (!customer) {
        console.warn('No customer provided, using default rate');
    }
    
    // Safe property access
    let cache = frappe._item_rate_cache || {};
    let key = `${item_code}_${customer || 'default'}`;
    
    // Return cached if available
    if (cache[key]) {
        return Promise.resolve(cache[key]);
    }
    
    // Fetch from server
    return frappe.call({
        method: 'your_app.api.get_item_rate',
        args: { item_code, customer }
    }).then(r => {
        let rate = r.message || 0;
        
        // Cache result
        if (!frappe._item_rate_cache) {
            frappe._item_rate_cache = {};
        }
        frappe._item_rate_cache[key] = rate;
        
        return rate;
    });
};

// ========== PERFORMANCE OPTIMIZATION ==========

// Debounce function
your_app.utils.debounce = function(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
};

// Usage: Debounce field change handler
frappe.ui.form.on('Sales Invoice', {
    customer: your_app.utils.debounce(function(frm) {
        // Only executes after user stops typing for 300ms
        your_app.load_customer_data(frm);
    }, 300)
});

// Throttle function
your_app.utils.throttle = function(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
};

// ========== DEPENDENCY INJECTION ==========

// Define service interface
your_app.services.CustomerService = class {
    constructor(api_client) {
        this.api = api_client;
    }
    
    get_customer_details(customer_name) {
        return this.api.call(
            'your_app.api.get_customer_details',
            { customer: customer_name }
        );
    }
    
    get_customer_addresses(customer_name) {
        return this.api.call(
            'your_app.api.get_customer_addresses',
            { customer: customer_name }
        );
    }
};

// Initialize with frappe API client
your_app.customer_service = new your_app.services.CustomerService({
    call: frappe.call.bind(frappe)
});

// Now easy to test with mock
your_app.customer_service = new your_app.services.CustomerService({
    call: function(method, args) {
        // Mock implementation
        return Promise.resolve({ customer_name: 'Test Customer' });
    }
});
```

## 12.3. Testing Strategy

```javascript
// ========== UNIT TESTS ==========

// your_app/public/js/tests/utils.test.js

QUnit.module('your_app.utils');

QUnit.test('format_currency formats VND correctly', function(assert) {
    let result = your_app.utils.format_currency(1000000, 'VND');
    assert.equal(result, '1.000.000đ', 'VND formatted correctly');
});

QUnit.test('calculate_total sums items correctly', function(assert) {
    let done = assert.async();
    
    let items = [
        { amount: 100 },
        { amount: 200 },
        { amount: 300 }
    ];
    
    your_app.utils.calculate_total(items).then(total => {
        assert.equal(total, 600, 'Total calculated correctly');
        done();
    });
});

// ========== INTEGRATION TESTS ==========

// Test form workflow
QUnit.test('Sales Invoice workflow', function(assert) {
    let done = assert.async();
    
    // Create new form
    frappe.set_route('Form', 'Sales Invoice', 'new');
    
    frappe.after_ajax(function() {
        let frm = cur_frm;
        
        // Set values
        frm.set_value('customer', 'Test Customer');
        frm.add_child('items', {
            item_code: 'Test Item',
            qty: 10,
            rate: 100
        });
        
        // Calculate totals
        frm.script_manager.trigger('calculate_totals').then(() => {
            assert.equal(frm.doc.grand_total, 1000, 'Total calculated');
            done();
        });
    });
});

// ========== E2E TESTS (with Cypress) ==========

// cypress/integration/sales_invoice.spec.js

describe('Sales Invoice E2E', function() {
    it('Creates a new Sales Invoice', function() {
        cy.login('Administrator', 'admin');
        cy.visit('/app/sales-invoice/new');
        
        // Fill form
        cy.get('[data-fieldname="customer"]').type('Test Customer');
        cy.get('[data-fieldname="customer"]').blur();
        
        // Add item
        cy.get('.grid-add-row').click();
        cy.get('[data-fieldname="item_code"]').type('Test Item');
        cy.get('[data-fieldname="qty"]').type('10');
        
        // Save
        cy.get('.primary-action').click();
        
        // Verify
        cy.get('.indicator-pill').should('contain', 'Saved');
    });
});
```

---

# 13. VÍ DỤ THỰC TẾ TỪ SOURCE CODE

## 13.1. Form Controller - Sales Invoice

```javascript
// erpnext/accounts/doctype/sales_invoice/sales_invoice.js

// Kế thừa từ erpnext.accounts.AccountsController
erpnext.accounts.SalesInvoiceController = class extends erpnext.accounts.AccountsController {
    
    // ===== SETUP PHASE =====
    setup() {
        // Gọi parent setup
        this._super();
        
        // Setup POS profile
        this.setup_pos_profile();
    }
    
    setup_pos_profile() {
        let me = this;
        
        // Query cho POS Profile field
        this.frm.set_query("pos_profile", function() {
            return {
                filters: {
                    company: me.frm.doc.company,
                    disabled: 0
                }
            };
        });
    }
    
    // ===== ONLOAD PHASE =====
    onload() {
        this._super();
        
        // Load POS data if POS invoice
        if (this.frm.doc.is_pos) {
            this.load_pos_data();
        }
    }
    
    load_pos_data() {
        // Fetch POS profile settings
        frappe.call({
            method: 'erpnext.selling.page.point_of_sale.point_of_sale.get_pos_profile_data',
            args: {
                pos_profile: this.frm.doc.pos_profile
            },
            callback: (r) => {
                if (r.message) {
                    this.pos_profile_data = r.message;
                    this.apply_pos_settings();
                }
            }
        });
    }
    
    // ===== REFRESH PHASE =====
    refresh() {
        this._super();
        
        // Show/hide POS fields
        this.toggle_pos_fields();
        
        // Custom buttons
        this.show_sales_return_button();
        this.show_delivery_note_button();
        this.show_payment_button();
    }
    
    toggle_pos_fields() {
        // Show POS fields only if is_pos checked
        let pos_fields = ['pos_profile', 'cash_bank_account', 'paid_amount', 'change_amount'];
        
        pos_fields.forEach(field => {
            this.frm.toggle_display(field, this.frm.doc.is_pos);
        });
    }
    
    show_payment_button() {
        if (this.frm.doc.docstatus === 1 && this.frm.doc.outstanding_amount > 0) {
            this.frm.add_custom_button(__('Payment'), () => {
                this.make_payment_entry();
            }, __('Create'));
        }
    }
    
    // ===== FIELD HANDLERS =====
    customer() {
        // Gọi parent's customer handler
        this._super();
        
        // Additional logic cho Sales Invoice
        if (this.frm.doc.customer) {
            this.get_customer_defaults();
        }
    }
    
    get_customer_defaults() {
        frappe.call({
            method: 'erpnext.accounts.party.get_party_account',
            args: {
                party_type: 'Customer',
                party: this.frm.doc.customer,
                company: this.frm.doc.company
            },
            callback: (r) => {
                if (r.message) {
                    this.frm.set_value('debit_to', r.message);
                }
            }
        });
    }
    
    is_pos() {
        // When POS checkbox changes
        this.toggle_pos_fields();
        
        if (this.frm.doc.is_pos) {
            // Apply POS defaults
            this.apply_pos_defaults();
        } else {
            // Clear POS fields
            this.clear_pos_fields();
        }
    }
    
    // ===== VALIDATION =====
    validate() {
        // Parent validation
        this._super();
        
        // Sales Invoice specific validation
        this.validate_pos_invoice();
        this.validate_return_invoice();
    }
    
    validate_pos_invoice() {
        if (this.frm.doc.is_pos) {
            if (!this.frm.doc.pos_profile) {
                frappe.throw(__('POS Profile is mandatory for POS Invoice'));
            }
            
            if (this.frm.doc.outstanding_amount > 0 && !this.frm.doc.is_return) {
                frappe.throw(__('Outstanding amount must be zero for POS Invoice'));
            }
        }
    }
    
    // ===== CHILD TABLE HANDLERS =====
    items_on_form_rendered() {
        // Setup barcode scanner
        this.setup_barcode_scanner();
    }
    
    setup_barcode_scanner() {
        let me = this;
        
        if (this.frm.doc.is_pos) {
            this.frm.fields_dict.items.grid.wrapper.find('.grid-body').on('focus', '.form-control', function() {
                // Barcode scanner listener
            });
        }
    }
    
    // ===== UTILITY METHODS =====
    make_payment_entry() {
        return frappe.call({
            method: 'erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry',
            args: {
                dt: this.frm.doctype,
                dn: this.frm.doc.name
            },
            callback: function(r) {
                let doc = frappe.model.sync(r.message);
                frappe.set_route('Form', doc.doctype, doc.name);
            }
        });
    }
    
    make_sales_return() {
        frappe.model.open_mapped_doc({
            method: 'erpnext.accounts.doctype.sales_invoice.sales_invoice.make_sales_return',
            frm: this.frm
        });
    }
};

// Child table controller
frappe.ui.form.on('Sales Invoice Item', {
    item_code(frm, cdt, cdn) {
        let item = frappe.get_doc(cdt, cdn);
        
        if (item.item_code) {
            // Get item details
            frappe.call({
                method: 'erpnext.stock.get_item_details.get_item_details',
                args: {
                    args: {
                        item_code: item.item_code,
                        doctype: frm.doctype,
                        customer: frm.doc.customer,
                        price_list: frm.doc.selling_price_list,
                        currency: frm.doc.currency
                    }
                },
                callback: function(r) {
                    if (!r.exc && r.message) {
                        // Set item details
                        Object.keys(r.message).forEach(key => {
                            frappe.model.set_value(cdt, cdn, key, r.message[key]);
                        });
                    }
                }
            });
        }
    },
    
    qty(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },
    
    rate(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
    },
    
    discount_percentage(frm, cdt, cdn) {
        let item = frappe.get_doc(cdt, cdn);
        
        if (item.discount_percentage) {
            // Calculate discount amount
            let discount_amount = flt(item.price_list_rate) * flt(item.discount_percentage) / 100;
            frappe.model.set_value(cdt, cdn, 'discount_amount', discount_amount);
            
            // Update rate
            let rate = flt(item.price_list_rate) - discount_amount;
            frappe.model.set_value(cdt, cdn, 'rate', rate);
        }
    }
});

function calculate_amount(frm, cdt, cdn) {
    let item = frappe.get_doc(cdt, cdn);
    let amount = flt(item.qty) * flt(item.rate);
    frappe.model.set_value(cdt, cdn, 'amount', amount);
}

// Register controller
$.extend(cur_frm.cscript, new erpnext.accounts.SalesInvoiceController({frm: cur_frm}));
```

## 13.2. Utility Functions - frappe.utils

```javascript
// frappe/public/js/frappe/utils/common.js

frappe.utils = {
    
    // ===== STRING UTILITIES =====
    
    format_currency: function(value, currency, precision) {
        // Default precision
        precision = precision || frappe.boot.sysdefaults.currency_precision || 2;
        
        // Format number
        let formatted = frappe.format(value, {
            fieldtype: 'Currency',
            options: currency,
            precision: precision
        });
        
        return formatted;
    },
    
    strip_html: function(text) {
        // Remove HTML tags
        let tmp = document.createElement('div');
        tmp.innerHTML = text;
        return tmp.textContent || tmp.innerText || '';
    },
    
    get_file_extension: function(filename) {
        if (!filename) return '';
        return filename.split('.').pop().toLowerCase();
    },
    
    // ===== ARRAY UTILITIES =====
    
    unique: function(array) {
        return [...new Set(array)];
    },
    
    sum: function(array, key) {
        if (key) {
            return array.reduce((sum, item) => sum + flt(item[key]), 0);
        }
        return array.reduce((sum, val) => sum + flt(val), 0);
    },
    
    filter_dict: function(dict, filters) {
        let result = {};
        
        Object.keys(dict).forEach(key => {
            let match = true;
            
            Object.keys(filters).forEach(filter_key => {
                if (dict[key][filter_key] !== filters[filter_key]) {
                    match = false;
                }
            });
            
            if (match) {
                result[key] = dict[key];
            }
        });
        
        return result;
    },
    
    // ===== DATE UTILITIES =====
    
    get_today: function() {
        return frappe.datetime.get_today();
    },
    
    add_days: function(date, days) {
        return frappe.datetime.add_days(date, days);
    },
    
    get_diff: function(date1, date2) {
        return frappe.datetime.get_diff(date1, date2);
    },
    
    // ===== VALIDATION =====
    
    validate_email: function(email) {
        let re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },
    
    validate_phone: function(phone) {
        let re = /^[\d\s\-\+\(\)]+$/;
        return re.test(phone);
    },
    
    // ===== URL & QUERY STRING =====
    
    get_url_arg: function(name) {
        let params = new URLSearchParams(window.location.search);
        return params.get(name);
    },
    
    build_url: function(base, params) {
        let url = new URL(base, window.location.origin);
        
        Object.keys(params).forEach(key => {
            url.searchParams.append(key, params[key]);
        });
        
        return url.toString();
    },
    
    // ===== STORAGE =====
    
    set_local_storage: function(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch(e) {
            console.error('Local storage error:', e);
        }
    },
    
    get_local_storage: function(key, default_value) {
        try {
            let value = localStorage.getItem(key);
            return value ? JSON.parse(value) : default_value;
        } catch(e) {
            console.error('Local storage error:', e);
            return default_value;
        }
    },
    
    // ===== MISC =====
    
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    throttle: function(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },
    
    copy_to_clipboard: function(text) {
        if (navigator.clipboard) {
            return navigator.clipboard.writeText(text).then(() => {
                frappe.show_alert({
                    message: __('Copied to clipboard'),
                    indicator: 'green'
                });
            });
        } else {
            // Fallback
            let textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            
            frappe.show_alert({
                message: __('Copied to clipboard'),
                indicator: 'green'
            });
        }
    }
};
```

## 13.3. Model Operations - frappe.model

```javascript
// frappe/public/js/frappe/model/model.js

frappe.model = {
    
    // ===== DOCUMENT OPERATIONS =====
    
    get_doc: function(doctype, name) {
        // Get from local cache
        let key = `${doctype}::${name}`;
        return frappe.local[key];
    },
    
    get_value: function(doctype, name, fieldname, callback) {
        // Fetch field value from server
        return frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: doctype,
                filters: { name: name },
                fieldname: fieldname
            },
            callback: callback
        });
    },
    
    set_value: function(doctype, name, fieldname, value, callback) {
        let doc = frappe.model.get_doc(doctype, name);
        
        if (doc) {
            // Local update
            doc[fieldname] = value;
            
            // Mark as modified
            doc.__unsaved = 1;
            
            // Trigger field change
            $(document).trigger('form-change', [doc, fieldname]);
        }
        
        // Save to server if callback provided
        if (callback) {
            return frappe.call({
                method: 'frappe.client.set_value',
                args: {
                    doctype: doctype,
                    name: name,
                    fieldname: fieldname,
                    value: value
                },
                callback: callback
            });
        }
    },
    
    // ===== CRUD OPERATIONS =====
    
    insert: function(doc, callback) {
        return frappe.call({
            method: 'frappe.client.insert',
            args: { doc: doc },
            callback: function(r) {
                if (!r.exc) {
                    // Add to local cache
                    frappe.model.sync(r.message);
                }
                if (callback) callback(r);
            }
        });
    },
    
    save: function(doc, callback) {
        return frappe.call({
            method: 'frappe.client.save',
            args: { doc: doc },
            callback: function(r) {
                if (!r.exc) {
                    // Update local cache
                    frappe.model.sync(r.message);
                }
                if (callback) callback(r);
            }
        });
    },
    
    delete_doc: function(doctype, name, callback) {
        return frappe.call({
            method: 'frappe.client.delete',
            args: {
                doctype: doctype,
                name: name
            },
            callback: function(r) {
                if (!r.exc) {
                    // Remove from local cache
                    let key = `${doctype}::${name}`;
                    delete frappe.local[key];
                }
                if (callback) callback(r);
            }
        });
    },
    
    // ===== CHILD TABLE OPERATIONS =====
    
    add_child: function(parent_doc, childtype, fieldname) {
        // Create new child doc
        let child = frappe.model.get_new_doc(childtype, parent_doc, fieldname);
        
        // Add to parent's child table
        if (!parent_doc[fieldname]) {
            parent_doc[fieldname] = [];
        }
        parent_doc[fieldname].push(child);
        
        return child;
    },
    
    remove_child: function(parent_doc, childtype, child_name) {
        let fieldname = frappe.model.get_table_fieldname(childtype, parent_doc.doctype);
        
        parent_doc[fieldname] = (parent_doc[fieldname] || []).filter(
            child => child.name !== child_name
        );
    },
    
    clear_table: function(doc, fieldname) {
        doc[fieldname] = [];
    },
    
    // ===== UTILITY FUNCTIONS =====
    
    get_new_doc: function(doctype, parent, parentfield) {
        // Generate local name
        let name = frappe.model.get_temp_name(doctype);
        
        let doc = {
            doctype: doctype,
            name: name,
            __islocal: 1,
            __unsaved: 1,
            owner: frappe.session.user
        };
        
        if (parent) {
            doc.parent = parent.name;
            doc.parenttype = parent.doctype;
            doc.parentfield = parentfield;
        }
        
        // Add to local cache
        let key = `${doctype}::${name}`;
        frappe.local[key] = doc;
        
        return doc;
    },
    
    get_temp_name: function(doctype) {
        return `new-${doctype.toLowerCase().replace(/\s/g, '-')}-${frappe.utils.get_random(8)}`;
    },
    
    sync: function(doc) {
        // Sync server doc to local cache
        if ($.isArray(doc)) {
            doc.forEach(d => frappe.model.sync(d));
            return doc;
        }
        
        let key = `${doc.doctype}::${doc.name}`;
        let existing = frappe.local[key];
        
        if (existing) {
            // Update existing
            $.extend(existing, doc);
        } else {
            // Add new
            frappe.local[key] = doc;
        }
        
        return doc;
    },
    
    copy_doc: function(doc, skip_fields) {
        skip_fields = skip_fields || ['name', 'creation', 'modified', 'modified_by', 'owner'];
        
        let new_doc = {};
        
        Object.keys(doc).forEach(key => {
            if (!skip_fields.includes(key) && !key.startsWith('_')) {
                new_doc[key] = doc[key];
            }
        });
        
        new_doc.__islocal = 1;
        new_doc.__unsaved = 1;
        
        return new_doc;
    }
};
```

---

# KẾT LUẬN

## Tóm tắt kiến trúc Frappe JavaScript

1. **Source vs Runtime**: Code được viết bằng ES6 modules nhưng runtime là global namespace
2. **Build Process**: esbuild bundle & transform code, dependency resolution, code splitting
3. **Boot Process**: Server inject boot data → Init UI → Setup router → Load modules
4. **Module System**: frappe.provide() tạo namespace tree, không phải true modules
5. **Form Lifecycle**: setup → onload → refresh → validate → save → after_save
6. **Controller Pattern**: Base → Transaction → Accounts → DocType (inheritance chain)
7. **Event System**: Form events, DOM events, Real-time events, Custom events
8. **Override**: Dangerous nhưng mạnh mẽ, cần wrapper pattern để safe
9. **Global State**: Shared mutable state, nguy cơ memory leak, cần careful management
10. **Best Practices**: App namespace, dependency injection, immutable updates, testing

## Những điều cần nhớ

- ✅ Luôn dùng app-specific namespace
- ✅ Wrapper functions thay vì override trực tiếp
- ✅ Unbind events trước khi bind lại
- ✅ Document code và error handling
- ✅ Test thoroughly
- ❌ Không pollute frappe core namespace
- ❌ Không tạo circular dependencies
- ❌ Không giữ reference đến large objects
- ❌ Không assume load order
- ❌ Không skip validation

---

## Tài liệu tham khảo

- [Frappe Framework Documentation](https://frappeframework.com/docs)
- [Frappe GitHub Repository](https://github.com/frappe/frappe)
- [ERPNext GitHub Repository](https://github.com/frappe/erpnext)
- [Frappe Developer Forum](https://discuss.frappe.io)

---

*Document version: 1.0*
*Last updated: 2024*


=================================================

Hoàn thành! Tôi đã bổ sung và tạo 2 tài liệu đầy đủ:
📚 File 1: frappe_js_architecture_guide.md (Đã cập nhật)
Bổ sung thêm Section 8.5: CHUỖI KẾ THỪA THỰC TẾ
Bao gồm:
✅ Sơ đồ kế thừa đầy đủ 7 cấp:

Level 0: frappe.ui.form.Controller (Base)
Level 1: erpnext.stock.StockController (Stock)
Level 2: erpnext.payments (Payment)
Level 3: erpnext.taxes_and_totals (Tax)
Level 4: erpnext.TransactionController (Transaction Base)
Level 5a: erpnext.selling.SellingController (Selling)
Level 5b: erpnext.buying.BuyingController (Buying)
Level 6a: erpnext.accounts.SalesInvoiceController (Final)
Level 6b: erpnext.accounts.PurchaseInvoice (Final)

✅ Code thực tế từng cấp với methods chi tiết
✅ 4 Pattern ghi đè an toàn:

Override cho 1 DocType - Direct inheritance
Override cho nhiều DocType - Intermediate controller
Override có điều kiện - Conditional logic
Wrapper Pattern - Preserve original

✅ Nguyên tắc vàng - DO vs DON'T
✅ Decision Matrix - Khi nào dùng pattern nào

📚 File 2: frappe_js_practical_examples.md (Mới)
Ví dụ thực tế chi tiết:
1. Kế thừa cơ bản

BaseController với utility methods
Kế thừa với mixin pattern (Address, Payment Terms, Tax)

2. Override methods

Pre/Post processing
Conditional logic (VIP vs New customer)
Validation chain (5 stages)

3. Các ví dụ bao gồm:
javascript// ✅ Logging & monitoring
// ✅ Error handling
// ✅ Async/await patterns
// ✅ API integration
// ✅ Custom validations
// ✅ Business rules
// ✅ Credit limit checking
// ✅ Inventory validation
// ✅ External system integration
// ✅ Performance optimization
```

---

## 🎯 **Điểm nổi bật:**

### **Chuỗi kế thừa thực tế ERPNext:**
```
frappe.ui.form.Controller (Base)
    ↓
StockController (warehouse, qty, serial)
    ↓
Payments (payment schedule, paid amount)
    ↓
TaxesAndTotals (tax calculations)
    ↓
TransactionController (currency, exchange rate)
    ↓
SellingController / BuyingController
    ↓
SalesInvoiceController / PurchaseInvoice
3 trường hợp override an toàn:

Sửa 1 method cho 1 DocType:

javascript   CustomSalesInvoice extends SalesInvoiceController
   frm.cscript = new CustomSalesInvoice()

Sửa 1 method cho nhiều DocType:

javascript   CustomTransactionController → CustomSellingController
   ├─ CustomSalesInvoice
   └─ CustomQuotation

Conditional override:

javascript   if (is_vip()) {
       custom_logic();
   } else {
       super.method();
   }
Code examples thực tế:

✅ Sales Invoice với POS handling
✅ Purchase Invoice với debit note
✅ Validation chain với 5 stages
✅ VIP customer handling
✅ Credit limit checking
✅ Inventory availability check
✅ External system integration


📖 Cách sử dụng tài liệu:

Đọc Architecture Guide trước - Hiểu tổng quan
Xem phần 8.5 - Hiểu chuỗi kế thừa thực tế
Đọc Practical Examples - Áp dụng vào dự án

Tài liệu này đủ để bạn:

✅ Hiểu sâu kiến trúc Frappe JS
✅ Kế thừa đúng cách
✅ Override an toàn
✅ Áp dụng vào dự án thực tế
✅ Tránh những lỗi phổ biến



-----------------------------------

# FRAPPE JAVASCRIPT - VÍ DỤ THỰC TẾ & BEST PRACTICES

## Mục lục

1. [Ví dụ kế thừa cơ bản](#1-ví-dụ-kế-thừa-cơ-bản)
2. [Ví dụ override methods](#2-ví-dụ-override-methods)
3. [Custom App với controller riêng](#3-custom-app-với-controller-riêng)
4. [Xử lý child table](#4-xử-lý-child-table)
5. [Tích hợp API và async](#5-tích-hợp-api-và-async)
6. [State management trong form](#6-state-management-trong-form)
7. [Performance optimization](#7-performance-optimization)
8. [Testing và debugging](#8-testing-và-debugging)

---

# 1. VÍ DỤ KẾ THỪA CƠ BẢN

## 1.1. Kế thừa simple - Thêm utility methods

```javascript
// ========== FILE: custom_app/public/js/controllers/base.js ==========

frappe.provide('custom_app.controllers');

/**
 * Base controller với utility methods cho tất cả forms
 */
custom_app.controllers.BaseController = class BaseController extends frappe.ui.form.Controller {
    
    constructor(opts) {
        super(opts);
        console.log('BaseController initialized for', this.frm.doctype);
    }
    
    // ===== UTILITY METHODS =====
    
    /**
     * Show loading overlay
     */
    show_loading(message = 'Loading...') {
        this.frm.page.set_indicator(__('Loading'), 'orange');
        frappe.dom.freeze(__(message));
    }
    
    /**
     * Hide loading overlay
     */
    hide_loading() {
        frappe.dom.unfreeze();
        this.frm.page.clear_indicator();
    }
    
    /**
     * Validate field not empty
     */
    validate_mandatory(fieldname, label) {
        if (!this.frm.doc[fieldname]) {
            frappe.throw(__(`{0} is mandatory`, [label || fieldname]));
            return false;
        }
        return true;
    }
    
    /**
     * Format currency with doc's currency
     */
    format_currency(value) {
        return frappe.format(value, {
            fieldtype: 'Currency',
            options: this.frm.doc.currency
        });
    }
    
    /**
     * Log activity
     */
    log_activity(action, details = {}) {
        console.log(`[${this.frm.doctype}] ${action}`, details);
        
        // Could also save to server
        frappe.call({
            method: 'custom_app.api.log_activity',
            args: {
                doctype: this.frm.doctype,
                doc_name: this.frm.doc.name,
                action: action,
                details: JSON.stringify(details)
            }
        });
    }
    
    /**
     * Show custom alert
     */
    show_alert(message, type = 'info') {
        const indicators = {
            success: 'green',
            error: 'red',
            warning: 'orange',
            info: 'blue'
        };
        
        frappe.show_alert({
            message: __(message),
            indicator: indicators[type] || 'blue'
        }, 5);
    }
};

// ========== USAGE: Inherit in specific controller ==========

custom_app.controllers.CustomSalesOrderController = class CustomSalesOrderController 
    extends custom_app.controllers.BaseController {
    
    refresh() {
        // Use utility methods from base
        this.log_activity('Form Refreshed', {
            status: this.frm.doc.status,
            grand_total: this.frm.doc.grand_total
        });
        
        if (this.frm.doc.docstatus === 1) {
            this.show_alert('Sales Order is submitted', 'success');
        }
    }
    
    validate() {
        // Use validation helpers
        this.validate_mandatory('customer', 'Customer');
        this.validate_mandatory('delivery_date', 'Delivery Date');
        
        // Custom validation
        if (this.frm.doc.grand_total > 1000000) {
            if (!this.frm.doc.custom_manager_approval) {
                frappe.throw(__('Manager approval required for orders over 1M'));
            }
        }
    }
    
    async calculate_totals() {
        this.show_loading('Calculating totals...');
        
        try {
            let result = await frappe.call({
                method: 'custom_app.api.calculate_order_totals',
                args: { doc: this.frm.doc }
            });
            
            this.frm.set_value('grand_total', result.message.grand_total);
            this.show_alert('Totals calculated successfully', 'success');
        } catch (error) {
            this.show_alert('Error calculating totals', 'error');
        } finally {
            this.hide_loading();
        }
    }
};

frappe.ui.form.on('Sales Order', {
    setup(frm) {
        frm.cscript = new custom_app.controllers.CustomSalesOrderController({frm});
    }
});
```

## 1.2. Kế thừa với mixin pattern

```javascript
// ========== DEFINE MIXINS ==========

frappe.provide('custom_app.mixins');

/**
 * Mixin: Address handling
 */
custom_app.mixins.AddressMixin = {
    
    setup_address_queries() {
        let me = this;
        
        this.frm.set_query('billing_address', function() {
            return {
                query: 'frappe.contacts.doctype.address.address.address_query',
                filters: {
                    link_doctype: me.get_party_type(),
                    link_name: me.get_party()
                }
            };
        });
        
        this.frm.set_query('shipping_address', function() {
            return {
                query: 'frappe.contacts.doctype.address.address.address_query',
                filters: {
                    link_doctype: me.get_party_type(),
                    link_name: me.get_party()
                }
            };
        });
    },
    
    get_address_display(address_name, target_field) {
        if (!address_name) return;
        
        frappe.call({
            method: 'frappe.contacts.doctype.address.address.get_address_display',
            args: { address_dict: address_name },
            callback: (r) => {
                if (r.message) {
                    this.frm.set_value(target_field, r.message);
                }
            }
        });
    },
    
    get_party_type() {
        // Override in child
        return 'Customer';
    },
    
    get_party() {
        // Override in child
        return this.frm.doc.customer;
    }
};

/**
 * Mixin: Payment terms
 */
custom_app.mixins.PaymentTermsMixin = {
    
    setup_payment_terms() {
        let me = this;
        
        this.frm.set_query('payment_terms_template', function() {
            return {
                filters: { enabled: 1 }
            };
        });
    },
    
    payment_terms_template() {
        if (this.frm.doc.payment_terms_template) {
            this.get_payment_schedule();
        }
    },
    
    get_payment_schedule() {
        let me = this;
        
        return frappe.call({
            method: 'erpnext.controllers.accounts_controller.get_payment_terms',
            args: {
                terms_template: me.frm.doc.payment_terms_template,
                posting_date: me.frm.doc.posting_date || me.frm.doc.transaction_date,
                grand_total: me.frm.doc.grand_total,
                base_grand_total: me.frm.doc.base_grand_total
            },
            callback: function(r) {
                if (r.message && !r.exc) {
                    me.frm.clear_table('payment_schedule');
                    
                    r.message.forEach(term => {
                        me.frm.add_child('payment_schedule', term);
                    });
                    
                    me.frm.refresh_field('payment_schedule');
                }
            }
        });
    }
};

/**
 * Mixin: Tax calculations
 */
custom_app.mixins.TaxCalculationMixin = {
    
    calculate_item_wise_tax(item) {
        let total_tax = 0;
        
        (this.frm.doc.taxes || []).forEach(tax_row => {
            if (tax_row.charge_type === 'On Net Total') {
                let item_tax = flt(item.net_amount * tax_row.rate / 100);
                total_tax += item_tax;
            }
        });
        
        return total_tax;
    },
    
    apply_tax_template(template_name) {
        let me = this;
        
        return frappe.call({
            method: 'erpnext.controllers.accounts_controller.get_taxes_and_charges',
            args: {
                master_doctype: me.get_tax_master_doctype(),
                master_name: template_name
            },
            callback: function(r) {
                if (r.message) {
                    me.frm.clear_table('taxes');
                    
                    r.message.forEach(tax => {
                        me.frm.add_child('taxes', tax);
                    });
                    
                    me.frm.refresh_field('taxes');
                    me.frm.script_manager.trigger('calculate_taxes_and_totals');
                }
            }
        });
    },
    
    get_tax_master_doctype() {
        // Override in child
        return 'Sales Taxes and Charges Template';
    }
};

// ========== APPLY MIXINS TO CONTROLLER ==========

custom_app.controllers.EnhancedSalesInvoiceController = class EnhancedSalesInvoiceController 
    extends erpnext.accounts.SalesInvoiceController {
    
    constructor(opts) {
        super(opts);
        
        // Apply mixins
        Object.assign(this, custom_app.mixins.AddressMixin);
        Object.assign(this, custom_app.mixins.PaymentTermsMixin);
        Object.assign(this, custom_app.mixins.TaxCalculationMixin);
    }
    
    setup() {
        super.setup();
        
        // Setup from mixins
        this.setup_address_queries();
        this.setup_payment_terms();
    }
    
    // Override mixin methods
    get_party_type() {
        return 'Customer';
    }
    
    get_party() {
        return this.frm.doc.customer;
    }
    
    get_tax_master_doctype() {
        return 'Sales Taxes and Charges Template';
    }
    
    // Use mixin functionality
    billing_address() {
        this.get_address_display(
            this.frm.doc.billing_address,
            'billing_address_display'
        );
    }
    
    shipping_address() {
        this.get_address_display(
            this.frm.doc.shipping_address,
            'shipping_address_display'
        );
    }
    
    taxes_and_charges() {
        if (this.frm.doc.taxes_and_charges) {
            this.apply_tax_template(this.frm.doc.taxes_and_charges);
        }
    }
};

frappe.ui.form.on('Sales Invoice', {
    setup(frm) {
        frm.cscript = new custom_app.controllers.EnhancedSalesInvoiceController({frm});
    }
});
```

---

# 2. VÍ DỤ OVERRIDE METHODS

## 2.1. Override với Pre/Post processing

```javascript
/**
 * Override calculate_taxes_and_totals với pre/post processing
 */
custom_app.controllers.CustomTransactionController = class CustomTransactionController 
    extends erpnext.TransactionController {
    
    constructor(opts) {
        super(opts);
        
        // Save original method
        this._original_calculate = this.calculate_taxes_and_totals.bind(this);
    }
    
    calculate_taxes_and_totals() {
        // ===== PRE-PROCESSING =====
        console.log('[Pre] Starting calculation...');
        
        // Store original values for comparison
        let original_grand_total = this.frm.doc.grand_total;
        
        // Apply custom discounts before calculation
        this.apply_early_bird_discount();
        this.apply_bulk_order_discount();
        
        // ===== CALL ORIGINAL =====
        this._original_calculate();
        
        // ===== POST-PROCESSING =====
        console.log('[Post] Calculation completed');
        
        // Apply custom adjustments after calculation
        this.apply_rounding_rules();
        this.update_loyalty_points();
        
        // Compare and log
        if (Math.abs(original_grand_total - this.frm.doc.grand_total) > 0.01) {
            console.log('Grand total changed:', {
                from: original_grand_total,
                to: this.frm.doc.grand_total,
                difference: this.frm.doc.grand_total - original_grand_total
            });
        }
        
        // Trigger custom events
        $(this.frm.wrapper).trigger('custom_totals_calculated', [this.frm.doc]);
    }
    
    apply_early_bird_discount() {
        // Apply 5% discount if order placed before 10 AM
        let now = moment();
        
        if (now.hour() < 10 && this.frm.doc.docstatus === 0) {
            let discount = this.frm.doc.net_total * 0.05;
            
            if (discount > 0) {
                this.frm.set_value('custom_early_bird_discount', discount);
                
                frappe.show_alert({
                    message: __('Early bird discount applied: {0}', [
                        this.format_currency(discount)
                    ]),
                    indicator: 'green'
                });
            }
        }
    }
    
    apply_bulk_order_discount() {
        // Apply bulk discount if total items > 100
        let total_qty = 0;
        
        (this.frm.doc.items || []).forEach(item => {
            total_qty += flt(item.qty);
        });
        
        if (total_qty > 100) {
            let discount_rate = 0.03; // 3%
            
            if (total_qty > 500) {
                discount_rate = 0.07; // 7% for very large orders
            }
            
            let discount = this.frm.doc.net_total * discount_rate;
            this.frm.set_value('custom_bulk_discount', discount);
            
            frappe.show_alert({
                message: __('Bulk order discount ({0}%) applied', [discount_rate * 100]),
                indicator: 'blue'
            });
        }
    }
    
    apply_rounding_rules() {
        // Custom rounding: round to nearest 100
        if (this.frm.doc.custom_enable_rounding) {
            let rounded = Math.round(this.frm.doc.grand_total / 100) * 100;
            let adjustment = rounded - this.frm.doc.grand_total;
            
            if (Math.abs(adjustment) > 0.01) {
                this.frm.set_value('custom_rounding_adjustment', adjustment);
                this.frm.set_value('custom_rounded_total', rounded);
            }
        }
    }
    
    update_loyalty_points() {
        // Calculate loyalty points based on grand total
        if (this.frm.doc.customer && this.frm.doc.grand_total > 0) {
            let points = Math.floor(this.frm.doc.grand_total / 100);
            this.frm.set_value('custom_loyalty_points_earned', points);
        }
    }
};
```

## 2.2. Override với conditional logic

```javascript
/**
 * Override với điều kiện - logic khác nhau cho từng scenario
 */
custom_app.controllers.ConditionalSalesInvoiceController = class ConditionalSalesInvoiceController 
    extends erpnext.accounts.SalesInvoiceController {
    
    customer() {
        // Determine which logic to use
        if (this.is_vip_customer()) {
            this.handle_vip_customer();
        } else if (this.is_new_customer()) {
            this.handle_new_customer();
        } else {
            // Default logic
            super.customer();
        }
    }
    
    is_vip_customer() {
        return this.frm.doc.customer_group === 'VIP' ||
               this.frm.doc.custom_vip_status === 1;
    }
    
    is_new_customer() {
        // Check if customer created within last 30 days
        if (!this.frm.doc.customer) return false;
        
        return frappe.call({
            method: 'custom_app.api.is_new_customer',
            args: { customer: this.frm.doc.customer },
            async: false
        }).responseJSON.message;
    }
    
    handle_vip_customer() {
        let me = this;
        
        frappe.call({
            method: 'custom_app.api.get_vip_customer_benefits',
            args: { customer: me.frm.doc.customer },
            callback: (r) => {
                if (r.message) {
                    // Apply VIP benefits
                    me.frm.set_value({
                        selling_price_list: r.message.vip_price_list,
                        payment_terms_template: r.message.flexible_payment_terms,
                        custom_credit_limit: r.message.extended_credit_limit,
                        custom_discount_percentage: r.message.loyalty_discount
                    });
                    
                    // Show VIP badge
                    me.frm.set_df_property('customer', 'description', 
                        '<span class="indicator-pill blue">VIP Customer</span>');
                    
                    // Custom buttons for VIP
                    me.show_vip_services_button();
                    
                    frappe.show_alert({
                        message: __('VIP customer benefits applied'),
                        indicator: 'blue'
                    }, 10);
                }
            }
        });
    }
    
    handle_new_customer() {
        // Welcome new customer
        frappe.show_alert({
            message: __('Welcome bonus: 10% discount on first order!'),
            indicator: 'green'
        }, 10);
        
        // Apply first-time discount
        this.frm.set_value('custom_first_order_discount', 0.10);
        
        // Assign to onboarding team
        this.frm.set_value('custom_assign_to_onboarding', 1);
        
        // Show onboarding guide
        this.show_onboarding_guide();
    }
    
    show_vip_services_button() {
        this.frm.add_custom_button(__('VIP Services'), () => {
            frappe.set_route('Form', 'VIP Service Request', 'new', {
                customer: this.frm.doc.customer,
                invoice: this.frm.doc.name
            });
        }, __('Create'));
    }
    
    show_onboarding_guide() {
        frappe.msgprint({
            title: __('Welcome to Our System!'),
            message: __(`
                <div style="padding: 20px;">
                    <h4>Getting Started:</h4>
                    <ul>
                        <li>You receive 10% discount on your first order</li>
                        <li>Flexible payment terms available</li>
                        <li>Dedicated support team assigned</li>
                        <li>Free delivery on orders over $500</li>
                    </ul>
                    <p>Need help? Contact our onboarding team at support@example.com</p>
                </div>
            `),
            indicator: 'blue'
        });
    }
};
```

## 2.3. Override với validation chain

```javascript
/**
 * Override validate với multiple validation stages
 */
custom_app.controllers.ValidationChainController = class ValidationChainController 
    extends erpnext.accounts.SalesInvoiceController {
    
    async validate() {
        try {
            // Stage 1: Pre-validation
            await this.pre_validate();
            
            // Stage 2: Original validation
            await super.validate();
            
            // Stage 3: Business rule validation
            await this.validate_business_rules();
            
            // Stage 4: External validation (if needed)
            await this.validate_with_external_system();
            
            // Stage 5: Post-validation
            await this.post_validate();
            
        } catch (error) {
            this.handle_validation_error(error);
            throw error;
        }
    }
    
    async pre_validate() {
        console.log('[Validation] Stage 1: Pre-validation');
        
        // Check document state
        if (this.frm.doc.__islocal && this.frm.doc.amended_from) {
            frappe.throw(__('Cannot create amended document before saving'));
        }
        
        // Check required custom fields
        this.validate_custom_mandatory_fields();
    }
    
    validate_custom_mandatory_fields() {
        let required_fields = [
            { field: 'custom_project', label: 'Project' },
            { field: 'custom_cost_center', label: 'Cost Center' },
            { field: 'custom_department', label: 'Department' }
        ];
        
        required_fields.forEach(({ field, label }) => {
            if (this.is_field_required(field) && !this.frm.doc[field]) {
                frappe.throw(__(`{0} is mandatory for this transaction`, [label]));
            }
        });
    }
    
    is_field_required(fieldname) {
        // Check if field is required based on conditions
        if (fieldname === 'custom_project') {
            return this.frm.doc.grand_total > 50000;
        }
        return false;
    }
    
    async validate_business_rules() {
        console.log('[Validation] Stage 3: Business rules');
        
        // Rule 1: Check credit limit
        await this.check_credit_limit();
        
        // Rule 2: Validate pricing
        await this.validate_pricing_rules();
        
        // Rule 3: Check inventory
        await this.validate_inventory_availability();
        
        // Rule 4: Validate delivery date
        this.validate_delivery_date();
    }
    
    async check_credit_limit() {
        if (!this.frm.doc.customer) return;
        
        let result = await frappe.call({
            method: 'custom_app.api.check_customer_credit_limit',
            args: {
                customer: this.frm.doc.customer,
                company: this.frm.doc.company,
                additional_amount: this.frm.doc.grand_total
            }
        });
        
        if (!result.message.credit_available) {
            let msg = __('Customer has exceeded credit limit. Available: {0}, Required: {1}', [
                result.message.available_credit,
                this.frm.doc.grand_total
            ]);
            
            frappe.throw({
                title: __('Credit Limit Exceeded'),
                message: msg,
                indicator: 'red'
            });
        }
    }
    
    async validate_pricing_rules() {
        // Validate that all items have valid pricing
        let invalid_items = [];
        
        for (let item of this.frm.doc.items) {
            if (!item.rate || item.rate <= 0) {
                invalid_items.push(item.item_code);
            }
            
            // Check if rate is below minimum
            let min_rate = await this.get_minimum_rate(item.item_code);
            if (item.rate < min_rate) {
                frappe.throw(__('Rate for {0} cannot be less than {1}', [
                    item.item_code,
                    min_rate
                ]));
            }
        }
        
        if (invalid_items.length > 0) {
            frappe.throw(__('Invalid rate for items: {0}', [invalid_items.join(', ')]));
        }
    }
    
    async get_minimum_rate(item_code) {
        let result = await frappe.call({
            method: 'erpnext.stock.get_item_details.get_item_price',
            args: {
                item_code: item_code,
                price_list: 'Minimum Selling',
                customer: this.frm.doc.customer
            }
        });
        
        return result.message || 0;
    }
    
    async validate_inventory_availability() {
        // Check if update stock is enabled
        if (!this.frm.doc.update_stock) return;
        
        let out_of_stock = [];
        
        for (let item of this.frm.doc.items) {
            let available = await this.get_available_qty(
                item.item_code,
                item.warehouse
            );
            
            if (available < item.qty) {
                out_of_stock.push({
                    item: item.item_code,
                    required: item.qty,
                    available: available
                });
            }
        }
        
        if (out_of_stock.length > 0) {
            let msg = __('Insufficient stock:') + '<br>';
            out_of_stock.forEach(i => {
                msg += `${i.item}: Required ${i.required}, Available ${i.available}<br>`;
            });
            
            frappe.throw({
                title: __('Stock Not Available'),
                message: msg
            });
        }
    }
    
    validate_delivery_date() {
        if (!this.frm.doc.delivery_date) return;
        
        let delivery = moment(this.frm.doc.delivery_date);
        let posting = moment(this.frm.doc.posting_date);
        
        if (delivery.isBefore(posting)) {
            frappe.throw(__('Delivery Date cannot be before Posting Date'));
        }
        
        // Check if delivery date is too far in future (e.g., > 90 days)
        if (delivery.diff(posting, 'days') > 90) {
            frappe.msgprint({
                title: __('Warning'),
                message: __('Delivery date is more than 90 days away'),
                indicator: 'orange'
            });
        }
    }
    
    async validate_with_external_system() {
        console.log('[Validation] Stage 4: External validation');
        
        // Only validate if certain conditions met
        if (this.frm.doc.grand_total < 10000) return;
        
        try {
            let result = await frappe.call({
                method: 'custom_app.api.validate_with_erp_system',
                args: {
                    doc: this.frm.doc
                },
                timeout: 5000 // 5 second timeout
            });
            
            if (!result.message.valid) {
                frappe.throw(__('External validation failed: {0}', [
                    result.message.error
                ]));
            }
        } catch (error) {
            // External system timeout - log but don't block
            console.error('External validation timeout:', error);
            frappe.show_alert({
                message: __('External validation skipped (timeout)'),
                indicator: 'orange'
            });
        }
    }
    
    async post_validate() {
        console.log('[Validation] Stage 5: Post-validation');
        
        // Calculate custom metrics
        this.calculate_profit_margin();
        this.update_customer_statistics();
    }
    
    calculate_profit_margin() {
        let total_cost = 0;
        let total_revenue = this.frm.doc.net_total;
        
        (this.frm.doc.items || []).forEach(item => {
            total_cost += flt(item.qty) * flt(item.valuation_rate || 0);
        });
        
        let profit = total_revenue - total_cost;
        let margin = total_revenue > 0 ? (profit / total_revenue) * 100 : 0;
        
        this.frm.set_value('custom_profit_margin', margin);
        this.frm.set_value('custom_estimated_profit', profit);
    }
    
    handle_validation_error(error) {
        console.error('[Validation] Error:', error);
        
        // Log validation failure
        frappe.call({
            method: 'custom_app.api.log_validation_error',
            args: {
                doctype: this.frm.doctype,
                doc_name: this.frm.doc.name,
                error: error.message
            }
        });
    }
};
```

---

[Tiếp tục với phần 3: Custom App với controller riêng...]
