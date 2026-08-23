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
  they appear **immediately when the form opens with existing rows** (no need to
  add a row or reload) — the form retries attaching buttons after the grid
  finishes rendering rows (up to ~5 seconds; idempotent, stops once attached,
  never duplicates buttons on re-render).
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
6. Results render through a **shared renderer**
   (`alumglass.render_bom_result_display`, the same renderer used by the 🖥️
   dialog):
   - **Summary bar**: selling price (`GIA_BAN`), VAT (`GIA_VAT`), material line
     count.
   - **Material lines** (collapsible): each row shows the **full label** (from
     AL Slug Library), item code, **dimensions W×H (mm)**, **quantity**, **unit
     price**, **line total**, **cost bucket** (name from AL Cost Bucket).
   - **Cost buckets** (collapsible): each bucket with its Vietnamese name
     (Vật liệu nhôm, Vật liệu kính, Vật tư phụ…).
   - **Manufacturing costs** (collapsible): each Cost Template line (TONG_VL,
     NC_SX, NC_LD, TONG_NC, OH_VC, OH_QLY, GIA_THANH, PROFIT, GIA_BAN,
     DON_GIA_M2, VAT, GIA_VAT…) shows **label** (from the Cost Template Item
     in the version snapshot) + **formula** + **value**. Subtotal rows
     (`TONG_`/`GIA_`/`VAT`) are bold on amber.
7. The **🖥️ Preview price** dialog (BOMDialog) renders the **same detail
   tables** (reuses the shared renderer — no duplicated code) plus:
   - **Formula + value** per manufacturing-cost row.
   - **HTML trace** per row (formula → variables substituted with values →
     result) inside a "View trace" accordion — the server `get_result_display`
     builds the trace (substituting input variables, buckets and cost-template
     lines).
8. Results are saved to the item: `al_gia_vat` (VAT-inclusive price),
   `al_gia_ban` (pre-VAT), `al_bom_result` (full JSON: buckets/cost_template/
   lines).
9. **`glass_master` variable (Loại kính / glass type)** is an input variable of
   BOMs with glass (Link → AL Glass Master): picking a different glass in the
   dialog saves it to `al_bom_vars` (`glass_master`). Phase 2 note
   (2026-08-22): the engine currently does **not** apply this value (it reads
   each AL Bom Item's `default_glass_master`) — engine-side override reading is
   Phase 4.
10. **Parameter-driven pricing**: material prices load by **composite key** —
   Item Price has `custom_pd_mau_sac`/`custom_pd_xuat_xu`/`custom_pd_do_day`/
   `custom_pd_be_mat` (color, origin, thickness, surface) mapped via
   `AL Variable Dimension Mapping` → the engine picks the Item Price row
   matching the **most** selected dimensions (`_match_composite_price`). Current
   seed data has a single price row per item (not yet split by each dimension).

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
- **ConfigSnapshot is created only when the Quotation is SUBMITTED** (doc_events
  `on_submit`): each Quotation Item that has a BOM calculation result
  (`al_bom_result` set) gets one `ConfigSnapshot` (`inputs_json` from
  `al_bom_vars`, `result_json` from `al_bom_result`, `bom_version` from
  `al_bom_version`) linked into `al_config_snapshot`. Clicking
  **Price / Preview** only writes `al_gia_vat` / `al_gia_ban` / `al_bom_result`
  on the row — it does **not** create a snapshot on every calculation.
