"""Comparison PDF report generation - delta-focused analysis between two periods."""

from datetime import datetime
from io import BytesIO

import pandas as pd
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import PDF_HEADER_BG, PDF_TEXT_PRIMARY, PDF_BORDER, PDF_POSITIVE, PDF_NEGATIVE


def generate(df_a, df_b, date_a_start, date_a_end, date_b_start, date_b_end,
             selected_category, selected_product, day_filter_mode, hour_range):
    """Generate comparison PDF report. Returns BytesIO buffer."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CTitle", parent=styles["Heading1"], fontSize=24,
        textColor=colors.HexColor(PDF_TEXT_PRIMARY), spaceAfter=10,
        alignment=TA_CENTER, fontName="Helvetica-Bold",
    )
    heading = ParagraphStyle(
        "CHead", parent=styles["Heading2"], fontSize=14,
        textColor=colors.HexColor(PDF_TEXT_PRIMARY), spaceAfter=10,
        spaceBefore=16, fontName="Helvetica-Bold",
    )

    days_a = (date_a_end - date_a_start).days + 1
    days_b = (date_b_end - date_b_start).days + 1
    diff_lengths = days_a != days_b

    # --- Cover ---
    story += [Spacer(1, 1.5 * inch)]
    story += [Paragraph("TMB HARRIS FARM", title_style)]
    story += [Paragraph("PERIOD COMPARISON REPORT",
                        ParagraphStyle("S", parent=styles["Heading2"], fontSize=16, alignment=TA_CENTER))]
    story += [Spacer(1, 0.5 * inch)]

    meta = [
        ["Period A:", f"{date_a_start.strftime('%B %d, %Y')} - {date_a_end.strftime('%B %d, %Y')} ({days_a} day{'s' if days_a != 1 else ''})"],
        ["Period B:", f"{date_b_start.strftime('%B %d, %Y')} - {date_b_end.strftime('%B %d, %Y')} ({days_b} day{'s' if days_b != 1 else ''})"],
        ["Generated:", datetime.now().strftime("%B %d, %Y at %I:%M %p")],
    ]
    if selected_category != "All Categories":
        meta.append(["Category Filter:", selected_category])
    if selected_product != "All Products":
        meta.append(["Product Filter:", selected_product])
    if day_filter_mode != "All Days":
        meta.append(["Day Filter:", day_filter_mode])
    if hour_range:
        meta.append(["Hour Filter:", f"{hour_range[0]}:00 - {hour_range[1]}:00"])

    t = Table(meta, colWidths=[2 * inch, 4 * inch])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, -1), "RIGHT"), ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [t]

    if diff_lengths:
        story += [Spacer(1, 0.3 * inch)]
        story += [Paragraph(
            "Different period lengths - all % changes calculated using daily averages for fair comparison",
            ParagraphStyle("Warn", parent=styles["Normal"], fontSize=10,
                           textColor=colors.HexColor("#D97706"),
                           backColor=colors.HexColor("#FEF3C7"),
                           borderPadding=10, borderWidth=1, borderColor=colors.HexColor("#F59E0B")),
        )]

    story += [PageBreak()]

    # --- Key Metrics ---
    story += [Paragraph("KEY METRICS COMPARISON", heading)]

    rev_a, rev_b = df_a["Revenue"].sum(), df_b["Revenue"].sum()
    trans_a, trans_b = len(df_a), len(df_b)
    bask_a, bask_b = df_a["Basket_ID"].nunique(), df_b["Basket_ID"].nunique()
    avg_bask_a = df_a.groupby("Basket_ID")["Revenue"].sum().mean() if bask_a > 0 else 0
    avg_bask_b = df_b.groupby("Basket_ID")["Revenue"].sum().mean() if bask_b > 0 else 0
    items_a, items_b = df_a["Quantity"].sum(), df_b["Quantity"].sum()
    ipb_a = items_a / bask_a if bask_a > 0 else 0
    ipb_b = items_b / bask_b if bask_b > 0 else 0

    def _chg(a, b):
        if b == 0:
            return "N/A"
        pct = (a - b) / b * 100
        arrow = "+" if pct > 0 else "" if pct < 0 else ""
        return f"{arrow}{pct:.1f}%"

    if diff_lengths:
        dr_a, dr_b = rev_a / days_a, rev_b / days_b
        dt_a, dt_b = trans_a / days_a, trans_b / days_b
        db_a, db_b = bask_a / days_a, bask_b / days_b
        rows = [
            ["Metric", "Period A", "Period B", "Change"],
            ["Total Revenue", f"${rev_a:,.2f}", f"${rev_b:,.2f}", "See daily avg"],
            ["Daily Avg Revenue", f"${dr_a:,.2f}", f"${dr_b:,.2f}", _chg(dr_a, dr_b)],
            ["Total Transactions", f"{trans_a:,}", f"{trans_b:,}", "See daily avg"],
            ["Daily Avg Trans", f"{dt_a:.1f}", f"{dt_b:.1f}", _chg(dt_a, dt_b)],
            ["Unique Baskets", f"{bask_a:,}", f"{bask_b:,}", "See daily avg"],
            ["Daily Avg Baskets", f"{db_a:.1f}", f"{db_b:.1f}", _chg(db_a, db_b)],
            ["Avg Basket Value", f"${avg_bask_a:.2f}", f"${avg_bask_b:.2f}", _chg(avg_bask_a, avg_bask_b)],
            ["Items per Basket", f"{ipb_a:.2f}", f"{ipb_b:.2f}", _chg(ipb_a, ipb_b)],
        ]
    else:
        rows = [
            ["Metric", "Period A", "Period B", "Change"],
            ["Total Revenue", f"${rev_a:,.2f}", f"${rev_b:,.2f}", _chg(rev_a, rev_b)],
            ["Transactions", f"{trans_a:,}", f"{trans_b:,}", _chg(trans_a, trans_b)],
            ["Unique Baskets", f"{bask_a:,}", f"{bask_b:,}", _chg(bask_a, bask_b)],
            ["Avg Basket Value", f"${avg_bask_a:.2f}", f"${avg_bask_b:.2f}", _chg(avg_bask_a, avg_bask_b)],
            ["Total Items Sold", f"{int(items_a):,}", f"{int(items_b):,}", _chg(items_a, items_b)],
            ["Items per Basket", f"{ipb_a:.2f}", f"{ipb_b:.2f}", _chg(ipb_a, ipb_b)],
        ]

    mt = Table(rows, colWidths=[2.5 * inch, 1.5 * inch, 1.5 * inch, 1.2 * inch])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PDF_HEADER_BG)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (0, -1), "LEFT"), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("GRID", (0, 0), (-1, -1), 1, colors.HexColor(PDF_BORDER)),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 1), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story += [mt, PageBreak()]

    # --- Category Changes ---
    story += [Paragraph("CATEGORY REVENUE CHANGES", heading)]
    cat_a = df_a.groupby("Category")["Revenue"].sum()
    cat_b = df_b.groupby("Category")["Revenue"].sum()
    if diff_lengths:
        cat_a, cat_b = cat_a / days_a, cat_b / days_b
    label_suffix = " (daily avg)" if diff_lengths else ""

    all_cats = sorted(set(cat_a.index) | set(cat_b.index))
    changes = []
    for cat in all_cats:
        ra, rb = cat_a.get(cat, 0), cat_b.get(cat, 0)
        changes.append({"Category": cat, "Delta": ra - rb, "RevA": ra, "RevB": rb})
    chg_df = pd.DataFrame(changes).sort_values("Delta", ascending=True)

    dc = Drawing(450, 250)
    bc = HorizontalBarChart()
    bc.x, bc.y, bc.height, bc.width = 180, 30, 200, 220

    # Single data series with per-bar coloring via tuple index
    delta_vals = chg_df["Delta"].tolist()
    bc.data = [delta_vals]
    bc.categoryAxis.categoryNames = [f"{r['Category'][:15]} ({r['Delta']:+.0f}{label_suffix})"
                                     for _, r in chg_df.iterrows()]
    bc.categoryAxis.labels.fontSize = 8
    bc.categoryAxis.labels.fontName = "Helvetica-Bold"
    bc.valueAxis.labels.fontSize = 8
    bc.bars[0].fillColor = colors.HexColor(PDF_HEADER_BG)
    # Color each bar green (positive) or red (negative)
    for i, val in enumerate(delta_vals):
        bc.bars[(0, i)].fillColor = colors.HexColor(PDF_POSITIVE if val >= 0 else PDF_NEGATIVE)
    dc.add(bc)
    story += [dc, Spacer(1, 0.2 * inch)]

    top_gainer = chg_df.iloc[-1]
    top_decliner = chg_df.iloc[0]
    if top_gainer["Delta"] > 0:
        story += [Paragraph(
            f"<b>Top Gainer:</b> {top_gainer['Category']} (+${abs(top_gainer['Delta']):.0f}{label_suffix})",
            ParagraphStyle("G", parent=styles["Normal"], fontSize=11,
                           backColor=colors.HexColor("#F0FDF4"), borderPadding=10),
        )]
    if top_decliner["Delta"] < 0:
        story += [Paragraph(
            f"<b>Top Decliner:</b> {top_decliner['Category']} (-${abs(top_decliner['Delta']):.0f}{label_suffix})",
            ParagraphStyle("D", parent=styles["Normal"], fontSize=11,
                           backColor=colors.HexColor("#FEF2F2"), borderPadding=10),
        )]

    story += [PageBreak()]

    # --- Top Product Movers ---
    story += [Paragraph("TOP PRODUCT MOVERS", heading)]
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
    pchg = pd.DataFrame(prod_changes).sort_values("Delta", ascending=False)

    gainers = pchg[pchg["Delta"] > 0].head(5)
    decliners = pchg[pchg["Delta"] < 0].tail(5).iloc[::-1]

    g_data = [["Top 5 Gainers", "Change"]]
    for _, r in gainers.iterrows():
        g_data.append([r["Product"][:25], f"+${r['Delta']:.0f} ({r['Percent']:+.0f}%)"])
    gt = Table(g_data, colWidths=[2.5 * inch, 1 * inch])
    gt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PDF_POSITIVE)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 1, colors.HexColor(PDF_BORDER)), ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    d_data = [["Top 5 Decliners", "Change"]]
    for _, r in decliners.iterrows():
        d_data.append([r["Product"][:25], f"${r['Delta']:.0f} ({r['Percent']:.0f}%)"])
    dt = Table(d_data, colWidths=[2.5 * inch, 1 * inch])
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PDF_NEGATIVE)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 1, colors.HexColor(PDF_BORDER)), ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [gt, Spacer(1, 0.2 * inch), dt, PageBreak()]

    # --- Revenue Patterns ---
    story += [Paragraph("REVENUE PATTERNS", heading)]

    if days_a == 1 and days_b == 1 and "Hour" in df_a.columns and "Hour" in df_b.columns:
        story += [Paragraph("Hourly Revenue Comparison", styles["Heading3"])]
        h_min = min(df_a["Hour"].min(), df_b["Hour"].min())
        h_max = max(df_a["Hour"].max(), df_b["Hour"].max())
        all_hrs = range(int(h_min), int(h_max) + 1)
        ha = df_a.groupby("Hour")["Revenue"].sum().reindex(all_hrs, fill_value=0)
        hb = df_b.groupby("Hour")["Revenue"].sum().reindex(all_hrs, fill_value=0)

        dr = Drawing(450, 220)
        lc = HorizontalLineChart()
        lc.x, lc.y, lc.height, lc.width = 50, 50, 140, 350
        lc.data = [ha.tolist(), hb.tolist()]
        lc.categoryAxis.categoryNames = [f"{int(h)}:00" for h in all_hrs]
        lc.categoryAxis.labels.fontSize = 9
        lc.valueAxis.valueMin = 0
        lc.lines[0].strokeColor = colors.HexColor(PDF_HEADER_BG)
        lc.lines[0].strokeWidth = 2.5
        lc.lines[1].strokeColor = colors.HexColor(PDF_NEGATIVE)
        lc.lines[1].strokeWidth = 2.5
        lc.lines[1].strokeDashArray = [4, 2]
        lc.categoryAxis.visibleGrid = 1
        lc.categoryAxis.gridStrokeColor = colors.HexColor("#D1D5DB")
        lc.categoryAxis.gridStrokeDashArray = [2, 2]
        dr.add(lc)
        story += [dr, Paragraph("<b>-</b> Period A (solid)  <b>- - -</b> Period B (dashed)", styles["Normal"])]

    elif days_a > 1 and days_b > 1:
        story += [Paragraph("Daily Revenue Comparison", styles["Heading3"])]
        da = df_a.groupby(df_a["Date"].dt.date)["Revenue"].sum()
        db = df_b.groupby(df_b["Date"].dt.date)["Revenue"].sum()
        max_d = max(len(da), len(db))

        dr = Drawing(450, 220)
        lc = HorizontalLineChart()
        lc.x, lc.y, lc.height, lc.width = 50, 50, 140, 350
        lc.data = [da.tolist(), db.tolist()]
        lc.categoryAxis.categoryNames = [f"Day {i + 1}" for i in range(max_d)]
        lc.categoryAxis.labels.angle = 45
        lc.categoryAxis.labels.fontSize = 8
        lc.valueAxis.valueMin = 0
        lc.lines[0].strokeColor = colors.HexColor(PDF_HEADER_BG)
        lc.lines[0].strokeWidth = 2.5
        lc.lines[1].strokeColor = colors.HexColor(PDF_NEGATIVE)
        lc.lines[1].strokeWidth = 2.5
        lc.lines[1].strokeDashArray = [4, 2]
        lc.categoryAxis.visibleGrid = 1
        lc.categoryAxis.gridStrokeColor = colors.HexColor("#D1D5DB")
        lc.categoryAxis.gridStrokeDashArray = [2, 2]
        dr.add(lc)
        story += [dr, Paragraph("<b>-</b> Period A (solid)  <b>- - -</b> Period B (dashed)", styles["Normal"])]
    else:
        story += [Paragraph("Revenue charts shown separately due to different time scales", styles["Normal"])]

    story += [PageBreak()]

    # --- Executive Summary ---
    story += [Paragraph("EXECUTIVE SUMMARY", heading)]
    pts = []
    if diff_lengths:
        dr_a, dr_b = rev_a / days_a, rev_b / days_b
        rp = ((dr_a - dr_b) / dr_b * 100) if dr_b > 0 else 0
        if rp > 0:
            pts.append(f"Daily revenue up {rp:.1f}% (${dr_a - dr_b:+.2f} per day)")
        elif rp < 0:
            pts.append(f"Daily revenue down {abs(rp):.1f}% (${dr_a - dr_b:.2f} per day)")
    else:
        rp = ((rev_a - rev_b) / rev_b * 100) if rev_b > 0 else 0
        if rp > 0:
            pts.append(f"Revenue up {rp:.1f}% (${rev_a - rev_b:+.2f})")
        elif rp < 0:
            pts.append(f"Revenue down {abs(rp):.1f}% (${rev_a - rev_b:.2f})")

    if top_gainer["Delta"] > 0:
        pts.append(f"{top_gainer['Category']} leading growth (+${abs(top_gainer['Delta']):.0f})")

    bp = ((avg_bask_a - avg_bask_b) / avg_bask_b * 100) if avg_bask_b > 0 else 0
    if abs(bp) > 1:
        pts.append(f"Average basket value {'improving' if bp > 0 else 'declining'} ({bp:+.1f}%)")

    if len(gainers) > 0:
        tp = gainers.iloc[0]
        pts.append(f"{tp['Product']} top performer (+${tp['Delta']:.0f})")

    story += [Paragraph("<b>KEY TAKEAWAYS</b>", styles["Heading3"])]
    summary = "\n".join(f"- {p}" for p in pts) if pts else "No significant changes detected"
    story += [Paragraph(summary, styles["Normal"])]

    doc.build(story)
    buf.seek(0)
    return buf
