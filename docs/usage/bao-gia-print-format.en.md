---
title: "AlumGlass Quotation Print (Print Format)"
contexts:
  - "print-format/Báo giá AlumGlass"
tags: [sales-crm]
doc_type: print_format
---

# AlumGlass Quotation Print

## What this is

The **"Báo giá AlumGlass"** Print Format is used to print/export a quotation
from **Quotation** to PDF. It prints the **locked prices** saved when you
clicked "Calculate" — it does **not** recalculate prices at print time.

## How to use

1. Open a **Quotation** whose lines have been priced (have `al_gia_vat`).
2. Click **Menu → Print → Báo giá AlumGlass** (or the Print button on the
   form).
3. Check: each product line shows the BOM + version + **pre-VAT price** +
   **VAT-inclusive price**; the lower part shows the **Cost Template** detail
   (TONG_VL → GIA_VAT), **Cost Buckets**, and the **grand total** (Σ
   `al_gia_vat`).

## Source data

The template reads directly from the Quotation Item (no recalculation):

| Field | Meaning |
|---|---|
| `item.al_bom` / `item.al_bom_version` | Locked BOM + version |
| `item.al_gia_ban` / `item.al_gia_vat` | Pre-VAT / VAT-inclusive price |
| `item.al_bom_result` (JSON) | buckets + cost_template + lines (parsed via `frappe.parse_json`) |

## Notes

- Lines **not yet priced** (no `al_gia_vat`) print empty — click "Calculate"
  for each line before printing.
- Large BOMs (async): wait until the background calculation is done
  (`al_calc_status = Success`) before printing — while `Queued`/`Running` the
  price is not available yet.
- The template avoids CSS zoom — works on both **wkhtmltopdf** and browser
  preview. If font/size looks off on wkhtmltopdf, use the browser preview
  (memory `eup-dntt-bulk-print-wkhtmltopdf`).
