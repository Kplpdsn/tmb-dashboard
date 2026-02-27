"""Product sales summary Excel export using openpyxl."""

from io import BytesIO

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from config import PDF_HEADER_BG


# ---------------------------------------------------------------------------
# Week helpers
# ---------------------------------------------------------------------------

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

    s = dates if isinstance(dates, pd.Series) else dates.to_series()
    iso = s.dt.isocalendar()
    unique_weeks = iso.drop_duplicates(subset=["year", "week"]).sort_values(["year", "week"])

    if len(unique_weeks) < 2:
        return []

    ranges = []
    for _, row in unique_weeks.iterrows():
        monday = pd.Timestamp.fromisocalendar(int(row["year"]), int(row["week"]), 1)
        sunday = monday + pd.Timedelta(days=6)
        start = max(monday, min_date)
        end = min(sunday, max_date)
        ranges.append((start, end))

    return ranges


def _build_weekly_product_data(df, week_ranges):
    """Aggregate revenue and quantity per product per week range.

    Returns a dict mapping (start, end) -> DataFrame with columns:
    Description, Revenue, Quantity. Every product appears in every week
    (zero-filled if absent).
    """
    all_products = df[["Description"]].drop_duplicates()

    result = {}
    for start, end in week_ranges:
        mask = (df["Date"] >= start) & (df["Date"] <= end)
        week_df = df[mask]

        agg = (
            week_df.groupby("Description", as_index=False)
            .agg(Revenue=("Revenue", "sum"), Quantity=("Quantity", "sum"))
        )

        merged = all_products.merge(agg, on="Description", how="left").fillna({"Revenue": 0, "Quantity": 0})
        result[(start, end)] = merged

    return result


def _week_label(start, end):
    """Format a week range like 'Feb 1-7' or 'Jan 28-Feb 1'."""
    s_month = start.strftime("%b")
    e_month = end.strftime("%b")
    if s_month != e_month:
        return f"{s_month} {start.day}-{e_month} {end.day}"
    return f"{s_month} {start.day}-{end.day}"


# ---------------------------------------------------------------------------
# Shared styling helpers
# ---------------------------------------------------------------------------

def _header_styles():
    """Return (fill, font, alignment) for header cells."""
    color = PDF_HEADER_BG.lstrip("#")
    fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
    font = Font(bold=True, color="FFFFFF")
    align = Alignment(horizontal="center")
    return fill, font, align


# ---------------------------------------------------------------------------
# generate_excel — public entry point
# ---------------------------------------------------------------------------

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

    # --- Aggregate by product ---
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


# ---------------------------------------------------------------------------
# Single-week layout
# ---------------------------------------------------------------------------

def _write_single_week(product_summary, total_rev):
    """Write the flat single-week layout."""
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

        header_fill, header_font, center = _header_styles()
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=6):
            row[2].number_format = '$#,##0.00'
            row[3].number_format = '#,##0'
            row[4].number_format = '$#,##0.00'
            row[5].number_format = '0.0%'

        # TOTAL row using SUBTOTAL formulas (respects auto-filter)
        data_last_row = ws.max_row
        totals_row = data_last_row + 1
        bold_font = Font(bold=True)
        ws.cell(row=totals_row, column=1, value="TOTAL").font = bold_font

        ws.cell(row=totals_row, column=3, value=f"=SUBTOTAL(9,C2:C{data_last_row})").font = bold_font
        ws.cell(row=totals_row, column=3).number_format = '$#,##0.00'

        ws.cell(row=totals_row, column=4, value=f"=SUBTOTAL(9,D2:D{data_last_row})").font = bold_font
        ws.cell(row=totals_row, column=4).number_format = '#,##0'

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:F{data_last_row}"

    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Multi-week layout
# ---------------------------------------------------------------------------

def _write_multi_week(product_summary, week_ranges, weekly_data, total_rev):
    """Write the multi-week layout with merged week headers."""
    num_weeks = len(week_ranges)
    week_start_col = 3  # column C
    total_start_col = week_start_col + num_weeks * 2
    total_col_names = ["Total Revenue", "Total Quantity", "Avg Price", "% of Revenue"]

    header_fill, header_font, center = _header_styles()
    sub_header_font = Font(bold=True, color="FFFFFF", size=9)
    bold_font = Font(bold=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Product Sales"

    # --- Row 1: Product, Category (merged r1-r2), week labels (merged), total labels (merged r1-r2) ---
    for col_idx, label in enumerate(["Product", "Category"], start=1):
        cell = ws.cell(1, col_idx, label)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        ws.merge_cells(start_row=1, start_column=col_idx, end_row=2, end_column=col_idx)

    for i, (start, end) in enumerate(week_ranges):
        col = week_start_col + i * 2
        label = _week_label(start, end)
        ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + 1)
        cell = ws.cell(1, col, label)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        ws.cell(1, col + 1).fill = header_fill

    for j, name in enumerate(total_col_names):
        col = total_start_col + j
        ws.merge_cells(start_row=1, start_column=col, end_row=2, end_column=col)
        cell = ws.cell(1, col, name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center

    # --- Row 2: Rev / Qty sub-headers ---
    for i in range(num_weeks):
        col = week_start_col + i * 2
        for offset, label in enumerate(["Rev", "Qty"]):
            cell = ws.cell(2, col + offset, label)
            cell.font = sub_header_font
            cell.fill = header_fill
            cell.alignment = center

    # --- Build product -> weekly lookup ---
    weekly_lookup = {}
    for key, wdf in weekly_data.items():
        for _, r in wdf.iterrows():
            weekly_lookup.setdefault(r["Description"], {})[key] = (r["Revenue"], r["Quantity"])

    # --- Data rows (starting row 3) ---
    data_start_row = 3
    for idx, (_, prod) in enumerate(product_summary.iterrows()):
        row_num = data_start_row + idx
        ws.cell(row_num, 1, prod["Description"])
        ws.cell(row_num, 2, prod["Category"])

        prod_weeks = weekly_lookup.get(prod["Description"], {})
        for i, wr in enumerate(week_ranges):
            col = week_start_col + i * 2
            rev, qty = prod_weeks.get(wr, (0, 0))
            ws.cell(row_num, col, rev).number_format = '$#,##0'
            ws.cell(row_num, col + 1, qty).number_format = '#,##0'

        tc = total_start_col
        ws.cell(row_num, tc, prod["total_revenue"]).number_format = '$#,##0.00'
        ws.cell(row_num, tc + 1, prod["total_quantity"]).number_format = '#,##0'
        ws.cell(row_num, tc + 2, prod["avg_price"]).number_format = '$#,##0.00'
        ws.cell(row_num, tc + 3, prod["pct_revenue"]).number_format = '0.0%'

    # --- TOTAL row using SUBTOTAL formulas ---
    data_last_row = data_start_row + len(product_summary) - 1
    totals_row = data_last_row + 1
    ws.cell(totals_row, 1, "TOTAL").font = bold_font

    for i in range(num_weeks):
        col = week_start_col + i * 2
        rev_letter = get_column_letter(col)
        qty_letter = get_column_letter(col + 1)
        rev_range = f"{rev_letter}{data_start_row}:{rev_letter}{data_last_row}"
        qty_range = f"{qty_letter}{data_start_row}:{qty_letter}{data_last_row}"
        ws.cell(totals_row, col, f"=SUBTOTAL(9,{rev_range})").font = bold_font
        ws.cell(totals_row, col).number_format = '$#,##0'
        ws.cell(totals_row, col + 1, f"=SUBTOTAL(9,{qty_range})").font = bold_font
        ws.cell(totals_row, col + 1).number_format = '#,##0'

    tc = total_start_col
    rev_letter = get_column_letter(tc)
    qty_letter = get_column_letter(tc + 1)
    ws.cell(totals_row, tc, f"=SUBTOTAL(9,{rev_letter}{data_start_row}:{rev_letter}{data_last_row})").font = bold_font
    ws.cell(totals_row, tc).number_format = '$#,##0.00'
    ws.cell(totals_row, tc + 1, f"=SUBTOTAL(9,{qty_letter}{data_start_row}:{qty_letter}{data_last_row})").font = bold_font
    ws.cell(totals_row, tc + 1).number_format = '#,##0'

    # --- Column widths ---
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 18
    for i in range(num_weeks):
        col = week_start_col + i * 2
        ws.column_dimensions[get_column_letter(col)].width = 12
        ws.column_dimensions[get_column_letter(col + 1)].width = 10
    for j in range(len(total_col_names)):
        ws.column_dimensions[get_column_letter(total_start_col + j)].width = 14

    # --- Freeze panes + auto-filter ---
    ws.freeze_panes = "A3"
    ws.auto_filter.ref = f"A2:B{data_last_row}"

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out


# ---------------------------------------------------------------------------
# Avg Day Excel
# ---------------------------------------------------------------------------

def generate_avg_day_excel(filtered_df, selected_day_name, selected_months=None):
    """Build a formatted average-day product performance Excel workbook.

    Returns a BytesIO buffer ready for st.download_button.
    """
    df = filtered_df[filtered_df["DayName"] == selected_day_name].copy()

    if selected_months:
        df = df[df["Date"].dt.month.isin(selected_months)]

    if df.empty:
        buf = BytesIO()
        empty_df = pd.DataFrame(columns=[
            "Product", "Category", "Avg Daily Revenue", "Avg Daily Quantity",
            "Avg Price", "% of Revenue",
        ])
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            empty_df.to_excel(writer, sheet_name="Avg Product Performance", index=False)
        buf.seek(0)
        return buf

    _date = df["Date"].dt.date
    num_days = _date.nunique()
    daily_product = (
        df.groupby([_date, "Description", "Category"], as_index=False)
        .agg(revenue=("Revenue", "sum"), quantity=("Quantity", "sum"))
    )

    total_product = (
        daily_product.groupby(["Description", "Category"], as_index=False)
        .agg(total_revenue=("revenue", "sum"), total_quantity=("quantity", "sum"))
    )
    total_product["avg_revenue"] = total_product["total_revenue"] / num_days
    total_product["avg_quantity"] = total_product["total_quantity"] / num_days
    avg_product = total_product.drop(columns=["total_revenue", "total_quantity"])

    avg_product["avg_price"] = (
        avg_product["avg_revenue"] / avg_product["avg_quantity"].replace(0, float("nan"))
    )
    total_avg_rev = avg_product["avg_revenue"].sum()
    if total_avg_rev:
        avg_product["pct_revenue"] = avg_product["avg_revenue"] / total_avg_rev
    else:
        avg_product["pct_revenue"] = 0.0

    avg_product = avg_product.sort_values("avg_revenue", ascending=False).reset_index(drop=True)

    export_df = avg_product.rename(columns={
        "Description": "Product",
        "Category": "Category",
        "avg_revenue": "Avg Daily Revenue",
        "avg_quantity": "Avg Daily Quantity",
        "avg_price": "Avg Price",
        "pct_revenue": "% of Revenue",
    })

    num_instances = num_days
    first_date = df["Date"].min().strftime("%d/%m/%Y")
    last_date = df["Date"].max().strftime("%d/%m/%Y")
    context_line = (
        f"Average {selected_day_name} - {num_instances} "
        f"instance{'s' if num_instances != 1 else ''} "
        f"({first_date} to {last_date})"
    )

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        export_df.to_excel(
            writer, sheet_name="Avg Product Performance", index=False, startrow=1,
        )
        ws = writer.sheets["Avg Product Performance"]

        ws.cell(row=1, column=1, value=context_line).font = Font(bold=True, italic=True)

        col_widths = {"A": 30, "B": 18, "C": 16, "D": 16, "E": 12, "F": 14}
        for letter, width in col_widths.items():
            ws.column_dimensions[letter].width = width

        header_fill, header_font, center = _header_styles()
        for cell in ws[2]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center

        for row in ws.iter_rows(min_row=3, max_row=ws.max_row, min_col=1, max_col=6):
            row[2].number_format = '$#,##0.00'
            row[3].number_format = '#,##0.0'
            row[4].number_format = '$#,##0.00'
            row[5].number_format = '0.0%'

        # TOTAL row with SUBTOTAL formulas
        data_last_row = ws.max_row
        totals_row = data_last_row + 1
        bold_font = Font(bold=True)
        ws.cell(row=totals_row, column=1, value="TOTAL").font = bold_font

        ws.cell(row=totals_row, column=3, value=f"=SUBTOTAL(9,C3:C{data_last_row})").font = bold_font
        ws.cell(row=totals_row, column=3).number_format = '$#,##0.00'
        ws.cell(row=totals_row, column=4, value=f"=SUBTOTAL(9,D3:D{data_last_row})").font = bold_font
        ws.cell(row=totals_row, column=4).number_format = '#,##0.0'

        ws.freeze_panes = "A3"
        ws.auto_filter.ref = f"A2:F{data_last_row}"

    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Baskets Excel
# ---------------------------------------------------------------------------

def generate_baskets_excel(filtered_df):
    """Build a formatted basket-level detail Excel workbook.

    Returns a BytesIO buffer ready for st.download_button.
    """
    if filtered_df.empty:
        buf = BytesIO()
        empty_df = pd.DataFrame(columns=["Basket", "Date", "Items", "Total", "Products"])
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            empty_df.to_excel(writer, sheet_name="Baskets", index=False)
        buf.seek(0)
        return buf

    baskets = (
        filtered_df.groupby("Basket_ID", as_index=False)
        .agg(
            date=("Date", "first"),
            items=("Quantity", "sum"),
            total=("Revenue", "sum"),
            products=("Description", lambda x: ", ".join(sorted(x.unique()))),
        )
    )

    baskets = baskets.sort_values(["date", "total"], ascending=[True, False]).reset_index(drop=True)

    export_df = baskets.rename(columns={
        "Basket_ID": "Basket",
        "date": "Date",
        "items": "Items",
        "total": "Total",
        "products": "Products",
    })

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="Baskets", index=False)
        ws = writer.sheets["Baskets"]

        col_widths = {"A": 18, "B": 14, "C": 10, "D": 14, "E": 50}
        for letter, width in col_widths.items():
            ws.column_dimensions[letter].width = width

        header_fill, header_font, center = _header_styles()
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=5):
            row[1].number_format = 'DD/MM/YYYY'
            row[2].number_format = '#,##0'
            row[3].number_format = '$#,##0.00'

        # TOTAL row with SUBTOTAL formulas
        data_last_row = ws.max_row
        totals_row = data_last_row + 1
        bold_font = Font(bold=True)
        ws.cell(row=totals_row, column=1, value="TOTAL").font = bold_font

        ws.cell(row=totals_row, column=3, value=f"=SUBTOTAL(9,C2:C{data_last_row})").font = bold_font
        ws.cell(row=totals_row, column=3).number_format = '#,##0'
        ws.cell(row=totals_row, column=4, value=f"=SUBTOTAL(9,D2:D{data_last_row})").font = bold_font
        ws.cell(row=totals_row, column=4).number_format = '$#,##0.00'

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:E{data_last_row}"

    buf.seek(0)
    return buf
