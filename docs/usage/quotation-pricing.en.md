---
title: "Aluminum & Glass Quotation Pricing"
contexts:
  - "Form/Quotation Item"
  - "Form/Quotation"
tags: [sales-crm]
doc_type: doctype
---

# Aluminum & Glass Quotation Pricing

## What this is

When drafting a quotation on **Quotation**, each product line (Quotation Item) is
linked to a **BOM** (`al_bom`) and a frozen version (`al_bom_version`). The
**Calculate** / **Price Preview** button runs the 7-phase `BomOrchestrator`
(B0–B7) to compute each material line amount → roll up cost buckets → run the
Cost Template → produce the **VAT-inclusive price** (`al_gia_vat`).

The core uses the **Formula Builder (FB-max)** platform: system variables, price
list values and costs are resolved from a **single source** — Formula Variable
Binding (via `get_live_context` + `BatchBindingResolver`) — replacing the former
hand-written resolvers. See `docs/design/quotation-pricing.md` for the
architecture.

## How to use

1. Open a **Quotation** → use the per-row actions on a product line (the small
   **📐** row button, or double-click) to open **BOM Parameters**, then click
   **Preview tính giá** (or expand the row and use the in-row buttons).
2. Fill in the product parameters (width/height, color, origin, thickness,
   surface…) — the form is generated dynamically from the BOM's Variable Set.
3. The dialog shows: **Cost Breakdown** (TONG_VL, NC_SX, NC_LD, TONG_NC, OH_VC,
   OH_QLY, GIA_THANH, PROFIT, GIA_BAN, DON_GIA_M2, VAT, GIA_VAT…), **Cost
   Buckets**, and a material-line detail table.
4. The result is saved on the line: `al_gia_vat` (VAT-inclusive price),
   `al_gia_ban` (pre-VAT), `al_bom_result` (full JSON: buckets/cost_template/
   lines + error list when applicable).

## Behaviour on calculation errors

- A failing material/rule line (e.g. missing variable) gets value `0` and the
  error is recorded in `al_bom_result.errors` — **other lines still compute
  normally**, the whole quotation does not die.
- **Division by zero** always halts with an error — check the inputs (zero
  dimensions, missing unit price…) before recalculating.
- If the dialog shows a detailed error, check the Error Log / `al_calc_error`.

## Large BOMs — background calculation (async)

- BOMs with ≤ **ASYNC_BOM_THRESHOLD** lines (default **150**, configured in
  Formula Global Variable) run **synchronously** — results appear immediately.
- Larger BOMs are sent to a **background job** (queue long): the dialog shows a
  spinner, and the result **auto-appears** via realtime when done.
- **Closing/reopening the dialog:** reads the saved state on the item
  (`al_calc_status`). Still running → shows "wait"; done → shows the saved
  result; error → shows the message.

## Notes

- Prices follow the **frozen version** (`al_bom_version`): BOM Set, Cost Template
  and **Pricing Dimension** snapshots are captured at publish time — changing
  config afterwards does not alter locked quotation prices.
- Do not edit `al_gia_vat`/`al_bom_result` directly — they are calculated
  results (read-only).
- To print: use the **"Báo giá AlumGlass"** Print Format (reads locked prices,
  no recalculation). See `docs/usage/bao-gia-print-format.en.md`.
