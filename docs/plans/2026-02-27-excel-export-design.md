# Excel Export Design

**Date:** 2026-02-27
**Branch:** feature/morning-brief-redesign
**Status:** Approved

## Goal

Replace the raw CSV and Excel data dumps with a single, well-formatted Excel export that provides a product sales summary useful for an accountant or bookkeeper.

## What Changes

1. **Remove** the CSV download button from `app.py` (lines 236-243)
2. **Create** `reports/excel_export.py` with `generate_excel(filtered_df, min_date, max_date) -> BytesIO`
3. **Update** `app.py` to import and call `generate_excel()` instead of inline `to_excel()`

## Excel File Spec

### Single Sheet: "Product Sales"

Data is grouped by product (Description), one row per product.

| Column        | Derivation                       | Format      |
|---------------|----------------------------------|-------------|
| Product       | `Description`                    | Text        |
| Category      | `Category`                       | Text        |
| Total Revenue | `sum(Revenue)` per product       | `$#,##0.00` |
| Total Quantity| `sum(Quantity)` per product      | `#,##0`     |
| Avg Price     | `Revenue / Quantity`             | `$#,##0.00` |
| % of Revenue  | `product_rev / total_rev * 100`  | `0.0%`      |

### Sorting

Total Revenue descending (top sellers first).

### Formatting

- Header row: bold, `#4B5563` background, white text (matches PDF report style)
- Frozen top row
- Auto-filter enabled on all columns
- Column widths: Product=30, Category=18, Total Revenue=14, Total Quantity=14, Avg Price=12, % of Revenue=14
- Totals row at the bottom: bold, sums for Revenue and Quantity columns

### File Naming

`TMB_Product_Sales_{start}_{end}.xlsx` where dates are `YYYYMMDD` format.

## What Was Removed

- CSV download button — scrapped entirely per user decision
- No summary sheets, charts, or conditional formatting — keep it clean for accountants

## Technical Notes

- Uses `openpyxl` (already in requirements.txt) via `pandas.ExcelWriter`
- No new dependencies needed
- Export logic lives in `reports/excel_export.py`, not in `app.py`
- `app.py` layout changes from 3 export columns to 2 (PDF + Excel)
