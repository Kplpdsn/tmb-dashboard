"""Average Day PDF report generation using ReportLab."""

from datetime import datetime
from io import BytesIO

import numpy as np
import pandas as pd
from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import (
    PDF_HEADER_BG, PDF_TEXT_PRIMARY, PDF_BORDER, PDF_POSITIVE, PDF_NEGATIVE,
    PIE_COLORS, MONTH_NAMES, DAY_NAMES_ORDERED, AVERAGE_DAY_ROLLING_WINDOW,
)


def generate(df, selected_day_name, selected_category="All Categories", selected_months=None):
    """Generate Average Day PDF report. Returns BytesIO buffer.

    Args:
        df: Full loaded DataFrame (all data in the loaded date range).
        selected_day_name: e.g. "Monday".
        selected_category: Category filter.
        selected_months: List of month numbers (1-12) or None.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Heading1"], fontSize=24,
        textColor=colors.HexColor(PDF_TEXT_PRIMARY), spaceAfter=10,
        alignment=TA_CENTER, fontName="Helvetica-Bold",
    )
    heading = ParagraphStyle(
        "CustomHeading", parent=styles["Heading2"], fontSize=14,
        textColor=colors.HexColor(PDF_TEXT_PRIMARY), spaceAfter=10,
        spaceBefore=16, fontName="Helvetica-Bold",
    )
    # FIX 1: Reduced borderPadding from 12->6, added explicit spaceAfter to prevent overlap
    insight_style = ParagraphStyle(
        "Insight", parent=styles["Normal"], fontSize=10,
        leftIndent=10, rightIndent=10, spaceAfter=6, spaceBefore=2,
        backColor=colors.HexColor("#F0F4EF"), borderPadding=6,
        borderWidth=1, borderColor=colors.HexColor(PDF_BORDER),
    )

    # --- Prepare data ---
    day_df = df[df["DayName"] == selected_day_name].copy()
    if selected_months:
        day_df = day_df[day_df["Date"].dt.month.isin(selected_months)]

    daily_totals = day_df.groupby(day_df["Date"].dt.date).agg(
        Revenue=("Revenue", "sum"),
        Quantity=("Quantity", "sum"),
        Baskets=("Basket_ID", "nunique"),
    ).reset_index()
    daily_totals["Date"] = pd.to_datetime(daily_totals["Date"])
    daily_totals["AvgBasketValue"] = daily_totals["Revenue"] / daily_totals["Baskets"].replace(0, np.nan)

    num_instances = len(daily_totals)
    first_date = daily_totals["Date"].min()
    last_date = daily_totals["Date"].max()

    avg_rev = daily_totals["Revenue"].mean()
    std_rev = daily_totals["Revenue"].std() if num_instances > 1 else 0
    avg_trans = daily_totals["Baskets"].mean()
    avg_basket_val = daily_totals["AvgBasketValue"].mean()
    avg_units = daily_totals["Quantity"].mean()

    # Peak hour
    hourly_by_date = day_df.groupby([day_df["Date"].dt.date, "Hour"])["Revenue"].sum().reset_index()
    hourly_stats = hourly_by_date.groupby("Hour")["Revenue"].agg(["mean", "std"]).reset_index()
    hourly_stats["std"] = hourly_stats["std"].fillna(0)
    peak_hour = int(hourly_stats.loc[hourly_stats["mean"].idxmax(), "Hour"]) if not hourly_stats.empty else 0
    peak_rev = hourly_stats["mean"].max() if not hourly_stats.empty else 0

    # Top product
    product_daily = day_df.groupby([day_df["Date"].dt.date, "Description"])["Revenue"].sum().reset_index()
    avg_product = product_daily.groupby("Description")["Revenue"].mean().sort_values(ascending=False)
    top_product = avg_product.index[0] if len(avg_product) > 0 else "N/A"
    top_product_rev = avg_product.iloc[0] if len(avg_product) > 0 else 0

    # Day ranking
    all_daily = df.groupby([df["Date"].dt.date, "DayName"])["Revenue"].sum().reset_index()
    day_avgs = all_daily.groupby("DayName")["Revenue"].mean().sort_values(ascending=False)
    day_rank = list(day_avgs.index).index(selected_day_name) + 1 if selected_day_name in day_avgs.index else 0

    # Trend
    trend_data = daily_totals.sort_values("Date")
    if len(trend_data) >= 2:
        x_num = np.arange(len(trend_data))
        slope, intercept = np.polyfit(x_num, trend_data["Revenue"].values, 1)
        pct_change = (slope * len(trend_data)) / trend_data["Revenue"].mean() * 100 if trend_data["Revenue"].mean() > 0 else 0
        trend_dir = "up" if slope > 0 else "down"
    else:
        pct_change = 0
        trend_dir = "stable"

    # =====================================================================
    # PAGE 1: Cover & Executive Summary
    # =====================================================================
    story += [Spacer(1, 1.2 * inch)]
    story += [Paragraph("TMB HARRIS FARM", title_style)]
    story += [Paragraph(f"AVERAGE {selected_day_name.upper()} REPORT", ParagraphStyle(
        "Sub", parent=styles["Heading2"], fontSize=16, alignment=TA_CENTER,
    ))]
    story += [Spacer(1, 0.5 * inch)]

    meta = [
        ["Day Analyzed:", selected_day_name],
        ["Data Period:", f"{first_date.strftime('%B %d, %Y')} to {last_date.strftime('%B %d, %Y')}"],
        ["Instances Analyzed:", f"{num_instances} {selected_day_name}s"],
        ["Currency:", "AUD ($)"],
        ["Generated:", datetime.now().strftime("%B %d, %Y at %I:%M %p")],
    ]
    if selected_category != "All Categories":
        meta.append(["Category Filter:", selected_category])
    if selected_months:
        month_names = [MONTH_NAMES[m - 1] for m in sorted(selected_months)]
        meta.append(["Month Filter:", ", ".join(month_names)])

    t = Table(meta, colWidths=[2 * inch, 4 * inch])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, -1), "RIGHT"), ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [t, Spacer(1, 0.4 * inch)]

    # Executive Summary
    story += [Paragraph("EXECUTIVE SUMMARY", heading)]
    insights = [
        f"An average {selected_day_name} generates <b>${avg_rev:,.0f}</b> in revenue "
        f"across <b>{avg_trans:,.0f}</b> transactions.",
        f"Peak trading hour: <b>{peak_hour}:00</b> with ${peak_rev:,.0f} average revenue.",
        f"Top product: <b>{top_product}</b> averaging ${top_product_rev:,.0f} per {selected_day_name}.",
        f"{selected_day_name} ranks <b>#{day_rank}</b> out of 7 days by average revenue.",
    ]
    # FIX 7: Only show trend in summary if we have enough data to be meaningful
    if abs(pct_change) > 1 and num_instances >= 5:
        insights.append(
            f"{selected_day_name} revenue is trending <b>{trend_dir}</b> "
            f"by {abs(pct_change):,.1f}% over the period."
        )
    elif abs(pct_change) > 1 and num_instances < 5:
        insights.append(
            f"{selected_day_name} revenue appears to be trending <b>{trend_dir}</b> "
            f"({abs(pct_change):,.1f}%), but only {num_instances} data points — treat with caution."
        )

    for ins in insights:
        story += [Paragraph(f"&bull; {ins}", insight_style)]
    story += [Spacer(1, 0.15 * inch)]

    story += [PageBreak()]

    # =====================================================================
    # PAGE 2: Key Metrics & Hourly Pattern
    # =====================================================================
    story += [Paragraph("KEY METRICS", heading)]
    metrics_data = [
        ["Metric", "Mean", "Std Dev", "Min", "Max", "Median"],
        [
            "Revenue",
            f"${avg_rev:,.2f}",
            f"${std_rev:,.2f}",
            f"${daily_totals['Revenue'].min():,.2f}",
            f"${daily_totals['Revenue'].max():,.2f}",
            f"${daily_totals['Revenue'].median():,.2f}",
        ],
        [
            "Units Sold",
            f"{avg_units:,.0f}",
            f"{daily_totals['Quantity'].std():,.0f}" if num_instances > 1 else "N/A",
            f"{daily_totals['Quantity'].min():,.0f}",
            f"{daily_totals['Quantity'].max():,.0f}",
            f"{daily_totals['Quantity'].median():,.0f}",
        ],
        [
            "Transactions",
            f"{avg_trans:,.0f}",
            f"{daily_totals['Baskets'].std():,.0f}" if num_instances > 1 else "N/A",
            f"{daily_totals['Baskets'].min():,.0f}",
            f"{daily_totals['Baskets'].max():,.0f}",
            f"{daily_totals['Baskets'].median():,.0f}",
        ],
        [
            "Basket Value",
            f"${avg_basket_val:,.2f}",
            f"${daily_totals['AvgBasketValue'].std():,.2f}" if num_instances > 1 else "N/A",
            f"${daily_totals['AvgBasketValue'].min():,.2f}",
            f"${daily_totals['AvgBasketValue'].max():,.2f}",
            f"${daily_totals['AvgBasketValue'].median():,.2f}",
        ],
    ]
    story += [_styled_table(metrics_data, [1.2 * inch, 1 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch])]
    story += [Spacer(1, 0.3 * inch)]

    # Hourly pattern chart
    story += [Paragraph("AVERAGE HOURLY REVENUE PATTERN", heading)]
    hourly_filtered = hourly_stats[(hourly_stats["Hour"] >= 6) & (hourly_stats["Hour"] <= 22)].reset_index(drop=True)

    if not hourly_filtered.empty:
        d_hourly = Drawing(450, 220)
        lc = HorizontalLineChart()
        lc.x, lc.y, lc.height, lc.width = 50, 50, 140, 350
        lc.data = [hourly_filtered["mean"].tolist()]
        lc.categoryAxis.categoryNames = [f"{int(h)}:00" for h in hourly_filtered["Hour"]]
        lc.categoryAxis.labels.fontSize = 8
        lc.valueAxis.valueMin = 0
        lc.lines[0].strokeColor = colors.HexColor(PDF_HEADER_BG)
        lc.lines[0].strokeWidth = 2.5
        lc.lineLabelFormat = "%d"
        lc.lineLabels.fontName = "Helvetica-Bold"
        lc.lineLabels.fontSize = 8
        lc.lineLabels.boxAnchor = "n"
        lc.lineLabels.dy = 5
        lc.categoryAxis.visibleGrid = 1
        lc.categoryAxis.gridStrokeColor = colors.HexColor("#D1D5DB")
        lc.categoryAxis.gridStrokeDashArray = [2, 2]
        d_hourly.add(lc)
        story += [d_hourly]

        story += [Spacer(1, 0.1 * inch)]
        story += [Paragraph(
            f"<b>Peak hour:</b> {peak_hour}:00 | "
            f"<b>Quietest hour:</b> {int(hourly_filtered.loc[hourly_filtered['mean'].idxmin(), 'Hour'])}:00",
            insight_style,
        )]

    story += [PageBreak()]

    # =====================================================================
    # PAGE 3: Product & Category Analysis
    # =====================================================================
    story += [Paragraph("TOP 10 PRODUCTS BY AVERAGE DAILY REVENUE", heading)]
    top_products = avg_product.head(10).sort_values(ascending=True)

    if not top_products.empty:
        # FIX 2: Wider label area (x=220) and longer product names (22 chars)
        d_prod = Drawing(460, 250)
        bc_prod = HorizontalBarChart()
        bc_prod.x, bc_prod.y, bc_prod.height, bc_prod.width = 220, 30, 200, 190
        bc_prod.data = [top_products.values.tolist()]
        bc_prod.categoryAxis.categoryNames = [
            f"{p[:22]} (${r:,.0f})" for p, r in zip(top_products.index, top_products.values)
        ]
        bc_prod.categoryAxis.labels.fontSize = 7
        bc_prod.categoryAxis.labels.fontName = "Helvetica-Bold"
        bc_prod.valueAxis.valueMin = 0
        bc_prod.valueAxis.labels.fontSize = 8
        bc_prod.bars[0].fillColor = colors.HexColor(PDF_HEADER_BG)
        d_prod.add(bc_prod)
        story += [d_prod, Spacer(1, 0.15 * inch)]

    # FIX 4: Category pie chart — increase label offset, smaller font for small slices
    story += [Paragraph("CATEGORY REVENUE DISTRIBUTION", heading)]
    cat_rev = day_df.groupby("Category")["Revenue"].sum().sort_values(ascending=False).reset_index()
    total_cat_rev = cat_rev["Revenue"].sum()

    if not cat_rev.empty:
        d_pie = Drawing(460, 220)
        pie = Pie()
        pie.x, pie.y, pie.width, pie.height = 130, 15, 140, 140
        pie.data = cat_rev["Revenue"].tolist()
        pie.labels = [
            f"{c[:18]} ({r / total_cat_rev * 100:.0f}%)"
            for c, r in zip(cat_rev["Category"], cat_rev["Revenue"])
        ]
        pie.slices.strokeWidth = 1
        pie.slices.strokeColor = colors.white
        pie.slices.fontName = "Helvetica"
        pie.slices.fontSize = 7
        pie.sideLabels = 1
        pie.simpleLabels = 0
        pie.sideLabelsOffset = 0.3
        # Hide labels for very small slices (<3%) to prevent overlap
        for i, (_, row) in enumerate(cat_rev.iterrows()):
            pct = row["Revenue"] / total_cat_rev * 100
            if i < len(PIE_COLORS):
                pie.slices[i].fillColor = colors.HexColor(PIE_COLORS[i])
            if pct < 3:
                pie.slices[i].fontSize = 6
        d_pie.add(pie)
        story += [d_pie, Spacer(1, 0.1 * inch)]

    # FIX 3 & 5: Best sellers table — wider columns, no PageBreak after (stays on same page)
    story += [Paragraph("BEST SELLERS TABLE", heading)]
    best = avg_product.head(10).reset_index()
    best.columns = ["Product", "AvgDailyRevenue"]
    product_daily_units = day_df.groupby([day_df["Date"].dt.date, "Description"])["Quantity"].sum().reset_index()
    avg_units_prod = product_daily_units.groupby("Description")["Quantity"].mean()
    best["AvgDailyUnits"] = best["Product"].map(avg_units_prod).fillna(0)
    best["PctOfDay"] = (best["AvgDailyRevenue"] / avg_rev * 100) if avg_rev > 0 else 0

    best_rows = [["Product", "Avg Revenue", "Avg Units", "% of Day"]]
    for _, row in best.iterrows():
        best_rows.append([
            row["Product"][:28],
            f"${row['AvgDailyRevenue']:,.2f}",
            f"{row['AvgDailyUnits']:,.0f}",
            f"{row['PctOfDay']:,.1f}%",
        ])
    story += [_styled_table(best_rows, [2.8 * inch, 1.2 * inch, 1 * inch, 1 * inch])]

    story += [PageBreak()]

    # =====================================================================
    # PAGE 4: Trends & Seasonality
    # =====================================================================
    story += [Paragraph(f"{selected_day_name.upper()} REVENUE TREND", heading)]

    if len(trend_data) >= 2:
        d_trend = Drawing(450, 220)
        lc_trend = HorizontalLineChart()
        lc_trend.x, lc_trend.y, lc_trend.height, lc_trend.width = 50, 50, 140, 350
        lc_trend.data = [trend_data["Revenue"].tolist()]

        # Date labels - show every Nth for readability
        n_labels = len(trend_data)
        step = max(1, n_labels // 10)
        cat_names = []
        for i, d in enumerate(trend_data["Date"]):
            cat_names.append(d.strftime("%b %d") if i % step == 0 else "")
        lc_trend.categoryAxis.categoryNames = cat_names
        lc_trend.categoryAxis.labels.fontSize = 7
        lc_trend.categoryAxis.labels.angle = 45
        lc_trend.valueAxis.valueMin = 0
        lc_trend.lines[0].strokeColor = colors.HexColor(PDF_HEADER_BG)
        lc_trend.lines[0].strokeWidth = 2
        lc_trend.categoryAxis.visibleGrid = 1
        lc_trend.categoryAxis.gridStrokeColor = colors.HexColor("#D1D5DB")
        lc_trend.categoryAxis.gridStrokeDashArray = [2, 2]
        d_trend.add(lc_trend)
        story += [d_trend, Spacer(1, 0.1 * inch)]

        # FIX 7: Add small-sample caveat when trend is based on few data points
        trend_color = PDF_POSITIVE if slope > 0 else PDF_NEGATIVE
        if num_instances >= 5:
            story += [Paragraph(
                f"<b>Trend:</b> {selected_day_name} revenue is trending "
                f"<font color='{trend_color}'><b>{trend_dir} {abs(pct_change):,.1f}%</b></font> "
                f"over the period.",
                insight_style,
            )]
        else:
            story += [Paragraph(
                f"<b>Trend:</b> {selected_day_name} revenue appears to be trending "
                f"<font color='{trend_color}'><b>{trend_dir} {abs(pct_change):,.1f}%</b></font> "
                f"over the period. <i>(Based on only {num_instances} data points — "
                f"load more data for a reliable trend.)</i>",
                insight_style,
            )]
    else:
        story += [Paragraph("Not enough data points for trend analysis.", styles["Normal"])]

    story += [Spacer(1, 0.3 * inch)]

    # FIX 6: Only show seasonality if we have 2+ months of data
    day_df_months = day_df.copy()
    day_df_months["MonthNum"] = day_df_months["Date"].dt.month
    monthly_rev = day_df_months.groupby([day_df_months["Date"].dt.date, "MonthNum"])["Revenue"].sum().reset_index()
    monthly_agg = monthly_rev.groupby("MonthNum").agg(
        AvgRevenue=("Revenue", "mean"),
        Instances=("Revenue", "count"),
    ).reset_index()

    if len(monthly_agg) >= 2:
        story += [Paragraph("MONTHLY SEASONALITY", heading)]
        overall_monthly_avg = monthly_agg["AvgRevenue"].mean()

        season_rows = [["Month", "Avg Revenue", "Instances", "vs Overall"]]
        for _, row in monthly_agg.iterrows():
            month_name = MONTH_NAMES[int(row["MonthNum"]) - 1]
            vs_overall = ((row["AvgRevenue"] - overall_monthly_avg) / overall_monthly_avg * 100) if overall_monthly_avg > 0 else 0
            sign = "+" if vs_overall >= 0 else ""
            season_rows.append([
                month_name,
                f"${row['AvgRevenue']:,.2f}",
                f"{int(row['Instances'])}",
                f"{sign}{vs_overall:,.1f}%",
            ])
        story += [_styled_table(season_rows, [1.5 * inch, 1.5 * inch, 1 * inch, 1.2 * inch])]
    else:
        story += [Paragraph(
            f"<i>Seasonality requires 2+ months of {selected_day_name} data. "
            f"Currently only {len(monthly_agg)} month loaded.</i>",
            ParagraphStyle("Note", parent=styles["Normal"], fontSize=10,
                           textColor=colors.HexColor("#6B7280"), spaceAfter=10),
        )]

    story += [PageBreak()]

    # =====================================================================
    # PAGE 5: Day Comparison
    # =====================================================================
    story += [Paragraph("DAY-OF-WEEK COMPARISON", heading)]
    story += [Paragraph(
        "Comparison of all days in the loaded data range",
        ParagraphStyle("SC", parent=styles["Normal"], fontSize=10,
                       textColor=colors.HexColor("#6B7280"), spaceAfter=12),
    )]

    all_daily_full = df.groupby([df["Date"].dt.date, "DayName"]).agg(
        Revenue=("Revenue", "sum"),
        Transactions=("Basket_ID", "nunique"),
    ).reset_index()
    day_comp = all_daily_full.groupby("DayName").agg(
        AvgRevenue=("Revenue", "mean"),
        AvgTransactions=("Transactions", "mean"),
        Instances=("Revenue", "count"),
    ).reset_index()
    day_comp["AvgBasketValue"] = day_comp["AvgRevenue"] / day_comp["AvgTransactions"].replace(0, np.nan)
    day_comp = day_comp.sort_values("AvgRevenue", ascending=False)
    day_comp["Rank"] = range(1, len(day_comp) + 1)

    comp_rows = [["Rank", "Day", "Avg Revenue", "Avg Trans", "Avg Basket", "Count"]]
    for _, row in day_comp.iterrows():
        comp_rows.append([
            f"#{int(row['Rank'])}",
            row["DayName"],
            f"${row['AvgRevenue']:,.2f}",
            f"{row['AvgTransactions']:,.0f}",
            f"${row['AvgBasketValue']:,.2f}",
            f"{int(row['Instances'])}",
        ])

    # FIX 8 (partial): Highlight selected day's row in the table
    comp_table = _styled_table(
        comp_rows,
        [0.6 * inch, 1.3 * inch, 1.2 * inch, 1 * inch, 1 * inch, 0.8 * inch],
    )
    # Find the row index for the selected day and highlight it
    for i, row_data in enumerate(comp_rows[1:], start=1):
        if row_data[1] == selected_day_name:
            comp_table.setStyle(TableStyle([
                ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#E8F0E3")),
                ("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"),
            ]))
            break
    story += [comp_table]

    story += [Spacer(1, 0.2 * inch)]

    # Highlight selected day's ranking
    story += [Paragraph(
        f"<b>{selected_day_name}</b> ranks <b>#{day_rank}</b> out of {len(day_comp)} days "
        f"by average revenue.",
        insight_style,
    )]

    # FIX 8: Revenue comparison bar chart — highlight selected day
    story += [Spacer(1, 0.3 * inch)]
    story += [Paragraph("AVERAGE REVENUE BY DAY OF WEEK", heading)]

    day_chart_data = day_comp.sort_values("AvgRevenue", ascending=True)
    d_daycomp = Drawing(450, 200)
    bc_day = HorizontalBarChart()
    bc_day.x, bc_day.y, bc_day.height, bc_day.width = 120, 30, 150, 280

    # Single data series with per-bar coloring via tuple index
    chart_vals = day_chart_data["AvgRevenue"].tolist()
    bc_day.data = [chart_vals]
    bc_day.categoryAxis.categoryNames = [
        f"{d} (${r:,.0f})" for d, r in zip(day_chart_data["DayName"], day_chart_data["AvgRevenue"])
    ]
    bc_day.categoryAxis.labels.fontSize = 8
    bc_day.categoryAxis.labels.fontName = "Helvetica-Bold"
    bc_day.valueAxis.valueMin = 0
    bc_day.valueAxis.labels.fontSize = 8
    bc_day.bars[0].fillColor = colors.HexColor(PDF_HEADER_BG)
    # Highlight the selected day's bar in green
    for i, (_, row) in enumerate(day_chart_data.iterrows()):
        if row["DayName"] == selected_day_name:
            bc_day.bars[(0, i)].fillColor = colors.HexColor(PDF_POSITIVE)
    d_daycomp.add(bc_day)
    story += [d_daycomp]

    # Build PDF
    doc.build(story)
    buf.seek(0)
    return buf


def _styled_table(data, col_widths):
    """Create a consistently styled table."""
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PDF_HEADER_BG)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.HexColor(PDF_BORDER)),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t
