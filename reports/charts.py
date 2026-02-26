"""Shared PDF chart rendering functions for ReportLab reports.

Each function returns a ReportLab Drawing object ready to be added to a
platypus story. Extracted from standard.py, average_day.py, and comparison.py
to eliminate duplicated chart-building code.
"""

from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors

from config import PDF_HEADER_BG, PDF_POSITIVE, PDF_NEGATIVE, PIE_COLORS


def render_horizontal_bar_chart(labels, values, width=420, height=250,
                                bar_color=None, label_format="${:,.0f}",
                                value_suffix=""):
    """Horizontal bar chart for top products, category revenue, penetration, etc.

    Args:
        labels: Category names (displayed on the Y axis).
        values: Numeric values (one per label).
        width: Drawing width in points.
        height: Drawing height in points.
        bar_color: Hex color string for bars. Defaults to PDF_HEADER_BG.
        label_format: Python format string applied to each value in the label.
                      E.g. "${:,.0f}" produces "$1,234".
        value_suffix: Appended after the formatted value in each label.
                      E.g. "%" produces "(45.2%)".

    Returns:
        A Drawing containing the chart.
    """
    if not values:
        return Drawing(width, height)

    bar_color = bar_color or PDF_HEADER_BG

    d = Drawing(width, height)
    bc = HorizontalBarChart()

    # Layout: leave room for labels on the left
    bc.x = int(width * 0.45)
    bc.y = 30
    bc.height = height - 60
    bc.width = int(width * 0.48)

    bc.data = [list(values)]

    # Build axis labels: truncated name + formatted value
    cat_names = []
    for lbl, val in zip(labels, values):
        truncated = lbl[:22]
        formatted = label_format.format(val) + value_suffix
        cat_names.append(f"{truncated} ({formatted})")
    bc.categoryAxis.categoryNames = cat_names

    bc.categoryAxis.labels.fontSize = 7
    bc.categoryAxis.labels.fontName = "Helvetica-Bold"
    bc.valueAxis.valueMin = 0
    bc.valueAxis.labels.fontSize = 8
    bc.bars[0].fillColor = colors.HexColor(bar_color)

    d.add(bc)
    return d


def render_vertical_bar_chart(labels, values, width=420, height=250,
                              bar_color=None):
    """Vertical bar chart for hourly distribution, basket sizes, etc.

    Args:
        labels: Category names (X axis).
        values: Numeric values (one per label).
        width: Drawing width in points.
        height: Drawing height in points.
        bar_color: Hex color string for bars. Defaults to PDF_HEADER_BG.

    Returns:
        A Drawing containing the chart.
    """
    if not values:
        return Drawing(width, height)

    bar_color = bar_color or PDF_HEADER_BG

    d = Drawing(width, height)
    bc = VerticalBarChart()

    bc.x = 60
    bc.y = 50
    bc.height = height - 90
    bc.width = width - 110

    bc.data = [list(values)]
    bc.categoryAxis.categoryNames = list(labels)
    bc.categoryAxis.labels.fontSize = 9
    bc.valueAxis.valueMin = 0
    bc.bars[0].fillColor = colors.HexColor(bar_color)
    bc.barWidth = 20
    bc.barLabels.fontName = "Helvetica-Bold"
    bc.barLabels.fontSize = 8
    bc.barLabelFormat = lambda x: f"${x:,.0f}" if x > 0 else ""
    bc.barLabels.nudge = 5

    d.add(bc)
    return d


def render_delta_bar_chart(labels, values, width=420, height=250):
    """Horizontal bar chart with per-bar green/red coloring for deltas.

    Positive values are colored PDF_POSITIVE (green), negative values
    are colored PDF_NEGATIVE (red). Used for comparison period changes.

    Args:
        labels: Category names (Y axis).
        values: Delta values (can be positive or negative).
        width: Drawing width in points.
        height: Drawing height in points.

    Returns:
        A Drawing containing the chart.
    """
    if not values:
        return Drawing(width, height)

    d = Drawing(width, height)
    bc = HorizontalBarChart()

    bc.x = int(width * 0.40)
    bc.y = 30
    bc.height = height - 60
    bc.width = int(width * 0.50)

    bc.data = [list(values)]
    bc.categoryAxis.categoryNames = list(labels)
    bc.categoryAxis.labels.fontSize = 8
    bc.categoryAxis.labels.fontName = "Helvetica-Bold"
    bc.valueAxis.labels.fontSize = 8

    # Default fill — overridden per bar below
    bc.bars[0].fillColor = colors.HexColor(PDF_HEADER_BG)

    for i, val in enumerate(values):
        bc.bars[(0, i)].fillColor = colors.HexColor(
            PDF_POSITIVE if val >= 0 else PDF_NEGATIVE
        )

    d.add(bc)
    return d


def render_line_chart(labels, data_series, width=420, height=200,
                      line_colors=None, dash_patterns=None):
    """Time-series line chart supporting multiple lines.

    Args:
        labels: X-axis category names (e.g. dates, hours).
        data_series: List of lists — each inner list is one data series.
        width: Drawing width in points.
        height: Drawing height in points.
        line_colors: List of hex color strings, one per series.
                     Defaults to [PDF_HEADER_BG, PDF_NEGATIVE, ...].
        dash_patterns: List of dash arrays per series (e.g. [[4,2], None]).
                       None entries produce solid lines.

    Returns:
        A Drawing containing the chart.
    """
    if not data_series or not data_series[0]:
        return Drawing(width, height)

    default_colors = [PDF_HEADER_BG, PDF_NEGATIVE, "#2563EB", "#D97706", "#7C3AED"]
    line_colors = line_colors or default_colors

    d = Drawing(width, height)
    lc = HorizontalLineChart()

    lc.x = 50
    lc.y = 50
    lc.height = height - 80
    lc.width = width - 100

    lc.data = [list(series) for series in data_series]

    # Show every Nth label for readability
    n_labels = len(labels)
    step = max(1, n_labels // 12)
    cat_names = []
    for i, lbl in enumerate(labels):
        cat_names.append(lbl if i % step == 0 else "")
    lc.categoryAxis.categoryNames = cat_names

    lc.categoryAxis.labels.fontSize = 8
    lc.categoryAxis.labels.angle = 45 if n_labels > 8 else 0
    lc.valueAxis.valueMin = 0

    # Style each line
    for idx in range(len(data_series)):
        color = line_colors[idx % len(line_colors)]
        lc.lines[idx].strokeColor = colors.HexColor(color)
        lc.lines[idx].strokeWidth = 2.5

        if dash_patterns and idx < len(dash_patterns) and dash_patterns[idx]:
            lc.lines[idx].strokeDashArray = dash_patterns[idx]

    # Grid lines
    lc.categoryAxis.visibleGrid = 1
    lc.categoryAxis.gridStrokeColor = colors.HexColor("#D1D5DB")
    lc.categoryAxis.gridStrokeDashArray = [2, 2]

    d.add(lc)
    return d


def render_pie_chart(labels, values, width=300, height=200):
    """Pie chart for category distribution. Uses PIE_COLORS cycling.

    Hides labels for slices that represent less than 3% of the total.

    Args:
        labels: Slice names.
        values: Slice values (will be shown as percentages).
        width: Drawing width in points.
        height: Drawing height in points.

    Returns:
        A Drawing containing the chart.
    """
    if not values:
        return Drawing(width, height)

    total = sum(values)
    if total <= 0:
        return Drawing(width, height)

    d = Drawing(width, height)
    pie = Pie()

    pie.x = int(width * 0.30)
    pie.y = 15
    pie.width = int(width * 0.40)
    pie.height = int(height * 0.70)

    pie.data = list(values)
    pie.labels = [
        f"{lbl[:15]}\n{val / total * 100:.1f}%"
        for lbl, val in zip(labels, values)
    ]

    pie.slices.strokeWidth = 1
    pie.slices.strokeColor = colors.white
    pie.slices.fontName = "Helvetica-Bold"
    pie.slices.fontSize = 8
    pie.sideLabels = 1
    pie.simpleLabels = 0
    pie.sideLabelsOffset = 0.25

    for i in range(len(values)):
        color_hex = PIE_COLORS[i % len(PIE_COLORS)]
        pie.slices[i].fillColor = colors.HexColor(color_hex)
        # Hide labels for tiny slices to prevent overlap
        pct = values[i] / total * 100
        if pct < 3:
            pie.slices[i].label_visible = 0
            pie.labels[i] = ""

    d.add(pie)
    return d
