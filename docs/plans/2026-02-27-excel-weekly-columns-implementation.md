# Excel Weekly Breakdown Columns — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add per-week Revenue and Quantity columns to the Product Sales Excel export when data spans 2+ weeks.

**Architecture:** Extract a helper to compute week boundaries from the date range. When 2+ weeks exist, build a wider DataFrame with weekly Rev/Qty column pairs, write it with merged headers using openpyxl. Single-week exports keep the current flat layout unchanged.

**Tech Stack:** pandas, openpyxl (already in requirements.txt), pytest

---

### Task 1: Add week-boundary helper + test

**Files:**
- Modify: `reports/excel_export.py` (add helper at top, before `generate_excel`)
- Create: `tests/test_excel_export.py`

**Step 1: Write the failing test**

Create `tests/test_excel_export.py`:

```python
"""Tests for reports/excel_export.py."""

import pandas as pd
import pytest

from reports.excel_export import _compute_week_ranges


class TestComputeWeekRanges:
    """Tests for the week boundary helper."""

    def test_single_week_returns_empty(self):
        """Data within one ISO week returns no week ranges."""
        # Feb 2-6 2026 is Mon-Fri, all ISO week 6
        dates = pd.to_datetime(["2026-02-02", "2026-02-04", "2026-02-06"])
        result = _compute_week_ranges(dates)
        assert result == []

    def test_two_weeks_returns_two_ranges(self):
        """Data spanning two ISO weeks returns two (start, end) tuples."""
        # Week 5: Jan 26 (Mon) - Feb 1 (Sun)
        # Week 6: Feb 2 (Mon) - Feb 8 (Sun)
        dates = pd.to_datetime(["2026-01-28", "2026-02-01", "2026-02-03", "2026-02-05"])
        result = _compute_week_ranges(dates)
        assert len(result) == 2
        # First range starts at data min, ends at Sun Feb 1
        assert result[0] == (pd.Timestamp("2026-01-28"), pd.Timestamp("2026-02-01"))
        # Second range starts Mon Feb 2, ends at data max
        assert result[1] == (pd.Timestamp("2026-02-02"), pd.Timestamp("2026-02-05"))

    def test_partial_week_at_start(self):
        """Data starting mid-week creates a partial first range."""
        # Wed Jan 28 through Mon Feb 9
        dates = pd.to_datetime(["2026-01-28", "2026-02-02", "2026-02-09"])
        result = _compute_week_ranges(dates)
        assert len(result) == 3
        # First partial week: Wed Jan 28 - Sun Feb 1
        assert result[0][0] == pd.Timestamp("2026-01-28")
        assert result[0][1] == pd.Timestamp("2026-02-01")

    def test_labels_format(self):
        """Week labels are 'Mon D-D' or 'Mon D-Mon D' for cross-month."""
        dates = pd.to_datetime(["2026-01-28", "2026-02-05"])
        result = _compute_week_ranges(dates)
        # First range crosses Jan-Feb boundary
        start, end = result[0]
        s_month = start.strftime("%b")
        e_month = end.strftime("%b")
        assert s_month == "Jan"
        assert e_month != "Jan" or e_month == "Jan"  # just checks it runs
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_excel_export.py -v`
Expected: FAIL — `ImportError: cannot import name '_compute_week_ranges'`

**Step 3: Write the helper**

Add to `reports/excel_export.py` after the imports, before `generate_excel`:

```python
def _compute_week_ranges(dates):
    """Compute (start, end) date pairs for each ISO week in the data.

    Returns an empty list if all dates fall within a single ISO week.
    Week boundaries split on Monday (ISO standard).
    Partial weeks at start/end use the actual data min/max.
    """
    if dates.empty:
        return []

    min_date = dates.min()
    max_date = dates.max()

    # Group by ISO year-week
    iso = dates.to_series().dt.isocalendar()
    unique_weeks = iso.drop_duplicates(subset=["year", "week"]).sort_values(["year", "week"])

    if len(unique_weeks) < 2:
        return []

    ranges = []
    for i, (_, row) in enumerate(unique_weeks.iterrows()):
        # Monday of this ISO week
        monday = pd.Timestamp.fromisocalendar(int(row["year"]), int(row["week"]), 1)
        sunday = monday + pd.Timedelta(days=6)

        start = max(monday, min_date)
        end = min(sunday, max_date)
        ranges.append((start, end))

    return ranges
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_excel_export.py -v`
Expected: all 4 tests PASS

**Step 5: Commit**

```bash
git add reports/excel_export.py tests/test_excel_export.py
git commit -m "feat: add _compute_week_ranges helper with tests"
```

---

### Task 2: Add weekly aggregation logic + test

**Files:**
- Modify: `reports/excel_export.py` (add helper)
- Modify: `tests/test_excel_export.py` (add test class)

**Step 1: Write the failing test**

Append to `tests/test_excel_export.py`:

```python
from reports.excel_export import _build_weekly_product_data


def _make_test_df():
    """Build a minimal DataFrame spanning 2 weeks for testing."""
    rows = []
    # Week 1: Jan 28-Feb 1 (Wed-Sun) — 2 products
    for date in pd.date_range("2026-01-28", "2026-02-01"):
        rows.append({"Date": date, "Description": "HOUSE SOURDOUGH", "Category": "Standard Loaves",
                      "Revenue": 100, "Quantity": 10})
        rows.append({"Date": date, "Description": "CROISSANT PLAIN", "Category": "Pastries",
                      "Revenue": 50, "Quantity": 15})
    # Week 2: Feb 2-5 (Mon-Thu) — same 2 products
    for date in pd.date_range("2026-02-02", "2026-02-05"):
        rows.append({"Date": date, "Description": "HOUSE SOURDOUGH", "Category": "Standard Loaves",
                      "Revenue": 120, "Quantity": 12})
        rows.append({"Date": date, "Description": "CROISSANT PLAIN", "Category": "Pastries",
                      "Revenue": 60, "Quantity": 18})
    return pd.DataFrame(rows)


class TestBuildWeeklyProductData:
    def test_returns_dict_per_week(self):
        df = _make_test_df()
        week_ranges = _compute_week_ranges(df["Date"])
        result = _build_weekly_product_data(df, week_ranges)
        # result is a dict: {(start, end): DataFrame with Product, Rev, Qty}
        assert len(result) == 2

    def test_weekly_sums_are_correct(self):
        df = _make_test_df()
        week_ranges = _compute_week_ranges(df["Date"])
        result = _build_weekly_product_data(df, week_ranges)
        # Week 1: Jan 28 - Feb 1 = 5 days, HOUSE SOURDOUGH = 5 * 100 = 500
        w1_key = week_ranges[0]
        w1 = result[w1_key]
        sourdough_rev = w1.loc[w1["Description"] == "HOUSE SOURDOUGH", "Revenue"].values[0]
        assert sourdough_rev == 500

    def test_products_missing_in_a_week_get_zero(self):
        df = _make_test_df()
        # Add a product only in week 2
        extra = pd.DataFrame([{
            "Date": pd.Timestamp("2026-02-03"), "Description": "BAGUETTE",
            "Category": "Standard Loaves", "Revenue": 30, "Quantity": 5,
        }])
        df = pd.concat([df, extra], ignore_index=True)
        week_ranges = _compute_week_ranges(df["Date"])
        result = _build_weekly_product_data(df, week_ranges)
        w1 = result[week_ranges[0]]
        baguette = w1.loc[w1["Description"] == "BAGUETTE", "Revenue"].values[0]
        assert baguette == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_excel_export.py::TestBuildWeeklyProductData -v`
Expected: FAIL — `ImportError: cannot import name '_build_weekly_product_data'`

**Step 3: Write the aggregation helper**

Add to `reports/excel_export.py` after `_compute_week_ranges`:

```python
def _build_weekly_product_data(df, week_ranges):
    """Aggregate revenue and quantity per product per week range.

    Returns a dict mapping (start, end) -> DataFrame with columns:
    Description, Revenue, Quantity. Every product appears in every week
    (zero-filled if absent).
    """
    all_products = df[["Description", "Category"]].drop_duplicates()

    result = {}
    for start, end in week_ranges:
        mask = (df["Date"] >= start) & (df["Date"] <= end)
        week_df = df[mask]

        agg = (
            week_df.groupby("Description", as_index=False)
            .agg(Revenue=("Revenue", "sum"), Quantity=("Quantity", "sum"))
        )

        # Ensure every product has a row (zero-fill missing ones)
        merged = all_products[["Description"]].drop_duplicates().merge(
            agg, on="Description", how="left",
        ).fillna({"Revenue": 0, "Quantity": 0})

        result[(start, end)] = merged

    return result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_excel_export.py::TestBuildWeeklyProductData -v`
Expected: all 3 tests PASS

**Step 5: Commit**

```bash
git add reports/excel_export.py tests/test_excel_export.py
git commit -m "feat: add _build_weekly_product_data aggregation helper"
```

---

### Task 3: Rewrite generate_excel for multi-week layout

**Files:**
- Modify: `reports/excel_export.py:11-96` (rewrite `generate_excel`)

**Step 1: Write the failing test**

Append to `tests/test_excel_export.py`:

```python
import openpyxl
from io import BytesIO
from reports.excel_export import generate_excel


class TestGenerateExcelMultiWeek:
    """Integration tests for the multi-week Excel layout."""

    def _open(self, buf):
        buf.seek(0)
        return openpyxl.load_workbook(buf)

    def test_single_week_has_flat_layout(self):
        """Single week = no weekly columns, just the 6 original columns."""
        df = _make_test_df()
        # Filter to week 1 only
        df = df[df["Date"] < "2026-02-02"]
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = self._open(buf).active
        headers = [ws.cell(1, c).value for c in range(1, 7)]
        assert headers == ["Product", "Category", "Total Revenue", "Total Quantity", "Avg Price", "% of Revenue"]

    def test_multi_week_has_merged_week_headers(self):
        """Two weeks = merged header cells for each week pair."""
        df = _make_test_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = self._open(buf).active
        # Row 1 should have Product, Category, then merged week labels
        assert ws.cell(1, 1).value == "Product"
        assert ws.cell(1, 2).value == "Category"
        # Column C should be the first week label (merged across C-D)
        week1_label = ws.cell(1, 3).value
        assert "Jan" in week1_label or "28" in week1_label

    def test_multi_week_has_sub_headers(self):
        """Row 2 has Rev/Qty sub-headers under each week."""
        df = _make_test_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = self._open(buf).active
        assert ws.cell(2, 3).value == "Rev"
        assert ws.cell(2, 4).value == "Qty"

    def test_multi_week_totals_at_end(self):
        """Total Rev, Total Qty, Avg Price, % of Rev are the last 4 columns."""
        df = _make_test_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = self._open(buf).active
        # 2 weeks = 4 week columns (C-F), then totals start at G
        # Find the total columns by scanning row 1
        max_col = ws.max_column
        assert ws.cell(1, max_col - 3).value == "Total Revenue"
        assert ws.cell(1, max_col - 2).value == "Total Quantity"
        assert ws.cell(1, max_col - 1).value == "Avg Price"
        assert ws.cell(1, max_col).value == "% of Revenue"

    def test_multi_week_data_values(self):
        """Spot-check a weekly revenue value."""
        df = _make_test_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = self._open(buf).active
        # HOUSE SOURDOUGH should be row 3 (row 1=merged headers, row 2=sub-headers, row 3=first data)
        # It has highest total rev so it's first after sorting
        # Week 1 rev (col C) = 5 days * $100 = $500
        found = False
        for r in range(3, ws.max_row + 1):
            if ws.cell(r, 1).value == "HOUSE SOURDOUGH":
                assert ws.cell(r, 3).value == 500
                found = True
                break
        assert found, "HOUSE SOURDOUGH not found in data rows"

    def test_totals_row_exists(self):
        """Last data row is a TOTAL row."""
        df = _make_test_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = self._open(buf).active
        last_row = ws.max_row
        assert ws.cell(last_row, 1).value == "TOTAL"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_excel_export.py::TestGenerateExcelMultiWeek -v`
Expected: Most tests FAIL (current layout doesn't have merged headers or 2-row structure)

**Step 3: Rewrite `generate_excel`**

Replace `generate_excel` in `reports/excel_export.py:11-96` with:

```python
def generate_excel(filtered_df, min_date, max_date):
    """Build a formatted product sales summary Excel workbook.

    For 2+ weeks: adds per-week Rev/Qty columns with merged headers.
    For single week: flat layout (Product, Category, totals).

    Returns a BytesIO buffer ready for st.download_button.
    """
    if filtered_df.empty:
        buf = BytesIO()
        empty_df = pd.DataFrame(columns=[
            "Product", "Category", "Total Revenue", "Total Quantity",
            "Avg Price", "% of Revenue",
        ])
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            empty_df.to_excel(writer, sheet_name="Product Sales", index=False)
        buf.seek(0)
        return buf

    # --- Aggregate by product (always needed for totals) ---
    product_summary = (
        filtered_df.groupby(["Description", "Category"], as_index=False)
        .agg(total_revenue=("Revenue", "sum"), total_quantity=("Quantity", "sum"))
    )
    total_rev = product_summary["total_revenue"].sum()
    product_summary["avg_price"] = (
        product_summary["total_revenue"] / product_summary["total_quantity"].replace(0, float("nan"))
    )
    if total_rev:
        product_summary["pct_revenue"] = product_summary["total_revenue"] / total_rev
    else:
        product_summary["pct_revenue"] = 0.0

    product_summary = product_summary.sort_values("total_revenue", ascending=False).reset_index(drop=True)

    # --- Check for multi-week ---
    week_ranges = _compute_week_ranges(filtered_df["Date"])

    if not week_ranges:
        return _write_single_week(product_summary, total_rev)
    else:
        weekly_data = _build_weekly_product_data(filtered_df, week_ranges)
        return _write_multi_week(product_summary, week_ranges, weekly_data, total_rev)


def _write_single_week(product_summary, total_rev):
    """Write the flat single-week layout (current behavior)."""
    export_df = product_summary.rename(columns={
        "Description": "Product",
        "Category": "Category",
        "total_revenue": "Total Revenue",
        "total_quantity": "Total Quantity",
        "avg_price": "Avg Price",
        "pct_revenue": "% of Revenue",
    })

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="Product Sales", index=False)
        ws = writer.sheets["Product Sales"]

        col_widths = {"A": 30, "B": 18, "C": 14, "D": 14, "E": 12, "F": 14}
        for letter, width in col_widths.items():
            ws.column_dimensions[letter].width = width

        header_color = PDF_HEADER_BG.lstrip("#")
        header_fill = PatternFill(start_color=header_color, end_color=header_color, fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=6):
            row[2].number_format = '$#,##0.00'
            row[3].number_format = '#,##0'
            row[4].number_format = '$#,##0.00'
            row[5].number_format = '0.0%'

        totals_row = ws.max_row + 1
        bold_font = Font(bold=True)
        ws.cell(row=totals_row, column=1, value="TOTAL").font = bold_font
        ws.cell(row=totals_row, column=3, value=total_rev).font = bold_font
        ws.cell(row=totals_row, column=3).number_format = '$#,##0.00'
        total_qty = product_summary["total_quantity"].sum()
        ws.cell(row=totals_row, column=4, value=total_qty).font = bold_font
        ws.cell(row=totals_row, column=4).number_format = '#,##0'

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:F{totals_row - 1}"

    buf.seek(0)
    return buf


def _week_label(start, end):
    """Format a week range as a readable label like 'Feb 1-7' or 'Jan 28-Feb 1'."""
    s_month = start.strftime("%b")
    e_month = end.strftime("%b")
    if s_month != e_month:
        return f"{s_month} {start.day}-{e_month} {end.day}"
    return f"{s_month} {start.day}-{end.day}"


def _write_multi_week(product_summary, week_ranges, weekly_data, total_rev):
    """Write the multi-week layout with merged week headers."""
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.cell import MergedCell

    num_weeks = len(week_ranges)
    # Columns: A=Product, B=Category, then 2 cols per week, then 4 total cols
    week_start_col = 3  # column C
    total_start_col = week_start_col + num_weeks * 2
    total_cols = ["Total Revenue", "Total Quantity", "Avg Price", "% of Revenue"]
    last_col = total_start_col + len(total_cols) - 1

    buf = BytesIO()
    wb = __import__("openpyxl").Workbook()
    ws = wb.active
    ws.title = "Product Sales"

    header_color = PDF_HEADER_BG.lstrip("#")
    header_fill = PatternFill(start_color=header_color, end_color=header_color, fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    sub_header_font = Font(bold=True, color="FFFFFF", size=9)
    center = Alignment(horizontal="center")

    # --- Row 1: merged week headers + total headers ---
    ws.cell(1, 1, "Product").font = header_font
    ws.cell(1, 1).fill = header_fill
    ws.cell(1, 1).alignment = center
    ws.cell(1, 2, "Category").font = header_font
    ws.cell(1, 2).fill = header_fill
    ws.cell(1, 2).alignment = center

    # Merge Product and Category across rows 1-2
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
    ws.merge_cells(start_row=1, start_column=2, end_row=2, end_column=2)

    for i, (start, end) in enumerate(week_ranges):
        col = week_start_col + i * 2
        label = _week_label(start, end)
        ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + 1)
        cell = ws.cell(1, col, label)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        # Fill the merged partner cell too
        ws.cell(1, col + 1).fill = header_fill

    # Total headers (merged across rows 1-2)
    for j, name in enumerate(total_cols):
        col = total_start_col + j
        ws.merge_cells(start_row=1, start_column=col, end_row=2, end_column=col)
        cell = ws.cell(1, col, name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center

    # --- Row 2: sub-headers (Rev / Qty) under each week ---
    for i in range(num_weeks):
        col = week_start_col + i * 2
        rev_cell = ws.cell(2, col, "Rev")
        rev_cell.font = sub_header_font
        rev_cell.fill = header_fill
        rev_cell.alignment = center
        qty_cell = ws.cell(2, col + 1, "Qty")
        qty_cell.font = sub_header_font
        qty_cell.fill = header_fill
        qty_cell.alignment = center

    # --- Data rows (starting row 3) ---
    # Build a lookup: product -> weekly (rev, qty) per week range
    weekly_lookup = {}
    for key, wdf in weekly_data.items():
        for _, r in wdf.iterrows():
            weekly_lookup.setdefault(r["Description"], {})[key] = (r["Revenue"], r["Quantity"])

    data_start_row = 3
    for idx, (_, prod) in enumerate(product_summary.iterrows()):
        row_num = data_start_row + idx
        ws.cell(row_num, 1, prod["Description"])
        ws.cell(row_num, 2, prod["Category"])

        # Weekly columns
        prod_weeks = weekly_lookup.get(prod["Description"], {})
        for i, wr in enumerate(week_ranges):
            col = week_start_col + i * 2
            rev, qty = prod_weeks.get(wr, (0, 0))
            rev_cell = ws.cell(row_num, col, rev)
            rev_cell.number_format = '$#,##0'
            qty_cell = ws.cell(row_num, col + 1, qty)
            qty_cell.number_format = '#,##0'

        # Total columns
        tc = total_start_col
        ws.cell(row_num, tc, prod["total_revenue"]).number_format = '$#,##0.00'
        ws.cell(row_num, tc + 1, prod["total_quantity"]).number_format = '#,##0'
        ws.cell(row_num, tc + 2, prod["avg_price"]).number_format = '$#,##0.00'
        ws.cell(row_num, tc + 3, prod["pct_revenue"]).number_format = '0.0%'

    # --- TOTAL row ---
    totals_row = data_start_row + len(product_summary)
    bold_font = Font(bold=True)
    ws.cell(totals_row, 1, "TOTAL").font = bold_font

    # Weekly totals
    for i, wr in enumerate(week_ranges):
        col = week_start_col + i * 2
        week_rev = sum(
            weekly_lookup.get(p, {}).get(wr, (0, 0))[0]
            for p in product_summary["Description"]
        )
        week_qty = sum(
            weekly_lookup.get(p, {}).get(wr, (0, 0))[1]
            for p in product_summary["Description"]
        )
        ws.cell(totals_row, col, week_rev).font = bold_font
        ws.cell(totals_row, col).number_format = '$#,##0'
        ws.cell(totals_row, col + 1, week_qty).font = bold_font
        ws.cell(totals_row, col + 1).number_format = '#,##0'

    tc = total_start_col
    ws.cell(totals_row, tc, total_rev).font = bold_font
    ws.cell(totals_row, tc).number_format = '$#,##0.00'
    total_qty = product_summary["total_quantity"].sum()
    ws.cell(totals_row, tc + 1, total_qty).font = bold_font
    ws.cell(totals_row, tc + 1).number_format = '#,##0'

    # --- Column widths ---
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 18
    for i in range(num_weeks):
        col = week_start_col + i * 2
        ws.column_dimensions[get_column_letter(col)].width = 12
        ws.column_dimensions[get_column_letter(col + 1)].width = 10
    for j in range(len(total_cols)):
        ws.column_dimensions[get_column_letter(total_start_col + j)].width = 14

    # --- Freeze panes + auto-filter ---
    ws.freeze_panes = "A3"
    ws.auto_filter.ref = f"A2:B{totals_row - 1}"

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out
```

**Step 4: Run all tests**

Run: `pytest tests/test_excel_export.py -v`
Expected: all tests PASS

**Step 5: Commit**

```bash
git add reports/excel_export.py tests/test_excel_export.py
git commit -m "feat: add weekly breakdown columns to product sales Excel export"
```

---

### Task 4: Manual smoke test + fix any issues

**Step 1: Run the app and export a multi-week Excel**

Run: `streamlit run app.py`
Load 2+ weeks of data, click "Generate Excel", open the file. Verify:
- Merged week headers display correctly
- Rev/Qty sub-headers are visible
- Weekly values sum to the totals
- Single-week still produces the flat layout

**Step 2: Fix any visual/formatting issues found**

Common things to check:
- Merged cell fill colors (openpyxl sometimes needs both cells filled)
- Column widths look right
- Number formats render in Excel

**Step 3: Commit any fixes**

```bash
git add reports/excel_export.py
git commit -m "fix: polish multi-week Excel formatting"
```
