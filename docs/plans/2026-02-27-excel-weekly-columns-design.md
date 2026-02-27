# Excel Export: Weekly Breakdown Columns

## Summary

Add per-week Revenue and Quantity columns to the Product Sales Excel export when the loaded date range spans 2+ weeks. Single-week exports keep the current flat layout.

## Layout

### Single week (one week boundary)

```
Product | Category | Total Rev | Total Qty | Avg Price | % of Rev
```

No change from current behavior.

### Multi-week (2+ weeks)

```
                    +-- merged --+  +-- merged --+
Product | Category | Feb 1-7    |  | Feb 8-14   | ... | Total Rev | Total Qty | Avg Price | % of Rev
                    | Rev | Qty |  | Rev | Qty  |     |
```

- Week ranges determined by calendar weeks within the loaded date range.
- Partial weeks at start/end are included (e.g. data starting Wednesday = first week is Wed-Sun).
- Merged header row spans each week's Rev + Qty pair.
- Total columns at the end sum across all weeks (unchanged).

## Week Boundaries

Split on **Monday** (ISO standard, matches DAY_NAMES_ORDERED starting Monday). Example: Feb 1, 2026 (Sunday) is the tail of one week; Feb 2 (Monday) starts a new one.

## Formatting

- Merged week headers: same dark fill as current column headers (`PDF_HEADER_BG`).
- Sub-headers (Rev / Qty): same style, row below the merged header.
- Week Rev cells: `$#,##0` (no decimals at weekly granularity).
- Week Qty cells: `#,##0`.
- Total columns at end: keep current formatting (with decimals on Rev).
- Frozen panes: `A3` (freeze Product/Category + both header rows).
- Auto-filter on row 2 (Product and Category columns only).
- TOTAL row at bottom sums weekly columns too.

## Scope

- Only affects `generate_excel()` in `reports/excel_export.py`.
- Avg Day and Baskets Excel exports are untouched.
- Product sort order (total revenue descending) unchanged.
- Empty data guard unchanged.

## Trigger condition

Count distinct ISO weeks in the data. If >= 2, use the multi-week layout. Otherwise, use the current single-week layout.
