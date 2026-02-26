"""Narrative comparison PDF report — tells the story of two periods side by side.

Page 1:  The Story (executive brief with headline, key metrics table, insights)
Page 2:  Category & Product Changes (delta bar chart, top gainers/decliners)
Page 3:  Conditional — revenue pattern comparison (hourly or daily line chart)
"""

from datetime import datetime
from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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

from config import PDF_HEADER_BG, PDF_TEXT_PRIMARY, PDF_BORDER, PDF_POSITIVE, PDF_NEGATIVE
from reports.charts import render_delta_bar_chart, render_line_chart


# ---------------------------------------------------------------------------
# Shared constants & styles
# ---------------------------------------------------------------------------

_DARK = colors.HexColor(PDF_TEXT_PRIMARY)
_HEADER_BG = colors.HexColor(PDF_HEADER_BG)
_BORDER = colors.HexColor(PDF_BORDER)
_MUTED = colors.HexColor("#6B7280")
_LIGHT_BG = colors.HexColor("#F9FAFB")
_GREEN = colors.HexColor(PDF_POSITIVE)
_RED = colors.HexColor(PDF_NEGATIVE)


def _build_styles():
    """Return a dict of ParagraphStyles used throughout the report."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "CTitle", parent=base["Heading1"], fontSize=22,
            textColor=_DARK, spaceAfter=4, alignment=TA_LEFT,
            fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "CSub", parent=base["Normal"], fontSize=11,
            textColor=_MUTED, spaceAfter=6, alignment=TA_LEFT,
        ),
        "headline": ParagraphStyle(
            "CHeadline", parent=base["Normal"], fontSize=13,
            textColor=_DARK, spaceAfter=14, spaceBefore=10,
            leading=18, fontName="Helvetica",
        ),
        "section": ParagraphStyle(
            "CSection", parent=base["Heading2"], fontSize=14,
            textColor=_DARK, spaceAfter=10, spaceBefore=16,
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "CBody", parent=base["Normal"], fontSize=10,
            textColor=_DARK, spaceAfter=6,
        ),
        "caption": ParagraphStyle(
            "CCaption", parent=base["Normal"], fontSize=9,
            textColor=_MUTED, spaceAfter=10, spaceBefore=4,
        ),
        "bullet": ParagraphStyle(
            "CBullet", parent=base["Normal"], fontSize=10,
            textColor=_DARK, spaceAfter=5, leftIndent=16,
            bulletIndent=4, bulletFontName="Helvetica", bulletFontSize=10,
        ),
        "insight": ParagraphStyle(
            "CInsight", parent=base["Normal"], fontSize=10,
            leftIndent=10, rightIndent=10, spaceAfter=6, spaceBefore=2,
            backColor=colors.HexColor("#F0F4EF"), borderPadding=6,
            borderWidth=1, borderColor=_BORDER,
        ),
        "warning": ParagraphStyle(
            "CWarn", parent=base["Normal"], fontSize=10,
            textColor=colors.HexColor("#D97706"),
            backColor=colors.HexColor("#FEF3C7"),
            borderPadding=10, borderWidth=1,
            borderColor=colors.HexColor("#F59E0B"),
        ),
        "footer_note": ParagraphStyle(
            "CFooter", parent=base["Normal"], fontSize=9,
            textColor=_MUTED, spaceBefore=20, alignment=TA_LEFT,
        ),
    }


# ---------------------------------------------------------------------------
# Table helpers
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
    """Render a single-row table of KPI cards (label/value pairs)."""
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
# Computation helpers
# ---------------------------------------------------------------------------

def _pct_change(new, old):
    """Return percentage change from old to new. Returns 0 if old is zero."""
    if old == 0:
        return 0
    return (new - old) / old * 100


def _fmt_pct(pct):
    """Format a percentage with sign and one decimal place."""
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f}%"


def _direction_word(pct):
    """Return 'rose' or 'fell' based on sign of percentage."""
    return "rose" if pct >= 0 else "fell"


def _compute_metrics(df_a, df_b, days_a, days_b, diff_lengths):
    """Compute the key comparison metrics for both periods.

    Returns a dict with all the numbers needed for the story page.
    """
    rev_a, rev_b = df_a["Revenue"].sum(), df_b["Revenue"].sum()
    bask_a = df_a["Basket_ID"].nunique()
    bask_b = df_b["Basket_ID"].nunique()
    avg_bask_a = df_a.groupby("Basket_ID")["Revenue"].sum().mean() if bask_a > 0 else 0
    avg_bask_b = df_b.groupby("Basket_ID")["Revenue"].sum().mean() if bask_b > 0 else 0

    # Use daily averages when periods differ in length
    if diff_lengths:
        comp_rev_a, comp_rev_b = rev_a / days_a, rev_b / days_b
        comp_bask_a, comp_bask_b = bask_a / days_a, bask_b / days_b
    else:
        comp_rev_a, comp_rev_b = rev_a, rev_b
        comp_bask_a, comp_bask_b = bask_a, bask_b

    rev_pct = _pct_change(comp_rev_a, comp_rev_b)
    bask_pct = _pct_change(comp_bask_a, comp_bask_b)
    avg_bask_pct = _pct_change(avg_bask_a, avg_bask_b)

    return {
        "rev_a": rev_a, "rev_b": rev_b,
        "comp_rev_a": comp_rev_a, "comp_rev_b": comp_rev_b,
        "bask_a": bask_a, "bask_b": bask_b,
        "comp_bask_a": comp_bask_a, "comp_bask_b": comp_bask_b,
        "avg_bask_a": avg_bask_a, "avg_bask_b": avg_bask_b,
        "rev_pct": rev_pct,
        "bask_pct": bask_pct,
        "avg_bask_pct": avg_bask_pct,
    }


def _compute_category_changes(df_a, df_b, days_a, days_b, diff_lengths):
    """Compute per-category revenue deltas.

    Returns a DataFrame sorted by Delta ascending (worst to best) with columns:
    Category, RevA, RevB, Delta.
    """
    cat_a = df_a.groupby("Category")["Revenue"].sum()
    cat_b = df_b.groupby("Category")["Revenue"].sum()
    if diff_lengths:
        cat_a, cat_b = cat_a / days_a, cat_b / days_b

    all_cats = sorted(set(cat_a.index) | set(cat_b.index))
    changes = []
    for cat in all_cats:
        ra, rb = cat_a.get(cat, 0), cat_b.get(cat, 0)
        changes.append({"Category": cat, "Delta": ra - rb, "RevA": ra, "RevB": rb})
    return pd.DataFrame(changes).sort_values("Delta", ascending=True)


def _compute_product_changes(df_a, df_b, days_a, days_b, diff_lengths):
    """Compute per-product revenue deltas.

    Returns a DataFrame sorted by Delta descending (best to worst) with columns:
    Product, Delta, Percent.
    """
    prod_a = df_a.groupby("Description")["Revenue"].sum()
    prod_b = df_b.groupby("Description")["Revenue"].sum()
    if diff_lengths:
        prod_a, prod_b = prod_a / days_a, prod_b / days_b

    all_prods = sorted(set(prod_a.index) | set(prod_b.index))
    prod_changes = []
    for p in all_prods:
        ra, rb = prod_a.get(p, 0), prod_b.get(p, 0)
        pct = (ra - rb) / rb * 100 if rb > 0 else 0
        prod_changes.append({"Product": p, "Delta": ra - rb, "Percent": pct})
    return pd.DataFrame(prod_changes).sort_values("Delta", ascending=False)


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def _page_executive_brief(story, sty, df_a, df_b,
                          date_a_start, date_a_end, date_b_start, date_b_end,
                          days_a, days_b, diff_lengths, metrics, cat_chg_df,
                          selected_category, selected_product,
                          day_filter_mode, hour_range):
    """PAGE 1: The Story -- executive brief a stakeholder can read alone."""

    # --- Header ---
    story.append(Paragraph("TMB Harris Farm \u2014 Period Comparison", sty["title"]))

    period_a_str = (
        f"{date_a_start.strftime('%B %d, %Y')} to {date_a_end.strftime('%B %d, %Y')}"
        if days_a > 1
        else date_a_start.strftime("%A, %B %d, %Y")
    )
    period_b_str = (
        f"{date_b_start.strftime('%B %d, %Y')} to {date_b_end.strftime('%B %d, %Y')}"
        if days_b > 1
        else date_b_start.strftime("%A, %B %d, %Y")
    )
    story.append(Paragraph(
        f"Period A: {period_a_str} ({days_a} day{'s' if days_a != 1 else ''}) &nbsp; | &nbsp; "
        f"Period B: {period_b_str} ({days_b} day{'s' if days_b != 1 else ''})",
        sty["subtitle"],
    ))

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

    # Warning for different-length periods
    if diff_lengths:
        story.append(Paragraph(
            "Different period lengths \u2014 showing daily averages for fair comparison.",
            sty["warning"],
        ))
        story.append(Spacer(1, 0.15 * inch))

    # --- Headline sentence ---
    rev_pct = metrics["rev_pct"]
    avg_bask_pct = metrics["avg_bask_pct"]
    rev_word = _direction_word(rev_pct)
    bask_word = "up" if avg_bask_pct >= 0 else "down"

    if diff_lengths:
        rev_label = "Daily average revenue"
        rev_a_str = f"${metrics['comp_rev_a']:,.0f}/day"
        rev_b_str = f"${metrics['comp_rev_b']:,.0f}/day"
    else:
        rev_label = "Revenue"
        rev_a_str = f"${metrics['rev_a']:,.0f}"
        rev_b_str = f"${metrics['rev_b']:,.0f}"

    headline = (
        f"{rev_label} <b>{rev_word} {abs(rev_pct):.1f}%</b> from {rev_b_str} to {rev_a_str}, "
        f"with basket values <b>{bask_word} {abs(avg_bask_pct):.1f}%</b>."
    )
    story.append(Paragraph(headline, sty["headline"]))
    story.append(Spacer(1, 0.1 * inch))

    # --- 3 key comparison metrics table ---
    label_note = " (daily avg)" if diff_lengths else ""
    comp_data = [
        ["Metric", "Period A", "Period B", "Change"],
        [
            f"Revenue{label_note}",
            f"${metrics['comp_rev_a']:,.2f}",
            f"${metrics['comp_rev_b']:,.2f}",
            _fmt_pct(rev_pct),
        ],
        [
            f"Transactions{label_note}",
            f"{metrics['comp_bask_a']:,.0f}",
            f"{metrics['comp_bask_b']:,.0f}",
            _fmt_pct(metrics["bask_pct"]),
        ],
        [
            "Avg Basket Value",
            f"${metrics['avg_bask_a']:.2f}",
            f"${metrics['avg_bask_b']:.2f}",
            _fmt_pct(avg_bask_pct),
        ],
    ]

    comp_table = _styled_table(
        comp_data,
        [2.2 * inch, 1.5 * inch, 1.5 * inch, 1.3 * inch],
    )
    # Color-code the Change column: green for positive, red for negative
    for row_idx in range(1, len(comp_data)):
        pct_val = [rev_pct, metrics["bask_pct"], avg_bask_pct][row_idx - 1]
        cell_color = _GREEN if pct_val >= 0 else _RED
        comp_table.setStyle(TableStyle([
            ("TEXTCOLOR", (3, row_idx), (3, row_idx), cell_color),
            ("FONTNAME", (3, row_idx), (3, row_idx), "Helvetica-Bold"),
        ]))
    story.append(comp_table)
    story.append(Spacer(1, 0.25 * inch))

    # --- Insight bullets ---
    bullets = _build_insights(metrics, cat_chg_df, diff_lengths)
    if bullets:
        story.append(Paragraph("INSIGHTS", sty["section"]))
        for text in bullets[:5]:
            story.append(Paragraph(f"\u2022  {text}", sty["bullet"]))
        story.append(Spacer(1, 0.15 * inch))

    # --- Footer ---
    story.append(Paragraph("Details on the following pages.", sty["footer_note"]))
    story.append(Spacer(1, 0.1 * inch))
    gen_ts = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    story.append(Paragraph(
        f"Generated {gen_ts}",
        ParagraphStyle("CTS", parent=sty["caption"], fontSize=8, textColor=_MUTED),
    ))


def _page_category_product_changes(story, sty, cat_chg_df, prod_chg_df, diff_lengths):
    """PAGE 2: Category revenue changes chart + top gainers/decliners tables."""

    story.append(PageBreak())
    label_note = " (daily avg)" if diff_lengths else ""

    # --- Category delta bar chart ---
    story.append(Paragraph("CATEGORY REVENUE CHANGES", sty["section"]))
    story.append(Paragraph(
        f"Revenue change per category{label_note} from Period B to Period A",
        sty["caption"],
    ))

    chart_labels = [
        f"{row['Category'][:18]} ({row['Delta']:+,.0f})"
        for _, row in cat_chg_df.iterrows()
    ]
    chart_values = cat_chg_df["Delta"].tolist()

    chart = render_delta_bar_chart(
        labels=chart_labels,
        values=chart_values,
        width=450,
        height=max(180, len(chart_labels) * 22),
    )
    story.append(chart)
    story.append(Spacer(1, 0.2 * inch))

    # Top gainer / decliner callouts
    top_gainer = cat_chg_df.iloc[-1]
    top_decliner = cat_chg_df.iloc[0]
    if top_gainer["Delta"] > 0:
        story.append(Paragraph(
            f"<b>Top gainer:</b> {top_gainer['Category']} "
            f"(+${abs(top_gainer['Delta']):,.0f}{label_note})",
            ParagraphStyle("CGain", parent=sty["body"], fontSize=11,
                           backColor=colors.HexColor("#F0FDF4"), borderPadding=10),
        ))
    if top_decliner["Delta"] < 0:
        story.append(Paragraph(
            f"<b>Top decliner:</b> {top_decliner['Category']} "
            f"(-${abs(top_decliner['Delta']):,.0f}{label_note})",
            ParagraphStyle("CDecl", parent=sty["body"], fontSize=11,
                           backColor=colors.HexColor("#FEF2F2"), borderPadding=10),
        ))

    story.append(Spacer(1, 0.3 * inch))

    # --- Top 5 Gainers table ---
    gainers = prod_chg_df[prod_chg_df["Delta"] > 0].head(5)
    decliners = prod_chg_df[prod_chg_df["Delta"] < 0].tail(5).iloc[::-1]

    story.append(Paragraph("TOP PRODUCT MOVERS", sty["section"]))

    if len(gainers) > 0:
        g_data = [["Top 5 Gainers", f"Change{label_note}", "% Change"]]
        for _, r in gainers.iterrows():
            g_data.append([
                r["Product"][:30],
                f"+${r['Delta']:,.0f}",
                f"{r['Percent']:+.0f}%" if r["Percent"] != 0 else "new",
            ])
        gt = Table(g_data, colWidths=[3 * inch, 1.5 * inch, 1.2 * inch])
        gt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 1, _BORDER),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ]))
        story.append(gt)
        story.append(Spacer(1, 0.15 * inch))

    # --- Top 5 Decliners table ---
    if len(decliners) > 0:
        d_data = [["Top 5 Decliners", f"Change{label_note}", "% Change"]]
        for _, r in decliners.iterrows():
            d_data.append([
                r["Product"][:30],
                f"-${abs(r['Delta']):,.0f}",
                f"{r['Percent']:.0f}%",
            ])
        dt_table = Table(d_data, colWidths=[3 * inch, 1.5 * inch, 1.2 * inch])
        dt_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _RED),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 1, _BORDER),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ]))
        story.append(dt_table)


def _page_revenue_patterns(story, sty, df_a, df_b, days_a, days_b):
    """PAGE 3 (conditional): Revenue pattern comparison.

    Shows hourly chart when both periods are single days, daily chart when both
    are multi-day. Skips entirely if the time scales do not match.
    """
    both_single = (days_a == 1 and days_b == 1)
    both_multi = (days_a > 1 and days_b > 1)

    if not (both_single or both_multi):
        # Time scales don't match -- skip this page
        return

    story.append(PageBreak())

    if both_single and "Hour" in df_a.columns and "Hour" in df_b.columns:
        # Hourly comparison
        story.append(Paragraph("HOURLY REVENUE COMPARISON", sty["section"]))
        story.append(Paragraph(
            "Side-by-side hourly revenue for both days",
            sty["caption"],
        ))

        h_min = min(df_a["Hour"].min(), df_b["Hour"].min())
        h_max = max(df_a["Hour"].max(), df_b["Hour"].max())
        all_hrs = range(int(h_min), int(h_max) + 1)
        ha = df_a.groupby("Hour")["Revenue"].sum().reindex(all_hrs, fill_value=0)
        hb = df_b.groupby("Hour")["Revenue"].sum().reindex(all_hrs, fill_value=0)

        labels = [f"{int(h)}:00" for h in all_hrs]
        chart = render_line_chart(
            labels=labels,
            data_series=[ha.tolist(), hb.tolist()],
            width=450, height=220,
            dash_patterns=[None, [4, 2]],
        )
        story.append(chart)
        story.append(Paragraph(
            "<b>\u2014</b> Period A (solid) &nbsp; <b>- - -</b> Period B (dashed)",
            sty["caption"],
        ))

        # Peak hour comparison
        peak_a_hr = int(ha.idxmax()) if ha.sum() > 0 else 0
        peak_b_hr = int(hb.idxmax()) if hb.sum() > 0 else 0
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(
            f"Period A peaked at <b>{peak_a_hr}:00</b> (${ha.max():,.0f}). "
            f"Period B peaked at <b>{peak_b_hr}:00</b> (${hb.max():,.0f}).",
            sty["insight"],
        ))

    elif both_multi:
        # Daily comparison (aligned by day number)
        story.append(Paragraph("DAILY REVENUE COMPARISON", sty["section"]))
        story.append(Paragraph(
            "Revenue by day within each period (aligned by day number)",
            sty["caption"],
        ))

        da = df_a.groupby(df_a["Date"].dt.date)["Revenue"].sum().sort_index()
        db = df_b.groupby(df_b["Date"].dt.date)["Revenue"].sum().sort_index()
        max_d = max(len(da), len(db))

        labels = [f"Day {i + 1}" for i in range(max_d)]
        chart = render_line_chart(
            labels=labels,
            data_series=[da.tolist(), db.tolist()],
            width=450, height=220,
            dash_patterns=[None, [4, 2]],
        )
        story.append(chart)
        story.append(Paragraph(
            "<b>\u2014</b> Period A (solid) &nbsp; <b>- - -</b> Period B (dashed)",
            sty["caption"],
        ))

        # Best/worst day callout
        story.append(Spacer(1, 0.1 * inch))
        best_a = da.max()
        best_b = db.max()
        story.append(Paragraph(
            f"Best day in Period A: ${best_a:,.0f}. "
            f"Best day in Period B: ${best_b:,.0f}.",
            sty["insight"],
        ))


# ---------------------------------------------------------------------------
# Insight generator
# ---------------------------------------------------------------------------

def _build_insights(metrics, cat_chg_df, diff_lengths):
    """Assemble 3-5 insight bullets for the story page."""
    bullets = []
    label_note = " per day" if diff_lengths else ""

    # 1. Revenue change in dollar terms
    rev_delta = metrics["comp_rev_a"] - metrics["comp_rev_b"]
    direction = "increased" if rev_delta >= 0 else "decreased"
    bullets.append(
        f"Revenue {direction} by <b>${abs(rev_delta):,.0f}{label_note}</b> "
        f"({_fmt_pct(metrics['rev_pct'])})."
    )

    # 2. Top category gainer
    top_gainer = cat_chg_df.iloc[-1]
    if top_gainer["Delta"] > 0:
        bullets.append(
            f"Top category gainer: <b>{top_gainer['Category']}</b> "
            f"(+${abs(top_gainer['Delta']):,.0f}{label_note})."
        )

    # 3. Top category decliner
    top_decliner = cat_chg_df.iloc[0]
    if top_decliner["Delta"] < 0:
        bullets.append(
            f"Biggest category drop: <b>{top_decliner['Category']}</b> "
            f"(-${abs(top_decliner['Delta']):,.0f}{label_note})."
        )

    # 4. Basket value change
    avg_bask_pct = metrics["avg_bask_pct"]
    bask_delta = metrics["avg_bask_a"] - metrics["avg_bask_b"]
    if abs(avg_bask_pct) > 1:
        bask_dir = "rose" if bask_delta >= 0 else "fell"
        bullets.append(
            f"Average basket value {bask_dir} by <b>${abs(bask_delta):.2f}</b> "
            f"({_fmt_pct(avg_bask_pct)})."
        )

    # 5. Transaction volume change
    bask_pct = metrics["bask_pct"]
    if abs(bask_pct) > 1:
        trans_dir = "grew" if bask_pct >= 0 else "shrank"
        bullets.append(
            f"Transaction volume {trans_dir} by <b>{abs(bask_pct):.1f}%</b>{label_note}."
        )

    return bullets


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(df_a, df_b, date_a_start, date_a_end, date_b_start, date_b_end,
             selected_category, selected_product, day_filter_mode, hour_range):
    """Generate a narrative comparison PDF report. Returns BytesIO buffer.

    Page 1 is an executive brief with headline, metrics, and insights.
    Page 2 shows category and product changes.
    Page 3 (conditional) overlays revenue patterns when time scales match.
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

    days_a = (date_a_end - date_a_start).days + 1
    days_b = (date_b_end - date_b_start).days + 1
    diff_lengths = days_a != days_b

    # Pre-compute data used across pages
    metrics = _compute_metrics(df_a, df_b, days_a, days_b, diff_lengths)
    cat_chg_df = _compute_category_changes(df_a, df_b, days_a, days_b, diff_lengths)
    prod_chg_df = _compute_product_changes(df_a, df_b, days_a, days_b, diff_lengths)

    # PAGE 1: Executive brief
    _page_executive_brief(
        story, sty, df_a, df_b,
        date_a_start, date_a_end, date_b_start, date_b_end,
        days_a, days_b, diff_lengths, metrics, cat_chg_df,
        selected_category, selected_product, day_filter_mode, hour_range,
    )

    # PAGE 2: Category & product changes
    _page_category_product_changes(story, sty, cat_chg_df, prod_chg_df, diff_lengths)

    # PAGE 3: Revenue patterns (conditional -- skipped if time scales mismatch)
    _page_revenue_patterns(story, sty, df_a, df_b, days_a, days_b)

    doc.build(story)
    buf.seek(0)
    return buf
