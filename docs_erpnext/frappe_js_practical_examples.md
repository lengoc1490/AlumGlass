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
