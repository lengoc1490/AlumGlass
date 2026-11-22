---
title: "Aluminum & Glass Quotation Pricing"
contexts:
  - "Form/Quotation Item"
  - "Form/Quotation"
tags: [sales-crm]
doc_type: doctype
---

# Aluminum & Glass Quotation Pricing

> **Canonical end-to-end guide (Vietnamese):** `docs/usage/tinh-gia-bao-gia.vi.md`.
> This page only summarises entry points and error handling — it does not repeat
> the user guide.
>
> Architecture and rationale: `docs/design/quotation-pricing.md` ·
> `docs/design/preview-khong-ghi-db.md`.

## What this is

Each quotation line is linked to a **BOM** and a **frozen BOM Version**. Pricing
breaks the BOM into material lines, computes quantities and amounts, rolls them up
by cost bucket, then runs the cost template to produce the **selling price** and
the **VAT-inclusive price**.

**Pricing does not write to the quotation.** The numbers stay on screen until you
click **Save** on the quotation. Details: the canonical guide above.

## Entry points

- **Per line:** **📐 BOM Parameters** (or double-click the row) — enter parameters,
  review the result, click **Apply to line**.
- **Quick preview one line:** **🖥️ Preview price** on the row — a read-only result
  window with **Apply to line** / **Close**.
- **Whole quotation:** **AlumGlass → Calculate** (batch, includes unsaved rows) and
  **AlumGlass → Preview price** (review the whole quotation).

The result shows: selling price, VAT-inclusive price, material-line detail, totals
by cost bucket, and the manufacturing-cost table with a step-by-step explanation.
Every material line has a **"Why this number?"** button.

## Behaviour on calculation errors

- A failing material/rule line (e.g. missing variable) gets value `0` and the error
  is recorded — **other lines still compute normally**, the whole quotation does
  not die.
- **Division by zero** always halts with an error — check the inputs (zero
  dimensions, missing unit price…) before recalculating.
- The result window shows a readable error and a **Retry** button; technical detail
  is kept inside the collapsed *"Technical details"* section.
- Errors are also written to the Error Log.

## Large BOMs — background calculation

- Small/medium BOMs compute synchronously; results appear immediately.
- Large BOMs run as a background job. The result appears automatically **only while
  the window stays open**; if it does not appear, reopen the window and click
  **🖥️ Preview price** to calculate again.
- Closing the window mid-calculation loses the pending result; reopen and calculate
  again.

## Notes

- Prices follow the **frozen BOM Version**: changing BOM config afterwards does not
  alter locked quotation prices.
- Do not edit the price fields or the result table on the line — they are computed
  values.
- To print: see `docs/usage/bao-gia-print-format.en.md`; the save-before-print rule
  is in the canonical guide `docs/usage/tinh-gia-bao-gia.vi.md` §7.
