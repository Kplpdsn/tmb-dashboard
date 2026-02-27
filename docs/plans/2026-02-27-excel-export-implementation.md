# Excel Export Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace raw CSV/Excel data dumps with a single formatted Excel product summary export for accountants.

**Architecture:** Create `reports/excel_export.py` with a `generate_excel()` function that aggregates the filtered DataFrame by product, formats it with openpyxl, and returns a BytesIO buffer. Update `app.py` to use it and remove the CSV button.

**Tech Stack:** pandas, openpyxl (both already installed)

**Design doc:** `docs/plans/2026-02-27-excel-export-design.md`

---

### Task 1: Create `reports/excel_export.py`

**Files:**
- Create: `reports/excel_export.py`

**Step 1: Create the module**

Create `reports/excel_export.py` with the `generate_excel` function:

```python
"""Product sales summary Excel export using openpyxl."""

from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def generate_excel(filtered_df, min_date, max_date):
    """Build a formatted product sales summary Excel workbook.

    Returns a BytesIO buffer ready for st.download_button.
    """
    # --- Aggregate by product ---
    product_summary = (
        filtered_df.groupby(["Description", "Category"], as_index=False)
        .agg(total_revenue=("Revenue", "sum"), total_quantity=("Quantity", "sum"))
    )
    total_rev = product_summary["total_revenue"].sum()
    product_summary["avg_price"] = (
        product_summary["total_revenue"] / product_summary["total_quantity"].replace(0, float("nan"))
    )
    product_summary["pct_revenue"] = product_summary["total_revenue"] / total_rev if total_rev else 0

    # Sort by revenue descending
    product_summary = product_summary.sort_values("total_revenue", ascending=False).reset_index(drop=True)

    # Rename for export
    export_df = product_summary.rename(columns={
        "Description": "Product",
        "Category": "Category",
        "total_revenue": "Total Revenue",
        "total_quantity": "Total Quantity",
        "avg_price": "Avg Price",
        "pct_revenue": "% of Revenue",
    })

    # --- Write to Excel ---
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="Product Sales", index=False)
        ws = writer.sheets["Product Sales"]

        # -- Column widths --
        col_widths = {"A": 30, "B": 18, "C": 14, "D": 14, "E": 12, "F": 14}
        for letter, width in col_widths.items():
            ws.column_dimensions[letter].width = width

        # -- Header styling --
        header_fill = PatternFill(start_color="4B5563", end_color="4B5563", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        # -- Number formatting for data rows --
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=6):
            row[2].number_format = '$#,##0.00'    # Total Revenue
            row[3].number_format = '#,##0'         # Total Quantity
            row[4].number_format = '$#,##0.00'    # Avg Price
            row[5].number_format = '0.0%'          # % of Revenue

        # -- Totals row --
        totals_row = ws.max_row + 1
        bold_font = Font(bold=True)
        ws.cell(row=totals_row, column=1, value="TOTAL").font = bold_font
        ws.cell(row=totals_row, column=3, value=total_rev).font = bold_font
        ws.cell(row=totals_row, column=3).number_format = '$#,##0.00'
        total_qty = product_summary["total_quantity"].sum()
        ws.cell(row=totals_row, column=4, value=total_qty).font = bold_font
        ws.cell(row=totals_row, column=4).number_format = '#,##0'

        # -- Freeze header row + auto-filter --
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:F{ws.max_row - 1}"

    buf.seek(0)
    return buf
```

**Step 2: Verify the import works**

Run: `python -c "from reports.excel_export import generate_excel; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add reports/excel_export.py
git commit -m "feat: add formatted Excel product sales export"
```

---

### Task 2: Update `app.py` — remove CSV, wire up Excel export

**Files:**
- Modify: `app.py:186-255`

**Step 1: Add import at top of app.py**

Near the other report imports (around line 14-15), add:

```python
from reports.excel_export import generate_excel
```

**Step 2: Replace export columns section**

Replace lines 186-255 (the `export_cols` section) with:

```python
            export_cols = st.columns([1, 1])

            with export_cols[0]:
```

Keep the existing PDF generation code in `export_cols[0]` exactly as-is (lines 188-234).

Then replace lines 236-255 (the CSV and Excel columns) with:

```python
            with export_cols[1]:
                date_str = f"{min_date.strftime('%Y%m%d')}_{max_date.strftime('%Y%m%d')}"
                try:
                    excel_buf = generate_excel(filtered_df, min_date, max_date)
                    st.download_button(
                        "Download Excel", data=excel_buf,
                        file_name=f"TMB_Product_Sales_{date_str}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="excel_export", use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"Excel generation failed: {e}")
```

**Step 3: Run the app to verify**

Run: `streamlit run app.py`
Check: only 2 export buttons (PDF + Excel), no CSV button.

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: wire up product sales Excel export, remove CSV"
```

---

### Task 3: Manual verification

**Step 1: Load some data and download the Excel file**

1. Run `streamlit run app.py`
2. Load a date range with data
3. Click "Download Excel"
4. Open the downloaded `.xlsx` file

**Step 2: Verify the file contents**

Check:
- [ ] Sheet name is "Product Sales"
- [ ] Columns: Product, Category, Total Revenue, Total Quantity, Avg Price, % of Revenue
- [ ] Sorted by Total Revenue descending
- [ ] Revenue columns show dollar formatting
- [ ] % of Revenue shows percentage formatting
- [ ] Header row is styled (dark background, white text)
- [ ] Header row is frozen
- [ ] Auto-filter dropdowns are present
- [ ] TOTAL row at bottom with sums
- [ ] No extra internal columns (Week, Month, Year, etc.)

**Step 3: Final import test**

Run: `python -c "from reports.excel_export import generate_excel; print('OK')"`
Expected: `OK`
