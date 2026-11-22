---
title: "BOM Price Calculation on Quotation (Preview / Calculate dialog)"
contexts:
  - "Form/Quotation"
tags: [sales-crm]
doc_type: doctype
---

# BOM Price Calculation on Quotation

> This page describes the **screen layout** of the pricing windows.
> The canonical end-to-end guide (Vietnamese) is
> `docs/usage/tinh-gia-bao-gia.vi.md` — how to price, what "not saved yet" means,
> saving and printing are **not repeated here**.
>
> Architecture and rationale: `docs/design/preview-khong-ghi-db.md`.

## Opening the windows

Each quotation line has two small buttons at the right corner of the item-code
cell:

- **📐** opens **BOM Parameters** (double-clicking the row also opens it).
- **🖥️** runs **Preview price** directly; if no BOM is selected yet, the system
  asks you to open 📐 first.

When a row is expanded, both buttons — **📐 BOM Parameters** / **🖥️ Preview
price** — appear at the top of the expanded form. Buttons appear as soon as the
form opens with existing rows and are never duplicated when the grid re-renders.

## "Select BOM" section

Pick a **BOM** and a **BOM Version**. Below it, **Product info** shows read-only
cells in a 2-column layout: **BOM**, **Bom Set**, **Variable Set**, **Profile
system**, **Aluminum brand**, **Accessory set**. Each cell shows `name (code)`;
missing data shows **"—"**. Changing the BOM re-renders this section and the
parameter section in place (no new window, no flicker).

## Parameter section

- The parameter form is generated from the BOM's variable set, **3-column**
  layout.
- **Input variables**: width/height, panel count, color, origin, thickness,
  surface… Dimensions used for pricing are **optional** — leaving one empty makes
  the system ignore that dimension when picking a price.
- **System variables** show their full label and default value and are
  **editable**. The **↺ Restore system variable defaults** button resets them.
- Some variables show a source note, e.g. *"ĐÃ RESOLVE từ …"* or
  *"Default · Resolve … khi chạy BOM"*.
- To add a parameter not in the variable set, use the **Extra variables** table
  (add/remove rows). The **Variable name** column picks from the variable
  catalogue; the **Type** column fills in automatically.

Changing any parameter triggers an automatic recalculation after a moment; a
yellow note appears while waiting: *"Tham số vừa đổi — đang tự động tính lại
giá..."*.

## "Glass per position" section

Every glass position has its own glass selector — always present, even when the
BOM has no default glass code.

- A **status line** under the selector says what is in use, e.g. *"Đã chọn: …"*,
  *"Đang dùng mã cố định trên BOM: … · Đổi được nếu khách chọn kính khác."*,
  *"Đang áp dụng kính mới — tự tính lại giá sau giây lát"*, or *"Chưa có mã kính —
  chọn kính cho vị trí này"*.
- A **price line** follows: *"Giá: …"*; a provisional price has a **≈** prefix and
  *(giá chốt khi tính lại xong)*; a missing price says why.
- Changing the glass code updates the price line and recalculates the whole line.

## "Color" section

Grouped by material type (aluminium / glass / accessories / auxiliary). Positions
with a configurable colour get a colour selector; positions with a fixed colour do
not.

## Result tables

Both the 📐 window and the 🖥️ window use the **same layout**:

1. **Summary**: selling price (pre-VAT), VAT-inclusive price, material line count.
2. **Material lines** (collapsible) — 11 columns: **Item code · Item name ·
   Width (mm) · Height (mm) · Quantity · Weight · Volume · Unit · Unit price ·
   Line total · Cost bucket**.
   - **Weight** only appears for aluminium/steel/stainless; other types show
     **"—"**.
   - **Volume** and **Unit** follow the item's quantity calculation method
     (kg / m / m² / pc…).
3. **Totals by cost bucket** (collapsible), with Vietnamese bucket names.
4. **Manufacturing costs** (collapsible) — 5 columns: **Item · Formula ·
   Explanation · Value · Unit**. Subtotal rows are bold on amber. The
   **Explanation** column shows the step-by-step trace, e.g.
   *"8% × TONG_VL(1,000,000) = 80,000"*.

Each material line has a **"Why this number?"** button that explains the result
currently shown, including unsaved results.

The **🖥️ Preview price** window adds formula/explanation detail per cost row. At
the top it states the result is for viewing only and not yet written to the
quotation; the two buttons are **Apply to line** / **Close**. **Apply to line**
is dim until a result exists.

## Large BOMs — background calculation

- Small/medium BOMs calculate immediately.
- Large BOMs are queued: the window shows a waiting panel. The result appears
  automatically when done, **only while the window stays open**, with the
  notification *"Tính giá xong — chưa lưu vào báo giá."*
- If the window was closed before the result arrived, it does **not** reopen by
  itself — reopen it with **🖥️**.
- If it takes too long, close the window and click the calculate button again.

## Notes

- Prices follow the **frozen BOM Version**: later configuration changes do not
  alter a quotation already priced.
- Do not edit the price cells or the result table on the line — they are computed
  values.
- The reproducibility snapshot is created only when the quotation is **submitted**,
  not on every calculation.
- Saving and printing rules: see the canonical guide
  `docs/usage/tinh-gia-bao-gia.vi.md`.
