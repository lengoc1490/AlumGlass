---
title: "BOM Price Calculation on Quotation (Preview / Calculate dialog)"
contexts:
  - "Form/Quotation"
tags: [sales-crm]
doc_type: doctype
---

# BOM Price Calculation on Quotation

## What this is

When preparing an AlumGlass quotation in **Quotation**, each product line
(Quotation Item) is linked to a **BOM** (`al_bom`) and a frozen version
(`al_bom_version`). The **Calculate** / **Preview price** action runs the
7-phase `BomOrchestrator` (B0–B7) to compute each material line cost →
group into cost buckets → run the Cost Template → produce the **VAT-inclusive
selling price** (`al_gia_vat`).

## How to use

The pricing actions live on **each Quotation Item row** (no more form-level
toolbar buttons):

- Each row has **two small buttons at the right corner of the item_code field**:
  **📐** opens the **BOM Parameters** dialog and **🖥️** runs **Preview price**
  directly (no need to expand the row; if no BOM is selected yet it prompts to
  open 📐 first). **Double-clicking** the row also opens the BOM Parameters
  dialog.
- When a row is expanded (grid form), two buttons appear at the **top** of the
  expanded form: **📐 BOM Parameters** and **🖥️ Preview price**.

Inside the **BOM Parameters** dialog:

1. **Select BOM** section: pick a **BOM** (`al_bom`) + **BOM Version**. Below,
   the **Product info** section shows **read-only fields** (standard Data
   fields, 2-column layout): **BOM**, **Bom Set**, **Variable Set**, **Profile
   system**, **Aluminum brand**, **Accessory Set** — each cell shows
   `name (code)` (the **Accessory Set** cell shows the set name), missing data
   renders as **"—"**. These cells update automatically when the BOM changes
   (no dialog recreation).
2. The system generates the parameter form from the BOM's **Variable Set** with
   a spacious **3-column** layout (both **Input variables** and **System
   variables**). System variables (`is_system`) show their **label + default
   value** and are **editable**.
3. Changing the BOM **re-renders the parameter section + BOM info in place** (no
   dialog recreation, no flicker, position/size preserved).
4. To add parameters not in the Variable Set, add rows in the **Extra
   variables** table (standard Frappe Table field, rows can be added/deleted).
   The **Variable name** column is a **Link → AL Variable Library** (only
   `is_system = 0` variables shown); after picking, the **Type** column is
   auto-filled from the Library. Allowed types: Data / Float / Int / Select /
   Link / Check / Currency.
5. Click **💾 Save** to persist the parameters to the row, or **🖥️ Preview
   price** to see the result immediately.
6. The dialog shows: **Cost Breakdown** (Cost Template lines: TONG_VL, NC_SX,
   NC_LD, TONG_NC, OH_VC, OH_QLY, GIA_THANH, PROFIT, GIA_BAN, DON_GIA_M2, VAT,
   GIA_VAT…), **Cost Buckets**, and the material line detail table (slug, item,
   W/H, qty, unit price, line total).
7. Results are saved to the item: `al_gia_vat` (VAT-inclusive price),
   `al_gia_ban` (pre-VAT), `al_bom_result` (full JSON: buckets/cost_template/
   lines).

## Large BOM — background calculation (async)

- BOMs with line count ≤ the **ASYNC_BOM_THRESHOLD** (default **150**, editable
  in Formula Global Variable) run **synchronously** — results appear instantly.
- BOMs larger than the threshold are queued as a **background job** (long
  queue): the dialog shows a "calculating in background" spinner, and the
  result **appears automatically** via realtime when done (no need to click
  again).
- **Reopening the dialog:** the system reads the saved item state
  (`al_calc_status`). If still calculating in background → shows a waiting
  message without re-calling. If already done → shows the saved result
  immediately. If failed → shows the error (details in `al_calc_error` /
  Error Log).

## Notes

- Pricing uses the **frozen version** (`al_bom_version`): the BOM Set, Cost
  Template and **Pricing Dimension** snapshots captured at publish time —
  changing config later does not change a quotation already priced.
- Do not edit `al_gia_vat` / `al_bom_result` directly — they are calculation
  outputs (read-only).
