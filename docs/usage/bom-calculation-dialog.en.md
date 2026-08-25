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
   - **Material lines** (collapsible): each row shows **11 columns** — **item
     code** | **label** (from AL Slug Library) | **Width (mm)** | **Height
     (mm)** | **Quantity** (`qty`, plus `unit_qty/unit` when different) |
     **Weight** | **Volume** | **Unit** | **Unit price** | **Line total** |
     **Cost bucket** (name from AL Cost Bucket).
     - **Weight** = `weight_per_unit` (kg/m) — only shown for materials with
       `has_weight` (ALUMINIUM / STEEL / STAINLESS); other types (Glass /
       VTP / PK) show **"—"**.
     - **Volume** = `total_qty` (engine B4 already computed the unit-correct
       value per `calc_pattern`); **Unit** = `output_unit` of `calc_pattern`
       (kg/m/m²/pc/m/m³…).
   - **Cost buckets** (collapsible): each bucket with its Vietnamese name
     (Vật liệu nhôm, Vật liệu kính, Vật tư phụ…).
   - **Manufacturing costs** (collapsible): each Cost Template line (TONG_VL,
     NC_SX, NC_LD, TONG_NC, OH_VC, OH_QLY, GIA_THANH, PROFIT, GIA_BAN,
     DON_GIA_M2, VAT, GIA_VAT…) shows **5 columns** — **Item** (label from the
     Cost Template Item in the version snapshot) | **Formula** | **Explanation**
     | **Value** | **Unit**.
     - **Explanation** = the step-by-step calculation trace, formatted as
       **"8% × TONG_VL(1,000,000) = 80,000"** (never the confusing decimal
       0.08). Subtotal rows (`TONG_`/`GIA_`/`VAT`) are bold on amber.
     - **2-level trace**: material lines (per-line "View trace" accordion) +
       manufacturing costs (Explanation column).
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
9. **Per-position glass (per-line, V6 P7 — 2026-08-25):** BOMs with multiple
   glass lines show **N "Glass per position" selectors** (one Link → AL Glass
   Master selector per representative code `default_glass_master` — KINH_1,
   KINH_2…, grouped from `glass_groups` returned by `get_variable_set_for_bom`).
   Each selector defaults to its group's representative code; picking a real
   glass **saves `glass_master_map: {rep: actual}`** into `al_bom_vars`
   (e.g. `{"KINH-1": "KINH-LOWE-24", "KINH-2": "KINH-DON-8"}`) → the engine
   applies it per-line (item_code + price + nẹp kính / keo resolve per glass).
   **Backward-compat:** BOMs without `glass_groups` keep the global
   `glass_master` variable as before; when no map is present the engine still
   applies the global `glass_master` to every glass line.
10. **Dimension pricing is optional (Q1b):** `aluminum_color` / `aluminum_origin`
   / `aluminum_thickness` / `aluminum_surface` are **not required**; Select
   fields (`aluminum_origin` / `aluminum_surface`) have an **empty option**
   `""`. Leaving a dimension empty → the engine **ignores that dimension** when
   matching the composite price (picks the Item Price row matching the most
   dimensions, fallback to the plain price). The BOM config selectors
   (brand / accessory / cost_template / profile system) are also not required.
11. **Parameter-driven pricing**: material prices load by **composite key** —
   Item Price has `custom_pd_mau_sac`/`custom_pd_xuat_xu`/`custom_pd_do_day`/
   `custom_pd_be_mat` (color, origin, thickness, surface) mapped via
   `AL Variable Dimension Mapping` → the engine picks the Item Price row
   matching the **most** selected dimensions (`_match_composite_price`). Current
   seed data has a single price row per item (not yet split by each dimension).
12. **System variables** (OFFSET_*, NC_*, OH_*, PROFIT_MARGIN, VAT_RATE…)
   render **fully + editable** in the "System variables (auto)" section; the
   **"↺ Restore system variable defaults"** button resets them to the
   `default_value` from AL Variable Library (leaving empty → the engine uses
   the value resolved from AL Profile System / AL Product Type). When the API
   starts returning extra variables from the `AL Profile System Variable` child
   table (DEV1), they appear automatically — nothing hardcoded.

## Form-level buttons: Calculate / Preview all (Phase 3)

Besides the per-row buttons, the Quotation form toolbar has an **AlumGlass**
group with two buttons:

- **Calculate** (C1): scans all product rows and **validates** each — rows
  missing a BOM / BOM Version / parameters (`al_bom_vars`) are **listed with
  the exact missing item** in a warning dialog (those rows are skipped). Rows
  with complete data are calculated sequentially (sync/async per the threshold
  as usual), updating `rate = al_gia_ban` (A8), `al_gia_ban`, `al_gia_vat`,
  `al_bom_result`. Shows a **"calculated X/Y rows"** summary (+ background /
  failed counts when present).
- **Preview price** (C2): opens a large dialog (max-width **90vw**) with:
  - **Summary table**: #, Item code, Item name, Qty, Unit price, Amount.
  - **Each product** as a **collapsible** calculation detail — **reusing the
    shared Phase 2 renderer** (Material lines / Cost buckets / Manufacturing
    costs). Uncalculated rows show **"Chưa tính giá" (not calculated)**.

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
