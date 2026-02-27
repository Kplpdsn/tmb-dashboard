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
