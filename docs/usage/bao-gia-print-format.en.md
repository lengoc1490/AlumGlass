---
title: "AlumGlass Quotation Print (Print Format)"
contexts:
  - "print-format/Báo giá AlumGlass"
tags: [sales-crm]
doc_type: print_format
---

# AlumGlass Quotation Print

> Save-before-print rules live in the canonical guide (Vietnamese):
> `docs/usage/tinh-gia-bao-gia.vi.md` §7.

## What this is

The **"Báo giá AlumGlass"** Print Format prints/exports a quotation from
**Quotation** to PDF. It does **not** recalculate prices — it prints the numbers
currently on the quotation line.

## How to use

1. Open a **Quotation** whose lines have been priced.
2. **Save** the quotation if you have just recalculated prices.
3. Click **Menu → Print → Báo giá AlumGlass** (or the Print button on the form).
4. Check: each product line shows the BOM + version + **pre-VAT price** +
   **VAT-inclusive price**; the lower part shows the cost breakdown (from
   materials to the VAT-inclusive price), the totals by cost bucket, and the
   **grand total**.

When printing **from the quotation form** while unsaved calculated prices remain,
the system opens a **Save then print** / **Cancel** dialog so the printout matches
the numbers on screen.

## Source data

The template reads the numbers on the quotation line (no recalculation):

| Shown on the printout | Taken from |
|---|---|
| BOM + frozen version | the quotation line |
| Pre-VAT / VAT-inclusive price | the quotation line |
| Detailed cost breakdown (buckets, cost items) | the saved calculation result on the line |

## Notes

- Lines **not yet priced** print empty — calculate those lines before printing.
- Large BOMs calculate in the background: wait until the result reaches the line;
  while still calculating, the price is not available.
- **Limitation:** the save prompt only exists when printing **from the quotation
  form**. Printing from the list view, bulk print, or opening a print link
  directly has **no** such check yet — save first.
- The template avoids CSS zoom — works on both **wkhtmltopdf** and browser
  preview. If font/size looks off on wkhtmltopdf, use the browser preview
  (memory `eup-dntt-bulk-print-wkhtmltopdf`).
