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

1. Open a **Quotation** → in the items table pick a product line → click
   **Calculate** (or open **BOM Parameters** then click **Preview price**).
2. Fill in product parameters (width/height, color, origin, thickness,
   surface…) — the form is generated dynamically from the BOM's Variable Set.
3. The dialog shows: **Cost Breakdown** (Cost Template lines: TONG_VL, NC_SX,
   NC_LD, TONG_NC, OH_VC, OH_QLY, GIA_THANH, PROFIT, GIA_BAN, DON_GIA_M2, VAT,
   GIA_VAT…), **Cost Buckets**, and the material line detail table (slug, item,
   W/H, qty, unit price, line total).
4. Results are saved to the item: `al_gia_vat` (VAT-inclusive price),
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
