"""Standard single-period PDF report generation using ReportLab."""

from collections import Counter
from datetime import datetime
from io import BytesIO
from itertools import combinations

import pandas as pd
from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import PDF_HEADER_BG, PDF_TEXT_PRIMARY, PDF_BORDER, PIE_COLORS


def generate(df, min_date, max_date, selected_category, selected_product, day_filter_mode, hour_range):
    """Generate a clean, factual PDF report. Returns BytesIO buffer."""
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

    days_span = (max_date - min_date).days + 1
    report_type = "Daily Report" if days_span == 1 else f"{days_span}-Day Report"

    # --- Cover ---
    story += [Spacer(1, 1.5 * inch)]
    story += [Paragraph("TMB HARRIS FARM", title_style)]
    story += [Paragraph("RETAIL SALES REPORT", ParagraphStyle("S", parent=styles["Heading2"], fontSize=16, alignment=TA_CENTER))]
    story += [Spacer(1, 0.5 * inch)]

    meta = [
        ["Report Type:", report_type],
        ["Period Start:", min_date.strftime("%B %d, %Y")],
        ["Period End:", max_date.strftime("%B %d, %Y")],
        ["Days Included:", f"{days_span} day{'s' if days_span != 1 else ''}"],
        ["Currency:", "AUD ($)"],
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
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [t, PageBreak()]

    # --- Key Metrics ---
    total_rev = df["Revenue"].sum()
    total_trans = len(df)
    num_baskets = df["Basket_ID"].nunique()
    avg_basket = df.groupby("Basket_ID")["Revenue"].sum().mean() if num_baskets > 0 else 0
    total_items = df["Quantity"].sum()
    avg_ipb = total_items / num_baskets if num_baskets > 0 else 0

    story += [Paragraph("KEY METRICS", heading)]
    metrics = [
        ["Metric", "Value"],
        ["Total Revenue", f"${total_rev:,.2f}"],
        ["Total Transactions", f"{total_trans:,}"],
        ["Unique Baskets", f"{num_baskets:,}"],
        ["Avg Basket Value", f"${avg_basket:.2f}"],
        ["Total Items Sold", f"{int(total_items):,}"],
        ["Avg Items per Basket", f"{avg_ipb:.1f}"],
    ]
    story += [_styled_table(metrics, [3.5 * inch, 2.5 * inch]), Spacer(1, 0.3 * inch)]

    # --- Revenue by Category ---
    story += [PageBreak(), Paragraph("REVENUE BY CATEGORY", heading)]
    cat_sum = df.groupby("Category").agg({"Revenue": "sum", "Quantity": "sum"}).sort_values("Revenue", ascending=True).reset_index()

    d1 = Drawing(450, 250)
    bc1 = HorizontalBarChart()
    bc1.x, bc1.y, bc1.height, bc1.width = 200, 30, 200, 200
    bc1.data = [cat_sum["Revenue"].tolist()]
    bc1.categoryAxis.categoryNames = [f"{c[:18]} (${r:,.0f})" for c, r in zip(cat_sum["Category"], cat_sum["Revenue"])]
    bc1.categoryAxis.labels.fontSize = 8
    bc1.categoryAxis.labels.fontName = "Helvetica-Bold"
    bc1.valueAxis.valueMin = 0
    bc1.valueAxis.labels.fontSize = 8
    bc1.bars[0].fillColor = colors.HexColor(PDF_HEADER_BG)
    d1.add(bc1)
    story += [d1, Spacer(1, 0.2 * inch)]

    # --- Top Products ---
    n_prod = min(10, max(5, len(df["Description"].unique()) // 3))
    story += [Paragraph(f"TOP {n_prod} PRODUCTS BY REVENUE", heading)]
    top_prod = df.groupby("Description").agg({"Revenue": "sum"}).sort_values("Revenue", ascending=True).tail(n_prod).reset_index()

    d2 = Drawing(450, 250)
    bc2 = HorizontalBarChart()
    bc2.x, bc2.y, bc2.height, bc2.width = 200, 30, 200, 200
    bc2.data = [top_prod["Revenue"].tolist()]
    bc2.categoryAxis.categoryNames = [f"{p[:15]} (${r:,.0f})" for p, r in zip(top_prod["Description"], top_prod["Revenue"])]
    bc2.categoryAxis.labels.fontSize = 7
    bc2.categoryAxis.labels.fontName = "Helvetica-Bold"
    bc2.valueAxis.valueMin = 0
    bc2.valueAxis.labels.fontSize = 8
    bc2.bars[0].fillColor = colors.HexColor(PDF_HEADER_BG)
    d2.add(bc2)
    story += [d2, Spacer(1, 0.2 * inch)]

    # --- Time chart ---
    story += [PageBreak()]
    if days_span == 1 and "Hour" in df.columns:
        story += [Paragraph("HOURLY REVENUE", heading)]
        h_min, h_max = int(df["Hour"].min()), int(df["Hour"].max())
        all_hrs = range(h_min, h_max + 1)
        hourly = df.groupby("Hour")["Revenue"].sum().reindex(all_hrs, fill_value=0).reset_index()
        hourly.columns = ["Hour", "Revenue"]

        d3 = Drawing(450, 220)
        lc = HorizontalLineChart()
        lc.x, lc.y, lc.height, lc.width = 50, 50, 140, 350
        lc.data = [hourly["Revenue"].tolist()]
        lc.categoryAxis.categoryNames = [f"{int(h)}:00" for h in hourly["Hour"]]
        lc.categoryAxis.labels.fontSize = 9
        lc.valueAxis.valueMin = 0
        lc.lines[0].strokeColor = colors.HexColor(PDF_HEADER_BG)
        lc.lines[0].strokeWidth = 2.5
        lc.lineLabelFormat = "%d"
        lc.lineLabels.fontName = "Helvetica-Bold"
        lc.lineLabels.fontSize = 9
        lc.lineLabels.boxAnchor = "n"
        lc.lineLabels.dy = 5
        lc.categoryAxis.visibleGrid = 1
        lc.categoryAxis.gridStrokeColor = colors.HexColor("#D1D5DB")
        lc.categoryAxis.gridStrokeDashArray = [2, 2]
        d3.add(lc)
        story += [d3]
    else:
        story += [Paragraph("DAILY REVENUE", heading)]
        date_rng = pd.date_range(start=min_date, end=max_date, freq="D")
        daily = df.groupby(df["Date"].dt.date)["Revenue"].sum().reindex(
            [d.date() for d in date_rng], fill_value=0
        ).reset_index()
        daily.columns = ["Date", "Revenue"]

        d3 = Drawing(450, 220)
        lc = HorizontalLineChart()
        lc.x, lc.y, lc.height, lc.width = 50, 50, 140, 350
        lc.data = [daily["Revenue"].tolist()]
        lc.categoryAxis.categoryNames = (
            [d.strftime("%a %m/%d") for d in daily["Date"]] if len(daily) <= 7
            else [d.strftime("%m/%d") for d in daily["Date"]]
        )
        lc.categoryAxis.labels.angle = 45
        lc.categoryAxis.labels.fontSize = 9
        lc.valueAxis.valueMin = 0
        lc.lines[0].strokeColor = colors.HexColor(PDF_HEADER_BG)
        lc.lines[0].strokeWidth = 2.5
        lc.categoryAxis.visibleGrid = 1
        lc.categoryAxis.gridStrokeColor = colors.HexColor("#D1D5DB")
        lc.categoryAxis.gridStrokeDashArray = [2, 2]
        d3.add(lc)
        story += [d3]

    story += [Spacer(1, 0.3 * inch)]

    # --- Hourly distribution (multi-day only) ---
    if "Hour" in df.columns and days_span > 1:
        story += [Paragraph("HOURLY REVENUE DISTRIBUTION", heading)]
        h_min, h_max = int(df["Hour"].min()), int(df["Hour"].max())
        all_hrs = range(h_min, h_max + 1)
        hourly = df.groupby("Hour")["Revenue"].sum().reindex(all_hrs, fill_value=0).reset_index()
        hourly.columns = ["Hour", "Revenue"]

        d4 = Drawing(450, 220)
        bc4 = VerticalBarChart()
        bc4.x, bc4.y, bc4.height, bc4.width = 50, 50, 140, 350
        bc4.data = [hourly["Revenue"].tolist()]
        bc4.categoryAxis.categoryNames = [f"{int(h)}:00" for h in hourly["Hour"]]
        bc4.categoryAxis.labels.fontSize = 9
        bc4.valueAxis.valueMin = 0
        bc4.bars[0].fillColor = colors.HexColor(PDF_HEADER_BG)
        bc4.barWidth = 20
        bc4.barLabels.fontName = "Helvetica-Bold"
        bc4.barLabels.fontSize = 8
        bc4.barLabelFormat = lambda x: f"${x:,.0f}" if x > 0 else ""
        bc4.barLabels.nudge = 5
        d4.add(bc4)
        story += [d4, Spacer(1, 0.3 * inch)]

    # --- Category pie ---
    story += [PageBreak(), Paragraph("CATEGORY REVENUE DISTRIBUTION", heading)]
    cat_pie = df.groupby("Category")["Revenue"].sum().sort_values(ascending=False).reset_index()
    total_pie = cat_pie["Revenue"].sum()

    d5 = Drawing(450, 250)
    pie = Pie()
    pie.x, pie.y, pie.width, pie.height = 125, 20, 150, 150
    pie.data = cat_pie["Revenue"].tolist()
    pie.labels = [f"{c[:15]}\n{r / total_pie * 100:.1f}%" for c, r in zip(cat_pie["Category"], cat_pie["Revenue"])]
    pie.slices.strokeWidth = 1
    pie.slices.strokeColor = colors.white
    pie.slices.fontName = "Helvetica-Bold"
    pie.slices.fontSize = 9
    pie.sideLabels = 1
    pie.simpleLabels = 0
    pie.sideLabelsOffset = 0.2
    for i, hex_col in enumerate(PIE_COLORS[: len(pie.data)]):
        pie.slices[i].fillColor = colors.HexColor(hex_col)
    d5.add(pie)
    story += [d5, Spacer(1, 0.3 * inch)]

    # --- Basket size ---
    story += [Paragraph("BASKET SIZE DISTRIBUTION", heading)]
    basket_rev = df.groupby("Basket_ID")["Revenue"].sum()
    bins = [0, 15, 30, 50, 100, 1000]
    lbls = ["$0-15", "$15-30", "$30-50", "$50-100", "$100+"]
    dist = pd.cut(basket_rev, bins=bins, labels=lbls).value_counts().reindex(lbls, fill_value=0)

    d6 = Drawing(450, 200)
    bc6 = VerticalBarChart()
    bc6.x, bc6.y, bc6.height, bc6.width = 75, 50, 125, 300
    bc6.data = [dist.tolist()]
    bc6.categoryAxis.categoryNames = lbls
    bc6.categoryAxis.labels.fontSize = 9
    bc6.valueAxis.valueMin = 0
    bc6.bars[0].fillColor = colors.HexColor(PDF_HEADER_BG)
    bc6.barLabels.fontName = "Helvetica-Bold"
    bc6.barLabels.fontSize = 10
    bc6.barLabelFormat = lambda x: f"{int(x)}" if x > 0 else ""
    bc6.barLabels.nudge = 5
    d6.add(bc6)
    story += [d6, Spacer(1, 0.3 * inch)]

    # --- Product Pairs ---
    story += [PageBreak(), Paragraph("TOP PRODUCT PAIRS", heading)]
    story += [Paragraph("Products frequently purchased together",
                        ParagraphStyle("SC", parent=styles["Normal"], fontSize=10,
                                       textColor=colors.HexColor("#6B7280"), spaceAfter=12))]

    multi = df.groupby("Basket_ID").filter(lambda x: len(x) > 1)
    if len(multi) > 0:
        basket_pairs = []
        for _, grp in multi.groupby("Basket_ID"):
            for pair in combinations(sorted(set(grp["Description"])), 2):
                basket_pairs.append(pair)
        if basket_pairs:
            top_pairs = Counter(basket_pairs).most_common(10)
            pairs_data = [["Product A", "Product B", "Times Purchased Together"]]
            for pair, count in top_pairs:
                pairs_data.append([pair[0][:30], pair[1][:30], f"{count:,}"])
            story += [_styled_table(pairs_data, [2.5 * inch, 2.5 * inch, 1.5 * inch])]
            top_pair = top_pairs[0]
            story += [Spacer(1, 0.2 * inch)]
            story += [Paragraph(
                f"<b>Most Common Pair:</b> {top_pair[0][0]} + {top_pair[0][1]} "
                f"purchased together {top_pair[1]} times",
                ParagraphStyle("Ins", parent=styles["Normal"], fontSize=11,
                               leftIndent=10, rightIndent=10, spaceAfter=20,
                               backColor=colors.HexColor("#F9FAFB"), borderPadding=15,
                               borderWidth=1, borderColor=colors.HexColor(PDF_BORDER)),
            )]
        else:
            story += [Paragraph("No product pairs found (all baskets contain single items)", styles["Normal"])]
    else:
        story += [Paragraph("No multi-item baskets in this period", styles["Normal"])]

    # --- Category Penetration ---
    story += [PageBreak(), Paragraph("CATEGORY PENETRATION", heading)]
    story += [Paragraph("Percentage of baskets containing each category",
                        ParagraphStyle("SC2", parent=styles["Normal"], fontSize=10,
                                       textColor=colors.HexColor("#6B7280"), spaceAfter=12))]
    total_baskets = df["Basket_ID"].nunique()
    if total_baskets > 0:
        cat_bask = df.groupby("Category")["Basket_ID"].nunique().reset_index()
        cat_bask.columns = ["Category", "Baskets"]
        cat_bask["Penetration"] = (cat_bask["Baskets"] / total_baskets * 100).round(1)
        cat_bask = cat_bask.sort_values("Penetration", ascending=True)

        dp = Drawing(450, 250)
        bcp = HorizontalBarChart()
        bcp.x, bcp.y, bcp.height, bcp.width = 200, 30, 200, 200
        bcp.data = [cat_bask["Penetration"].tolist()]
        bcp.categoryAxis.categoryNames = [f"{c[:20]} ({p:.1f}%)" for c, p in zip(cat_bask["Category"], cat_bask["Penetration"])]
        bcp.categoryAxis.labels.fontSize = 9
        bcp.categoryAxis.labels.fontName = "Helvetica-Bold"
        bcp.valueAxis.valueMin = 0
        bcp.valueAxis.valueMax = 100
        bcp.valueAxis.labels.fontSize = 8
        bcp.valueAxis.labelTextFormat = "%d%%"
        bcp.bars[0].fillColor = colors.HexColor(PDF_HEADER_BG)
        dp.add(bcp)
        story += [dp, Spacer(1, 0.3 * inch)]

        top_cat = cat_bask.iloc[-1]
        story += [Paragraph(
            f"<b>Highest Penetration:</b> {top_cat['Category']} appears in {top_cat['Penetration']:.1f}% "
            f"of baskets ({int(top_cat['Baskets'])} out of {total_baskets} baskets)",
            ParagraphStyle("Ins2", parent=styles["Normal"], fontSize=11,
                           leftIndent=10, rightIndent=10, spaceAfter=20,
                           backColor=colors.HexColor("#F9FAFB"), borderPadding=15,
                           borderWidth=1, borderColor=colors.HexColor(PDF_BORDER)),
        )]

    # --- Data tables ---
    story += [PageBreak(), Paragraph("DETAILED DATA", heading)]

    story += [Paragraph(f"Top {n_prod} Products by Revenue",
                        ParagraphStyle("SH", parent=styles["Heading3"], fontSize=12, spaceAfter=8))]
    top_full = df.groupby("Description").agg({"Revenue": "sum", "Quantity": "sum"}).sort_values(
        "Revenue", ascending=False
    ).head(n_prod).reset_index()
    prod_rows = [["Product", "Revenue", "% Total", "Units"]]
    for _, row in top_full.iterrows():
        pct = row["Revenue"] / total_rev * 100 if total_rev > 0 else 0
        prod_rows.append([row["Description"][:35], f"${row['Revenue']:,.2f}", f"{pct:.1f}%", f"{int(row['Quantity']):,}"])
    story += [_styled_table(prod_rows, [3 * inch, 1.5 * inch, 0.8 * inch, 0.8 * inch]), Spacer(1, 0.4 * inch)]

    story += [Paragraph("Category Breakdown",
                        ParagraphStyle("SH2", parent=styles["Heading3"], fontSize=12, spaceAfter=8))]
    cat_sorted = cat_sum.sort_values("Revenue", ascending=False)
    cat_rows = [["Category", "Revenue", "% Total", "Units"]]
    for _, row in cat_sorted.iterrows():
        pct = row["Revenue"] / total_rev * 100 if total_rev > 0 else 0
        cat_rows.append([row["Category"], f"${row['Revenue']:,.2f}", f"{pct:.1f}%", f"{int(row['Quantity']):,}"])
    story += [_styled_table(cat_rows, [2.5 * inch, 1.5 * inch, 0.8 * inch, 0.8 * inch])]

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
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.HexColor(PDF_BORDER)),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t
