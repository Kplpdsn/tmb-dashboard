"""Average Day PDF report — narrative layout.

Page 1:  The Story (executive brief an owner can read standalone)
Page 2:  Trading Pattern (hourly revenue with confidence band concept)
Page 3:  Product Performance (top products, category pie, best-sellers table)
Page 4+: Conditional — trend, seasonality, day comparison (only when data warrants)
"""

from datetime import datetime
from io import BytesIO

import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from config import (
    PDF_HEADER_BG, PDF_TEXT_PRIMARY, PDF_BORDER, PDF_POSITIVE, PDF_NEGATIVE,
    PIE_COLORS, MONTH_NAMES, DAY_NAMES_ORDERED, AVERAGE_DAY_ROLLING_WINDOW,
)
from reports.charts import (
    render_horizontal_bar_chart,
    render_line_chart,
    render_pie_chart,
)
from services.insights import generate_insights


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(df, selected_day_name, selected_category="All Categories", selected_months=None):
    """Generate Average Day PDF report. Returns BytesIO buffer.

    Args:
        df: Full loaded DataFrame (all data in the loaded date range).
        selected_day_name: e.g. "Monday".
        selected_category: Category filter.
        selected_months: List of month numbers (1-12) or None.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
    )

    styles = _build_styles()

    # --- Filter to selected day (+ optional month filter) ---
    day_df = df[df["DayName"] == selected_day_name].copy()
    if selected_months:
        day_df = day_df[day_df["Date"].dt.month.isin(selected_months)]

    # --- Pre-compute everything we'll reference across pages ---
    ctx = _build_context(df, day_df, selected_day_name, selected_category, selected_months)

    story = []
    story += _page_story(ctx, styles)
    story += [PageBreak()]
    story += _page_trading_pattern(ctx, styles)
    story += [PageBreak()]
    story += _page_product_performance(ctx, day_df, styles)

    # Conditional pages — only when data warrants
    conditional = _page_conditional(ctx, day_df, df, selected_day_name, styles)
    if conditional:
        story += [PageBreak()]
        story += conditional

    doc.build(story)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _build_styles():
    """Return a dict of ParagraphStyles used throughout the report."""
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "CustomTitle", parent=base["Heading1"], fontSize=22,
            textColor=colors.HexColor(PDF_TEXT_PRIMARY), spaceAfter=6,
            alignment=TA_CENTER, fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Heading2"], fontSize=13,
            textColor=colors.HexColor("#6B7280"), spaceAfter=4,
            alignment=TA_CENTER, fontName="Helvetica",
        ),
        "heading": ParagraphStyle(
            "CustomHeading", parent=base["Heading2"], fontSize=14,
            textColor=colors.HexColor(PDF_TEXT_PRIMARY), spaceAfter=10,
            spaceBefore=16, fontName="Helvetica-Bold",
        ),
        "headline": ParagraphStyle(
            "Headline", parent=base["Normal"], fontSize=12,
            textColor=colors.HexColor(PDF_TEXT_PRIMARY), spaceAfter=14,
            spaceBefore=10, fontName="Helvetica", leading=18,
            leftIndent=10, rightIndent=10,
        ),
        "insight": ParagraphStyle(
            "Insight", parent=base["Normal"], fontSize=10,
            leftIndent=10, rightIndent=10, spaceAfter=6, spaceBefore=2,
            backColor=colors.HexColor("#F0F4EF"), borderPadding=6,
            borderWidth=1, borderColor=colors.HexColor(PDF_BORDER),
        ),
        "body": base["Normal"],
        "note": ParagraphStyle(
            "Note", parent=base["Normal"], fontSize=10,
            textColor=colors.HexColor("#6B7280"), spaceAfter=10,
        ),
        "footer_note": ParagraphStyle(
            "FooterNote", parent=base["Normal"], fontSize=10,
            textColor=colors.HexColor("#9CA3AF"), spaceBefore=20,
            alignment=TA_CENTER, fontName="Helvetica-Oblique",
        ),
    }


# ---------------------------------------------------------------------------
# Data context
# ---------------------------------------------------------------------------

def _build_context(df, day_df, selected_day_name, selected_category, selected_months):
    """Pre-compute all numbers referenced across multiple pages."""
    daily_totals = day_df.groupby(day_df["Date"].dt.date).agg(
        Revenue=("Revenue", "sum"),
        Quantity=("Quantity", "sum"),
        Baskets=("Basket_ID", "nunique"),
    ).reset_index()
    daily_totals["Date"] = pd.to_datetime(daily_totals["Date"])
    daily_totals["AvgBasketValue"] = (
        daily_totals["Revenue"] / daily_totals["Baskets"].replace(0, np.nan)
    )

    num_instances = len(daily_totals)
    first_date = daily_totals["Date"].min() if num_instances else pd.NaT
    last_date = daily_totals["Date"].max() if num_instances else pd.NaT

    avg_rev = daily_totals["Revenue"].mean() if num_instances else 0
    std_rev = daily_totals["Revenue"].std() if num_instances > 1 else 0
    avg_trans = daily_totals["Baskets"].mean() if num_instances else 0
    avg_basket_val = daily_totals["AvgBasketValue"].mean() if num_instances else 0
    avg_units = daily_totals["Quantity"].mean() if num_instances else 0

    # Hourly stats (mean + std per hour, averaged across instances)
    hourly_by_date = (
        day_df.groupby([day_df["Date"].dt.date, "Hour"])["Revenue"]
        .sum().reset_index()
    )
    hourly_stats = (
        hourly_by_date.groupby("Hour")["Revenue"]
        .agg(["mean", "std"]).reset_index()
    )
    hourly_stats["std"] = hourly_stats["std"].fillna(0)

    peak_hour = (
        int(hourly_stats.loc[hourly_stats["mean"].idxmax(), "Hour"])
        if not hourly_stats.empty else 0
    )
    peak_rev = hourly_stats["mean"].max() if not hourly_stats.empty else 0

    quiet_hour = (
        int(hourly_stats.loc[hourly_stats["mean"].idxmin(), "Hour"])
        if not hourly_stats.empty else 0
    )

    # Top product (average daily revenue)
    product_daily = (
        day_df.groupby([day_df["Date"].dt.date, "Description"])["Revenue"]
        .sum().reset_index()
    )
    avg_product = (
        product_daily.groupby("Description")["Revenue"]
        .mean().sort_values(ascending=False)
    )
    top_product = avg_product.index[0] if len(avg_product) > 0 else "N/A"
    top_product_rev = avg_product.iloc[0] if len(avg_product) > 0 else 0

    # Day ranking across all days in full dataset
    all_daily = df.groupby([df["Date"].dt.date, "DayName"])["Revenue"].sum().reset_index()
    day_avgs = all_daily.groupby("DayName")["Revenue"].mean().sort_values(ascending=False)
    day_rank = (
        list(day_avgs.index).index(selected_day_name) + 1
        if selected_day_name in day_avgs.index else 0
    )

    # Trend (linear fit over sorted daily totals)
    trend_data = daily_totals.sort_values("Date")
    if len(trend_data) >= 2:
        x_num = np.arange(len(trend_data))
        slope, intercept = np.polyfit(x_num, trend_data["Revenue"].values, 1)
        pct_change = (
            (slope * len(trend_data)) / trend_data["Revenue"].mean() * 100
            if trend_data["Revenue"].mean() > 0 else 0
        )
        trend_dir = "up" if slope > 0 else "down"
    else:
        slope = 0
        pct_change = 0
        trend_dir = "stable"

    # Month breakdown
    day_df_months = day_df.copy()
    day_df_months["MonthNum"] = day_df_months["Date"].dt.month
    monthly_rev = (
        day_df_months.groupby([day_df_months["Date"].dt.date, "MonthNum"])["Revenue"]
        .sum().reset_index()
    )
    monthly_agg = monthly_rev.groupby("MonthNum").agg(
        AvgRevenue=("Revenue", "mean"),
        Instances=("Revenue", "count"),
    ).reset_index()

    # Insight engine bullets (run on day-filtered data)
    days_span = (last_date - first_date).days + 1 if num_instances >= 2 else 1
    engine_insights = generate_insights(day_df, days_span=days_span)

    return {
        "selected_day_name": selected_day_name,
        "selected_category": selected_category,
        "selected_months": selected_months,
        "daily_totals": daily_totals,
        "num_instances": num_instances,
        "first_date": first_date,
        "last_date": last_date,
        "avg_rev": avg_rev,
        "std_rev": std_rev,
        "avg_trans": avg_trans,
        "avg_basket_val": avg_basket_val,
        "avg_units": avg_units,
        "hourly_stats": hourly_stats,
        "peak_hour": peak_hour,
        "peak_rev": peak_rev,
        "quiet_hour": quiet_hour,
        "avg_product": avg_product,
        "top_product": top_product,
        "top_product_rev": top_product_rev,
        "day_avgs": day_avgs,
        "day_rank": day_rank,
        "trend_data": trend_data,
        "slope": slope,
        "pct_change": pct_change,
        "trend_dir": trend_dir,
        "monthly_agg": monthly_agg,
        "engine_insights": engine_insights,
    }


# ---------------------------------------------------------------------------
# PAGE 1 — The Story
# ---------------------------------------------------------------------------

def _page_story(ctx, styles):
    """Executive brief that an owner can read standalone."""
    story = []
    day = ctx["selected_day_name"]
    n = ctx["num_instances"]
    first = ctx["first_date"]
    last = ctx["last_date"]

    # Header
    story += [Spacer(1, 0.6 * inch)]
    story += [Paragraph("TMB Harris Farm", styles["title"])]
    story += [Paragraph(f"Your Typical {day}", ParagraphStyle(
        "DayTitle", parent=styles["title"], fontSize=20,
        textColor=colors.HexColor("#4B5563"),
    ))]
    story += [Spacer(1, 0.15 * inch)]

    # Sample size line
    if pd.notna(first) and pd.notna(last):
        date_range_str = f"{first.strftime('%b %d, %Y')} to {last.strftime('%b %d, %Y')}"
    else:
        date_range_str = "N/A"
    story += [Paragraph(
        f"Based on {n} {day}s from {date_range_str}",
        styles["subtitle"],
    )]

    # Filter badges
    filter_parts = []
    if ctx["selected_category"] != "All Categories":
        filter_parts.append(f"Category: {ctx['selected_category']}")
    if ctx["selected_months"]:
        month_names = [MONTH_NAMES[m - 1] for m in sorted(ctx["selected_months"])]
        filter_parts.append(f"Months: {', '.join(month_names)}")
    if filter_parts:
        story += [Paragraph(
            " | ".join(filter_parts),
            ParagraphStyle("Filters", parent=styles["note"], alignment=TA_CENTER),
        )]

    story += [Spacer(1, 0.35 * inch)]

    # Headline sentence
    story += [Paragraph(
        f"A typical {day} brings in <b>${ctx['avg_rev']:,.0f}</b> "
        f"across <b>{ctx['avg_trans']:.0f}</b> transactions, "
        f"with an average basket of <b>${ctx['avg_basket_val']:,.2f}</b>.",
        styles["headline"],
    )]

    story += [Spacer(1, 0.2 * inch)]

    # 3 key numbers in a horizontal table
    kpi_data = [
        ["Avg Revenue", "Avg Transactions", "Avg Basket Value"],
        [
            f"${ctx['avg_rev']:,.2f}",
            f"{ctx['avg_trans']:,.0f}",
            f"${ctx['avg_basket_val']:,.2f}",
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[2.1 * inch, 2.1 * inch, 2.1 * inch])
    kpi_table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PDF_HEADER_BG)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        # Value row
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 16),
        ("TOPPADDING", (0, 1), (-1, 1), 12),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 12),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F9FAFB")),
        # Grid
        ("GRID", (0, 0), (-1, -1), 1, colors.HexColor(PDF_BORDER)),
    ]))
    story += [kpi_table]

    story += [Spacer(1, 0.3 * inch)]

    # Insight bullets — mix of hand-crafted + engine
    bullets = _build_story_bullets(ctx)
    for bullet in bullets[:5]:
        story += [Paragraph(f"&bull; {bullet}", styles["insight"])]

    story += [Spacer(1, 0.3 * inch)]
    story += [Paragraph("Details on the following pages.", styles["footer_note"])]

    return story


def _build_story_bullets(ctx):
    """Assemble 3-5 insight bullets for the story page.

    Priority: peak hour, top seller, day ranking, trend, then engine insights
    that aren't duplicates.
    """
    bullets = []
    day = ctx["selected_day_name"]

    # 1. Peak hour
    if ctx["peak_rev"] > 0:
        bullets.append(
            f"Peak trading: <b>{ctx['peak_hour']}:00</b> with "
            f"${ctx['peak_rev']:,.0f} average revenue "
            f"-- busiest hour of the day."
        )

    # 2. Top seller
    if ctx["top_product"] != "N/A":
        bullets.append(
            f"Top product: <b>{ctx['top_product']}</b> averaging "
            f"${ctx['top_product_rev']:,.0f} per {day}."
        )

    # 3. Day ranking
    if ctx["day_rank"] > 0:
        n_days = len(ctx["day_avgs"])
        bullets.append(
            f"{day} ranks <b>#{ctx['day_rank']}</b> out of "
            f"{n_days} days by average revenue."
        )

    # 4. Trend (only if meaningful)
    if abs(ctx["pct_change"]) > 1 and ctx["num_instances"] >= 5:
        bullets.append(
            f"{day} revenue is trending <b>{ctx['trend_dir']}</b> "
            f"by {abs(ctx['pct_change']):,.1f}% over the period."
        )
    elif abs(ctx["pct_change"]) > 1 and ctx["num_instances"] >= 2:
        bullets.append(
            f"{day} revenue appears to be trending <b>{ctx['trend_dir']}</b> "
            f"({abs(ctx['pct_change']):,.1f}%), but only {ctx['num_instances']} "
            f"data points -- treat with caution."
        )

    # 5. Fill from engine insights (avoid near-duplicates)
    existing_lower = " ".join(bullets).lower()
    for eng in ctx["engine_insights"]:
        if len(bullets) >= 5:
            break
        # Skip if the engine insight overlaps with something we already wrote
        eng_words = set(eng.lower().split())
        if "peak" in eng_words and "peak" in existing_lower:
            continue
        if "top seller" in eng.lower() and "top product" in existing_lower:
            continue
        bullets.append(eng)

    return bullets


# ---------------------------------------------------------------------------
# PAGE 2 — Trading Pattern
# ---------------------------------------------------------------------------

def _page_trading_pattern(ctx, styles):
    """Hourly revenue pattern with peak/quiet callout."""
    story = []
    story += [Paragraph("TRADING PATTERN", styles["heading"])]
    story += [Paragraph(
        f"Average hourly revenue across {ctx['num_instances']} "
        f"{ctx['selected_day_name']}s",
        styles["note"],
    )]

    hourly = ctx["hourly_stats"]
    hourly_filtered = hourly[
        (hourly["Hour"] >= 6) & (hourly["Hour"] <= 22)
    ].reset_index(drop=True)

    if hourly_filtered.empty:
        story += [Paragraph("No hourly data available.", styles["body"])]
        return story

    # Line chart via shared helper — mean line
    labels = [f"{int(h)}:00" for h in hourly_filtered["Hour"]]
    mean_vals = hourly_filtered["mean"].tolist()

    # Upper and lower confidence bands (mean +/- 1 std)
    upper_vals = (hourly_filtered["mean"] + hourly_filtered["std"]).tolist()
    lower_vals = (hourly_filtered["mean"] - hourly_filtered["std"]).clip(lower=0).tolist()

    chart = render_line_chart(
        labels=labels,
        data_series=[mean_vals, upper_vals, lower_vals],
        width=450, height=220,
        line_colors=[PDF_HEADER_BG, "#D1D5DB", "#D1D5DB"],
        dash_patterns=[None, [3, 3], [3, 3]],
    )
    story += [chart]
    story += [Spacer(1, 0.05 * inch)]

    # Band legend note
    if ctx["num_instances"] > 1:
        story += [Paragraph(
            "<i>Solid line = average revenue. Dashed lines = +/- one standard deviation.</i>",
            styles["note"],
        )]

    story += [Spacer(1, 0.1 * inch)]

    # Peak / quiet callout
    story += [Paragraph(
        f"<b>Peak hour:</b> {ctx['peak_hour']}:00 "
        f"(${ctx['peak_rev']:,.0f} avg) &nbsp; | &nbsp; "
        f"<b>Quietest hour:</b> {ctx['quiet_hour']}:00",
        styles["insight"],
    )]
    story += [Spacer(1, 0.15 * inch)]
    story += [Paragraph(
        "These patterns reflect your typical trading hours.",
        styles["note"],
    )]

    # Key metrics detail table
    story += [Spacer(1, 0.25 * inch)]
    story += [Paragraph("KEY METRICS DETAIL", styles["heading"])]

    daily_totals = ctx["daily_totals"]
    n = ctx["num_instances"]
    metrics_data = [
        ["Metric", "Mean", "Std Dev", "Min", "Max", "Median"],
        [
            "Revenue",
            f"${ctx['avg_rev']:,.2f}",
            f"${ctx['std_rev']:,.2f}",
            f"${daily_totals['Revenue'].min():,.2f}" if n else "N/A",
            f"${daily_totals['Revenue'].max():,.2f}" if n else "N/A",
            f"${daily_totals['Revenue'].median():,.2f}" if n else "N/A",
        ],
        [
            "Units Sold",
            f"{ctx['avg_units']:,.0f}",
            f"{daily_totals['Quantity'].std():,.0f}" if n > 1 else "N/A",
            f"{daily_totals['Quantity'].min():,.0f}" if n else "N/A",
            f"{daily_totals['Quantity'].max():,.0f}" if n else "N/A",
            f"{daily_totals['Quantity'].median():,.0f}" if n else "N/A",
        ],
        [
            "Transactions",
            f"{ctx['avg_trans']:,.0f}",
            f"{daily_totals['Baskets'].std():,.0f}" if n > 1 else "N/A",
            f"{daily_totals['Baskets'].min():,.0f}" if n else "N/A",
            f"{daily_totals['Baskets'].max():,.0f}" if n else "N/A",
            f"{daily_totals['Baskets'].median():,.0f}" if n else "N/A",
        ],
        [
            "Basket Value",
            f"${ctx['avg_basket_val']:,.2f}",
            f"${daily_totals['AvgBasketValue'].std():,.2f}" if n > 1 else "N/A",
            f"${daily_totals['AvgBasketValue'].min():,.2f}" if n else "N/A",
            f"${daily_totals['AvgBasketValue'].max():,.2f}" if n else "N/A",
            f"${daily_totals['AvgBasketValue'].median():,.2f}" if n else "N/A",
        ],
    ]
    story += [_styled_table(
        metrics_data,
        [1.2 * inch, 1 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch],
    )]

    return story


# ---------------------------------------------------------------------------
# PAGE 3 — Product Performance
# ---------------------------------------------------------------------------

def _page_product_performance(ctx, day_df, styles):
    """Top products bar chart, category pie, best-sellers table."""
    story = []
    avg_product = ctx["avg_product"]

    # Top 10 products bar chart
    story += [Paragraph("TOP 10 PRODUCTS BY AVERAGE DAILY REVENUE", styles["heading"])]
    top10 = avg_product.head(10).sort_values(ascending=True)

    if not top10.empty:
        chart = render_horizontal_bar_chart(
            labels=list(top10.index),
            values=list(top10.values),
            width=460, height=250,
        )
        story += [chart, Spacer(1, 0.15 * inch)]

    # Category distribution pie
    story += [Paragraph("CATEGORY REVENUE DISTRIBUTION", styles["heading"])]
    cat_rev = (
        day_df.groupby("Category")["Revenue"]
        .sum().sort_values(ascending=False).reset_index()
    )

    if not cat_rev.empty:
        chart_pie = render_pie_chart(
            labels=cat_rev["Category"].tolist(),
            values=cat_rev["Revenue"].tolist(),
            width=460, height=220,
        )
        story += [chart_pie, Spacer(1, 0.1 * inch)]

    # Best sellers table
    story += [Paragraph("BEST SELLERS TABLE", styles["heading"])]
    best = avg_product.head(10).reset_index()
    best.columns = ["Product", "AvgDailyRevenue"]

    product_daily_units = (
        day_df.groupby([day_df["Date"].dt.date, "Description"])["Quantity"]
        .sum().reset_index()
    )
    avg_units_prod = product_daily_units.groupby("Description")["Quantity"].mean()
    best["AvgDailyUnits"] = best["Product"].map(avg_units_prod).fillna(0)
    avg_rev = ctx["avg_rev"]
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

    return story


# ---------------------------------------------------------------------------
# PAGE 4+ — Conditional (trend, seasonality, day comparison)
# ---------------------------------------------------------------------------

def _page_conditional(ctx, day_df, df, selected_day_name, styles):
    """Only render sections where the data is sufficient. Returns empty list
    if nothing qualifies."""
    story = []
    has_content = False

    # --- Revenue Trend ---
    trend_data = ctx["trend_data"]
    if len(trend_data) >= 3:
        has_content = True
        story += [Paragraph(
            f"{selected_day_name.upper()} REVENUE TREND", styles["heading"],
        )]

        labels = []
        n_labels = len(trend_data)
        step = max(1, n_labels // 10)
        for i, d in enumerate(trend_data["Date"]):
            labels.append(d.strftime("%b %d") if i % step == 0 else "")

        chart = render_line_chart(
            labels=labels,
            data_series=[trend_data["Revenue"].tolist()],
            width=450, height=220,
        )
        story += [chart, Spacer(1, 0.1 * inch)]

        # Trend annotation
        slope = ctx["slope"]
        pct_change = ctx["pct_change"]
        trend_dir = ctx["trend_dir"]
        n = ctx["num_instances"]
        trend_color = PDF_POSITIVE if slope > 0 else PDF_NEGATIVE

        if n >= 5:
            story += [Paragraph(
                f"<b>Trend:</b> {selected_day_name} revenue is trending "
                f"<font color='{trend_color}'><b>{trend_dir} "
                f"{abs(pct_change):,.1f}%</b></font> over the period.",
                styles["insight"],
            )]
        else:
            story += [Paragraph(
                f"<b>Trend:</b> {selected_day_name} revenue appears to be trending "
                f"<font color='{trend_color}'><b>{trend_dir} "
                f"{abs(pct_change):,.1f}%</b></font> over the period. "
                f"<i>(Based on only {n} data points -- load more data "
                f"for a reliable trend.)</i>",
                styles["insight"],
            )]

        story += [Spacer(1, 0.3 * inch)]

    # --- Monthly Seasonality (need 2+ months) ---
    monthly_agg = ctx["monthly_agg"]
    if len(monthly_agg) >= 2:
        has_content = True
        story += [Paragraph("MONTHLY SEASONALITY", styles["heading"])]
        overall_monthly_avg = monthly_agg["AvgRevenue"].mean()

        season_rows = [["Month", "Avg Revenue", "Instances", "vs Overall"]]
        for _, row in monthly_agg.iterrows():
            month_name = MONTH_NAMES[int(row["MonthNum"]) - 1]
            vs_overall = (
                ((row["AvgRevenue"] - overall_monthly_avg) / overall_monthly_avg * 100)
                if overall_monthly_avg > 0 else 0
            )
            sign = "+" if vs_overall >= 0 else ""
            season_rows.append([
                month_name,
                f"${row['AvgRevenue']:,.2f}",
                f"{int(row['Instances'])}",
                f"{sign}{vs_overall:,.1f}%",
            ])
        story += [_styled_table(
            season_rows,
            [1.5 * inch, 1.5 * inch, 1 * inch, 1.2 * inch],
        )]
        story += [Spacer(1, 0.3 * inch)]

    # --- Day-of-Week Comparison ---
    all_daily_full = df.groupby([df["Date"].dt.date, "DayName"]).agg(
        Revenue=("Revenue", "sum"),
        Transactions=("Basket_ID", "nunique"),
    ).reset_index()
    day_comp = all_daily_full.groupby("DayName").agg(
        AvgRevenue=("Revenue", "mean"),
        AvgTransactions=("Transactions", "mean"),
        Instances=("Revenue", "count"),
    ).reset_index()
    day_comp["AvgBasketValue"] = (
        day_comp["AvgRevenue"] / day_comp["AvgTransactions"].replace(0, np.nan)
    )
    day_comp = day_comp.sort_values("AvgRevenue", ascending=False)
    day_comp["Rank"] = range(1, len(day_comp) + 1)

    if len(day_comp) >= 2:
        has_content = True
        story += [Paragraph("DAY-OF-WEEK COMPARISON", styles["heading"])]
        story += [Paragraph(
            "Comparison of all days in the loaded data range",
            styles["note"],
        )]

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

        comp_table = _styled_table(
            comp_rows,
            [0.6 * inch, 1.3 * inch, 1.2 * inch, 1 * inch, 1 * inch, 0.8 * inch],
        )
        # Highlight selected day's row
        for i, row_data in enumerate(comp_rows[1:], start=1):
            if row_data[1] == selected_day_name:
                comp_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#E8F0E3")),
                    ("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"),
                ]))
                break
        story += [comp_table, Spacer(1, 0.15 * inch)]

        story += [Paragraph(
            f"<b>{selected_day_name}</b> ranks <b>#{ctx['day_rank']}</b> "
            f"out of {len(day_comp)} days by average revenue.",
            styles["insight"],
        )]

        story += [Spacer(1, 0.3 * inch)]

        # Revenue comparison bar chart
        story += [Paragraph("AVERAGE REVENUE BY DAY OF WEEK", styles["heading"])]
        day_chart_data = day_comp.sort_values("AvgRevenue", ascending=True)

        chart_labels = [
            f"{d} (${r:,.0f})" for d, r
            in zip(day_chart_data["DayName"], day_chart_data["AvgRevenue"])
        ]
        chart_values = day_chart_data["AvgRevenue"].tolist()

        bar_chart = render_horizontal_bar_chart(
            labels=chart_labels,
            values=chart_values,
            width=450, height=200,
        )
        story += [bar_chart]

    if not has_content:
        return []

    return story


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
