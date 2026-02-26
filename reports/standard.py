"""Narrative single-period PDF report generation using ReportLab.

Page 1 tells the story (executive brief). Subsequent pages are evidence.
Conditional pages are only included when the data warrants them.
"""

from collections import Counter
from datetime import datetime
from io import BytesIO
from itertools import combinations

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import PDF_HEADER_BG, PDF_TEXT_PRIMARY, PDF_BORDER, PIE_COLORS
from reports.charts import (
    render_horizontal_bar_chart,
    render_line_chart,
    render_pie_chart,
    render_vertical_bar_chart,
)
from services.insights import generate_insights


# ---------------------------------------------------------------------------
# Shared styles
# ---------------------------------------------------------------------------

_PAGE_WIDTH = A4[0]

_DARK = colors.HexColor(PDF_TEXT_PRIMARY)
_HEADER_BG = colors.HexColor(PDF_HEADER_BG)
_BORDER = colors.HexColor(PDF_BORDER)
_MUTED = colors.HexColor("#6B7280")
_LIGHT_BG = colors.HexColor("#F9FAFB")


def _build_styles():
    """Return a dict of ParagraphStyles used throughout the report."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "RTitle", parent=base["Heading1"], fontSize=22,
            textColor=_DARK, spaceAfter=4, alignment=TA_LEFT,
            fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "RSub", parent=base["Normal"], fontSize=11,
            textColor=_MUTED, spaceAfter=6, alignment=TA_LEFT,
        ),
        "headline": ParagraphStyle(
            "RHeadline", parent=base["Normal"], fontSize=13,
            textColor=_DARK, spaceAfter=14, spaceBefore=10,
            leading=18, fontName="Helvetica",
        ),
        "section": ParagraphStyle(
            "RSection", parent=base["Heading2"], fontSize=14,
            textColor=_DARK, spaceAfter=10, spaceBefore=16,
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "RBody", parent=base["Normal"], fontSize=10,
            textColor=_DARK, spaceAfter=6,
        ),
        "caption": ParagraphStyle(
            "RCaption", parent=base["Normal"], fontSize=9,
            textColor=_MUTED, spaceAfter=10, spaceBefore=4,
        ),
        "bullet": ParagraphStyle(
            "RBullet", parent=base["Normal"], fontSize=10,
            textColor=_DARK, spaceAfter=5, leftIndent=16,
            bulletIndent=4, bulletFontName="Helvetica", bulletFontSize=10,
        ),
        "footer_note": ParagraphStyle(
            "RFooter", parent=base["Normal"], fontSize=9,
            textColor=_MUTED, spaceBefore=20, alignment=TA_LEFT,
        ),
    }


# ---------------------------------------------------------------------------
# Table helper
# ---------------------------------------------------------------------------

def _styled_table(data, col_widths):
    """Create a consistently styled table with header row."""
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, _BORDER),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def _kpi_row(labels_values):
    """Render a single-row table of 2-3 KPI cards.

    *labels_values* is a list of (label, value_string) tuples.
    """
    header = [lv[0] for lv in labels_values]
    values = [lv[1] for lv in labels_values]
    n = len(labels_values)
    col_w = 6.5 * inch / n

    t = Table([header, values], colWidths=[col_w] * n)
    t.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        # Value row
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 16),
        ("ALIGN", (0, 1), (-1, 1), "CENTER"),
        ("TOPPADDING", (0, 1), (-1, 1), 12),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 12),
        ("TEXTCOLOR", (0, 1), (-1, 1), _DARK),
        # Grid
        ("GRID", (0, 0), (-1, -1), 1, _BORDER),
    ]))
    return t


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def _page_executive_brief(story, sty, df, min_date, max_date, days_span,
                          selected_category, selected_product,
                          day_filter_mode, hour_range):
    """PAGE 1: The Story -- executive brief a stakeholder can read alone."""

    # --- Header ---
    story.append(Paragraph("TMB Harris Farm \u2014 Sales Report", sty["title"]))

    if days_span == 1:
        period_str = min_date.strftime("%A, %B %d, %Y")
    else:
        period_str = (
            f"{min_date.strftime('%B %d, %Y')} to {max_date.strftime('%B %d, %Y')} "
            f"({days_span} days)"
        )
    story.append(Paragraph(period_str, sty["subtitle"]))

    # Filter line
    filters = []
    if selected_category != "All Categories":
        filters.append(f"Category: {selected_category}")
    if selected_product != "All Products":
        filters.append(f"Product: {selected_product}")
    if day_filter_mode != "All Days":
        filters.append(f"Days: {day_filter_mode}")
    if hour_range:
        filters.append(f"Hours: {hour_range[0]}:00\u2013{hour_range[1]}:00")
    if filters:
        story.append(Paragraph(" | ".join(filters), sty["caption"]))

    story.append(Spacer(1, 0.15 * inch))

    # --- Headline sentence ---
    total_rev = df["Revenue"].sum()
    num_baskets = df["Basket_ID"].nunique()
    daily_avg = total_rev / max(days_span, 1)
    avg_basket = (
        df.groupby("Basket_ID")["Revenue"].sum().mean()
        if num_baskets > 0 else 0
    )

    headline = (
        f"Your bakery did <b>${total_rev:,.0f}</b> over {days_span} "
        f"day{'s' if days_span != 1 else ''}, averaging "
        f"<b>${daily_avg:,.0f}/day</b> across "
        f"<b>{num_baskets:,}</b> transactions."
    )
    story.append(Paragraph(headline, sty["headline"]))

    story.append(Spacer(1, 0.1 * inch))

    # --- 3 key numbers ---
    kpi = _kpi_row([
        ("Total Revenue", f"${total_rev:,.2f}"),
        ("Daily Average", f"${daily_avg:,.2f}"),
        ("Avg Basket", f"${avg_basket:,.2f}"),
    ])
    story.append(kpi)
    story.append(Spacer(1, 0.25 * inch))

    # --- Insights ---
    insights = generate_insights(df, days_span)
    if insights:
        story.append(Paragraph("KEY INSIGHTS", sty["section"]))
        for text in insights[:5]:
            story.append(Paragraph(
                f"\u2022  {text}", sty["bullet"]
            ))
        story.append(Spacer(1, 0.15 * inch))

    # --- Footer note ---
    story.append(Paragraph(
        "Details on the following pages.",
        sty["footer_note"],
    ))
    story.append(Spacer(1, 0.1 * inch))
    gen_ts = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    story.append(Paragraph(
        f"Generated {gen_ts}",
        ParagraphStyle("TS", parent=sty["caption"], fontSize=8,
                       textColor=_MUTED),
    ))


def _page_revenue_detail(story, sty, df, min_date, max_date, days_span):
    """PAGE 2: Revenue detail -- daily/weekly bars + breakdown table."""

    story.append(PageBreak())
    story.append(Paragraph("REVENUE DETAIL", sty["section"]))

    total_rev = df["Revenue"].sum()

    if days_span == 1 and "Hour" in df.columns:
        # Single day: hourly line chart
        story.append(Paragraph("Hourly revenue breakdown", sty["caption"]))
        h_min, h_max = int(df["Hour"].min()), int(df["Hour"].max())
        all_hrs = list(range(h_min, h_max + 1))
        hourly = (
            df.groupby("Hour")["Revenue"].sum()
            .reindex(all_hrs, fill_value=0)
            .reset_index()
        )
        hourly.columns = ["Hour", "Revenue"]

        labels = [f"{int(h)}:00" for h in hourly["Hour"]]
        chart = render_line_chart(labels, [hourly["Revenue"].tolist()], width=450, height=200)
        story.append(chart)
        story.append(Spacer(1, 0.15 * inch))

        # Hourly table
        table_data = [["Hour", "Revenue", "% of Day"]]
        for _, row in hourly.iterrows():
            pct = row["Revenue"] / total_rev * 100 if total_rev > 0 else 0
            if row["Revenue"] > 0:
                table_data.append([
                    f"{int(row['Hour'])}:00",
                    f"${row['Revenue']:,.2f}",
                    f"{pct:.1f}%",
                ])
        if len(table_data) > 1:
            story.append(_styled_table(table_data, [1.5 * inch, 2.5 * inch, 2.5 * inch]))

    else:
        # Multi-day: daily bars or line chart
        date_rng = pd.date_range(start=min_date, end=max_date, freq="D")
        daily = (
            df.groupby(df["Date"].dt.date)["Revenue"].sum()
            .reindex([d.date() for d in date_rng], fill_value=0)
            .reset_index()
        )
        daily.columns = ["Date", "Revenue"]

        if days_span <= 14:
            story.append(Paragraph("Day-by-day revenue", sty["caption"]))
            labels = [d.strftime("%a %m/%d") for d in daily["Date"]]
        else:
            story.append(Paragraph("Daily revenue trend", sty["caption"]))
            labels = [d.strftime("%m/%d") for d in daily["Date"]]

        chart = render_line_chart(labels, [daily["Revenue"].tolist()], width=450, height=200)
        story.append(chart)
        story.append(Spacer(1, 0.15 * inch))

        # Breakdown table
        table_data = [["Date", "Revenue", "% of Total"]]
        for _, row in daily.iterrows():
            pct = row["Revenue"] / total_rev * 100 if total_rev > 0 else 0
            if row["Revenue"] > 0:
                table_data.append([
                    row["Date"].strftime("%a %b %d") if days_span <= 14 else row["Date"].strftime("%m/%d"),
                    f"${row['Revenue']:,.2f}",
                    f"{pct:.1f}%",
                ])
        if len(table_data) > 1:
            # Cap table rows to avoid multi-page overflow; show top days if too many
            if len(table_data) > 22:
                header = table_data[0]
                rows_sorted = sorted(table_data[1:], key=lambda r: r[1], reverse=True)
                table_data = [header] + rows_sorted[:20]
                story.append(Paragraph(
                    f"Showing top 20 days by revenue (out of {days_span})",
                    sty["caption"],
                ))
            story.append(_styled_table(table_data, [2 * inch, 2.5 * inch, 2 * inch]))

    # Connecting caption
    daily_avg = total_rev / max(days_span, 1)
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        f"Total: ${total_rev:,.2f} across {days_span} day{'s' if days_span != 1 else ''} "
        f"(${daily_avg:,.0f}/day average).",
        sty["caption"],
    ))


def _page_product_performance(story, sty, df):
    """PAGE 3: Product performance -- top products bar, category pie, slow movers."""

    story.append(PageBreak())
    story.append(Paragraph("PRODUCT PERFORMANCE", sty["section"]))

    total_rev = df["Revenue"].sum()

    # --- Top products ---
    n_prod = min(10, max(5, len(df["Description"].unique()) // 3))
    story.append(Paragraph(f"Top {n_prod} products by revenue", sty["caption"]))

    top_prod = (
        df.groupby("Description")
        .agg({"Revenue": "sum"})
        .sort_values("Revenue", ascending=True)
        .tail(n_prod)
        .reset_index()
    )

    chart = render_horizontal_bar_chart(
        top_prod["Description"].tolist(),
        top_prod["Revenue"].tolist(),
        width=450, height=250,
    )
    story.append(chart)
    story.append(Spacer(1, 0.15 * inch))

    # Top products table
    top_full = (
        df.groupby("Description")
        .agg({"Revenue": "sum", "Quantity": "sum"})
        .sort_values("Revenue", ascending=False)
        .head(n_prod)
        .reset_index()
    )
    prod_rows = [["Product", "Revenue", "% Total", "Units"]]
    for _, row in top_full.iterrows():
        pct = row["Revenue"] / total_rev * 100 if total_rev > 0 else 0
        prod_rows.append([
            row["Description"][:35],
            f"${row['Revenue']:,.2f}",
            f"{pct:.1f}%",
            f"{int(row['Quantity']):,}",
        ])
    story.append(_styled_table(prod_rows, [3 * inch, 1.5 * inch, 0.8 * inch, 0.8 * inch]))
    story.append(Spacer(1, 0.25 * inch))

    # --- Category pie ---
    story.append(Paragraph("Revenue by category", sty["caption"]))
    cat_rev = (
        df.groupby("Category")["Revenue"].sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    chart_pie = render_pie_chart(
        cat_rev["Category"].tolist(),
        cat_rev["Revenue"].tolist(),
        width=400, height=220,
    )
    story.append(chart_pie)
    story.append(Spacer(1, 0.15 * inch))

    # Category table
    cat_rows = [["Category", "Revenue", "% Total"]]
    for _, row in cat_rev.iterrows():
        pct = row["Revenue"] / total_rev * 100 if total_rev > 0 else 0
        cat_rows.append([
            row["Category"],
            f"${row['Revenue']:,.2f}",
            f"{pct:.1f}%",
        ])
    story.append(_styled_table(cat_rows, [2.5 * inch, 2 * inch, 2 * inch]))


def _page_hourly_pattern(story, sty, df, days_span):
    """CONDITIONAL: Hourly distribution (multi-day only -- single-day is on p2)."""

    if "Hour" not in df.columns:
        return False
    if days_span <= 1:
        return False  # single day hourly is already on page 2

    h_min, h_max = int(df["Hour"].min()), int(df["Hour"].max())
    all_hrs = list(range(h_min, h_max + 1))
    hourly = (
        df.groupby("Hour")["Revenue"].sum()
        .reindex(all_hrs, fill_value=0)
        .reset_index()
    )
    hourly.columns = ["Hour", "Revenue"]

    if hourly["Revenue"].sum() <= 0:
        return False

    story.append(PageBreak())
    story.append(Paragraph("HOURLY PATTERN", sty["section"]))
    story.append(Paragraph(
        f"Revenue by hour across {days_span} days", sty["caption"],
    ))

    labels = [f"{int(h)}:00" for h in hourly["Hour"]]
    chart = render_vertical_bar_chart(
        labels, hourly["Revenue"].tolist(),
        width=450, height=220,
    )
    story.append(chart)

    # Peak hour callout
    peak_idx = hourly["Revenue"].idxmax()
    peak_hour = int(hourly.loc[peak_idx, "Hour"])
    peak_rev = hourly.loc[peak_idx, "Revenue"]
    total_rev = hourly["Revenue"].sum()
    peak_pct = peak_rev / total_rev * 100 if total_rev > 0 else 0

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        f"Peak hour: {peak_hour}:00 with ${peak_rev:,.0f} "
        f"({peak_pct:.0f}% of total revenue).",
        sty["body"],
    ))
    return True


def _page_basket_distribution(story, sty, df):
    """CONDITIONAL: Basket size distribution (only if meaningful basket count)."""

    num_baskets = df["Basket_ID"].nunique()
    if num_baskets < 10:
        return False

    basket_rev = df.groupby("Basket_ID")["Revenue"].sum()
    bins = [0, 15, 30, 50, 100, 1000]
    lbls = ["$0-15", "$15-30", "$30-50", "$50-100", "$100+"]
    dist = pd.cut(basket_rev, bins=bins, labels=lbls).value_counts().reindex(lbls, fill_value=0)

    if dist.sum() <= 0:
        return False

    story.append(PageBreak())
    story.append(Paragraph("BASKET DISTRIBUTION", sty["section"]))
    story.append(Paragraph(
        f"How {num_baskets:,} baskets break down by value",
        sty["caption"],
    ))

    chart = render_vertical_bar_chart(
        lbls, dist.tolist(), width=450, height=200,
    )
    story.append(chart)
    story.append(Spacer(1, 0.15 * inch))

    # Summary stats
    avg_bask = basket_rev.mean()
    median_bask = basket_rev.median()
    total_items = df["Quantity"].sum()
    avg_items = total_items / num_baskets if num_baskets > 0 else 0

    stats_data = [
        ["Metric", "Value"],
        ["Average basket value", f"${avg_bask:.2f}"],
        ["Median basket value", f"${median_bask:.2f}"],
        ["Average items per basket", f"{avg_items:.1f}"],
    ]
    story.append(_styled_table(stats_data, [3.5 * inch, 3 * inch]))
    return True


def _page_product_pairs(story, sty, df):
    """CONDITIONAL: Top product pairs (only if multi-item baskets exist)."""

    multi = df.groupby("Basket_ID").filter(lambda x: len(x) > 1)
    if len(multi) == 0:
        return False

    basket_pairs = []
    for _, grp in multi.groupby("Basket_ID"):
        for pair in combinations(sorted(set(grp["Description"])), 2):
            basket_pairs.append(pair)

    if not basket_pairs:
        return False

    top_pairs = Counter(basket_pairs).most_common(10)
    if not top_pairs:
        return False

    story.append(PageBreak())
    story.append(Paragraph("TOP PRODUCT PAIRS", sty["section"]))
    story.append(Paragraph(
        "Products frequently purchased together", sty["caption"],
    ))

    pairs_data = [["Product A", "Product B", "Times Together"]]
    for pair, count in top_pairs:
        pairs_data.append([pair[0][:30], pair[1][:30], f"{count:,}"])
    story.append(_styled_table(pairs_data, [2.5 * inch, 2.5 * inch, 1.5 * inch]))

    # Callout
    top_pair = top_pairs[0]
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        f"<b>Most common pair:</b> {top_pair[0][0]} + {top_pair[0][1]} "
        f"purchased together {top_pair[1]} times.",
        ParagraphStyle(
            "PairCallout", parent=sty["body"], fontSize=11,
            leftIndent=10, rightIndent=10, spaceAfter=10,
            backColor=_LIGHT_BG, borderPadding=12,
            borderWidth=1, borderColor=_BORDER,
        ),
    ))
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(df, min_date, max_date, selected_category, selected_product,
             day_filter_mode, hour_range):
    """Generate a narrative PDF report. Returns BytesIO buffer.

    Page 1 is an executive brief a stakeholder can read without context.
    Subsequent pages provide supporting evidence.
    Conditional pages are skipped when the data doesn't justify them.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=0.6 * inch,
        bottomMargin=0.5 * inch,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
    )
    story = []
    sty = _build_styles()

    days_span = (max_date - min_date).days + 1

    # PAGE 1: Executive brief
    _page_executive_brief(
        story, sty, df, min_date, max_date, days_span,
        selected_category, selected_product, day_filter_mode, hour_range,
    )

    # PAGE 2: Revenue detail
    _page_revenue_detail(story, sty, df, min_date, max_date, days_span)

    # PAGE 3: Product performance
    _page_product_performance(story, sty, df)

    # PAGE 4+: Conditional pages (only if data warrants)
    _page_hourly_pattern(story, sty, df, days_span)
    _page_basket_distribution(story, sty, df)
    _page_product_pairs(story, sty, df)

    doc.build(story)
    buf.seek(0)
    return buf
